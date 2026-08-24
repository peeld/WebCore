#!/usr/bin/env python3
"""
deploy.py -- deploy the local repo to the production server directly,
bypassing GitHub Actions (avoids needing CI-side auth for the core/modules
git submodules).

Mirrors .github/workflows/deploy.yml (build the frontend, ship the repo,
regen module manifests, install deps, migrate, collectstatic, restart),
but ships source over a tar-over-ssh pipe instead of rsync, builds the
frontend ON THE SERVER (its own Node/npm -- this machine only needs
git/tar/ssh/curl), and never touches the live release directory in place.
Each deploy builds a full new release alongside the live one, activates
it there (module manifests, pip install, npm build, migrate,
collectstatic), and only swaps it into place (two `mv`s) once activation
succeeds -- so a failure at any point before the swap leaves the live
site completely untouched. The previous release is kept as APP_DIR.old
until a smoke test confirms the new one is healthy.

Usage:
    python deploy.py [--yes] [--dry-run] [--sync-secrets]

Config is read from deploy.env (copy deploy.env.example and fill it in;
never commit deploy.env). Requires your own SSH access to both GitHub
(for submodules) and the target server -- same as any other git/ssh use
on this machine.

--sync-secrets additionally copies secrets.production.json (repo root,
never committed) to the server as secrets.json, one directory above
APP_DIR -- the exact spot core/backend/core/secrets.py looks for it in
production. Off by default: a routine code deploy shouldn't silently
overwrite a secrets.json that may have been hand-edited directly on the
server. Runs before the release build so a first-time deploy (or one that
adds a new required key) has secrets.json in place before migrate runs.
"""
import argparse
import json
import os
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path, PurePosixPath

ROOT_DIR     = Path(__file__).resolve().parent.parent
DEPLOY_ENV       = ROOT_DIR / "deploy.env"
SECRETS_FILE     = ROOT_DIR / "secrets.production.json"
MODULES_MANIFEST = ROOT_DIR / "modules.json"

# The frontend is built ON THE SERVER (as part of the release activation
# step, using the server's own Node/npm), not locally -- this machine only
# needs git/tar/ssh/curl. core/frontend/dist is excluded defensively in
# case a stale local build is lying around; it should never be shipped.
DEPLOY_EXCLUDES = [
    ".env", "deploy.env", "core/backend/secrets.json", "secrets.production.json",
    "__pycache__", "*.pyc", "*.pyo", ".git",
    "node_modules", "venv", "core/backend/staticfiles", "core/backend/media",
    "core/backend/db.sqlite3", "core/frontend/dist",
    # Never ship private key material. The licensing module's RSA keypair
    # lives at /var/www/beta.peeldev.com/etc/license_*.pem -- outside
    # APP_DIR, like .env, so no copy-forward is needed; a deploy never
    # touches it either way. Excluding it here just guards against ever
    # shipping a *local* keypair that would shadow or confuse things.
    "*.pem",
]

# Directories install.py wires up as symlinks/junctions (core/backend/<app>
# and core/frontend/modules/<app> per module, core/frontend/public). These
# must NEVER be in the payload: on Windows, tar dereferences a junction and
# archives its target's real content under the junction's own path -- so
# core/backend/licensing would get shipped as a real (duplicated) directory
# instead of a link, and once extracted, install.py regen's "already exists"
# idempotency check would skip re-creating the actual symlink, silently
# leaving the module permanently disconnected from modules/ on the server.
# Detected dynamically (mirroring install.py's own _is_dir_link) so this
# doesn't need updating every time a module is added.
_LINK_SCAN_DIRS = ["core/backend", "core/frontend", "core/frontend/modules"]


def _is_dir_link(path: Path) -> bool:
    """Mirrors install.py's _is_dir_link: symlink, or Windows junction."""
    if path.is_symlink():
        return True
    if sys.platform == "win32" and path.is_dir():
        try:
            attrs = os.stat(str(path), follow_symlinks=False).st_file_attributes
            return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
        except OSError:
            pass
    return False


def _module_link_excludes():
    excludes = []
    for rel_dir in _LINK_SCAN_DIRS:
        d = ROOT_DIR / rel_dir
        if not d.is_dir():
            continue
        for entry in d.iterdir():
            if _is_dir_link(entry):
                excludes.append(f"{rel_dir}/{entry.name}")
    return excludes

# core/backend/media holds user uploads (not regeneratable), so it's copied
# forward from the live release into each new one. staticfiles isn't --
# collectstatic rebuilds it fresh every deploy. Production's secrets.json
# lives *outside* APP_DIR entirely (core/backend/core/secrets.py loads it
# from one directory above the repo root), so a deploy never touches it
# either way -- it must be placed there once, out of band (see
# secrets.production.json for this site's values).
MEDIA_REL_PATH = "core/backend/media"


def _die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _run(*cmd, cwd=None, env=None, input_text=None):
    result = subprocess.run(cmd, cwd=cwd, env=env, input=input_text, text=True if input_text else None)
    if result.returncode != 0:
        _die(f"Command failed (exit {result.returncode}): {' '.join(str(c) for c in cmd)}")


def _capture(*cmd, cwd=None):
    result = subprocess.run(cmd, cwd=cwd, capture_output=True, text=True)
    if result.returncode != 0:
        _die(f"Command failed (exit {result.returncode}): {' '.join(str(c) for c in cmd)}\n{result.stderr}")
    return result.stdout.strip()


def _ssh_capture(config, remote_command):
    """Run a short remote command and return (returncode, stdout)."""
    result = subprocess.run(
        [TOOLS["ssh"], f"{config['SERVER_USER']}@{config['SERVER_IP']}", remote_command],
        capture_output=True, text=True,
    )
    return result.returncode, result.stdout.strip()


def _shquote(s):
    return "'" + s.replace("'", "'\\''") + "'"


TOOLS = {}


def _require_tools(*names):
    """Resolve each tool via shutil.which and cache the resolved path in
    TOOLS. Passing a bare name like "npm" to subprocess.run fails on
    Windows (it's actually npm.cmd, and CreateProcess doesn't do PATHEXT
    resolution the way cmd.exe does) -- shutil.which does the same
    resolution install.py's _npm() helper relies on, so every call site
    uses TOOLS[name] instead of a literal string.
    """
    missing = []
    for name in names:
        path = shutil.which(name)
        if path:
            TOOLS[name] = path
        else:
            missing.append(name)
    if missing:
        _die(f"Required tool(s) not found in PATH: {', '.join(missing)}")


def _load_enabled_modules():
    """Mirrors install.py's _load_enabled_modules: this project's module
    allow-list from modules.json (repo root). modules/ is a shared submodule
    holding every module available across all sites -- modules.json says
    which of those this project actually uses, and travels with the tar
    payload so the remote `install.py regen` sees the same list.
    """
    if not MODULES_MANIFEST.exists():
        _die(f'{MODULES_MANIFEST.name} not found at repo root. Create it, e.g. {{"modules": []}}.')
    with MODULES_MANIFEST.open() as f:
        data = json.load(f)
    return list(data.get("modules", []))


def _check_enabled_modules_present():
    """Fail fast locally if modules.json lists a module missing from the
    modules/ submodule checkout -- catches a typo or an un-initialized
    submodule before the tar/ssh round trip, instead of failing remotely
    partway through release activation.
    """
    missing = [
        name for name in _load_enabled_modules()
        if not (ROOT_DIR / "modules" / name).is_dir()
    ]
    if missing:
        _die(f"modules.json lists module(s) not found under modules/: {', '.join(missing)}")


def _load_frontend_sentry_dsn():
    """SENTRY_DSN_FRONTEND lives in secrets.production.json (repo root, never
    committed) alongside SENTRY_DSN_BACKEND, not in deploy.env -- one file
    holds both Sentry DSNs. Returns '' if the file or key isn't present yet
    (e.g. a first deploy before --sync-secrets has ever been run).
    """
    if not SECRETS_FILE.exists():
        return ""
    with SECRETS_FILE.open() as f:
        return json.load(f).get("SENTRY_DSN_FRONTEND", "")


def _load_deploy_env():
    if not DEPLOY_ENV.exists():
        _die(f"{DEPLOY_ENV.name} not found. Copy deploy.env.example to deploy.env and fill it in.")
    config = {}
    for line in DEPLOY_ENV.read_text().splitlines():
        line = line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, _, val = line.partition("=")
        config[key.strip()] = val.strip()

    required = [
        "SERVER_IP", "SERVER_USER", "DOMAIN", "APP_DIR", "SERVICE_NAME",
        "APP_NAME", "RECAPTCHA_SITE_KEY", "GOOGLE_CLIENT_ID",

    ]

    # "STRIPE_PUBLISHABLE_KEY",
    missing = [k for k in required if not config.get(k)]
    if missing:
        _die(f"deploy.env missing required value(s): {', '.join(missing)}")
    return config


def confirm(config, dry_run, sync_secrets_flag, release_version):
    branch = _capture(TOOLS["git"], "rev-parse", "--abbrev-ref", "HEAD", cwd=ROOT_DIR)
    commit = _capture(TOOLS["git"], "rev-parse", "--short", "HEAD", cwd=ROOT_DIR)
    dirty = _capture(TOOLS["git"], "status", "--porcelain", cwd=ROOT_DIR)

    modules = _load_enabled_modules()

    print("--- Deploy summary ---")
    print(f"  Local branch/commit : {branch} @ {commit}{' (dirty)' if dirty else ''}")
    print(f"  Release version     : {release_version}")
    print(f"  Modules             : {', '.join(modules) if modules else '(none)'}")
    print(f"  Target              : {config['SERVER_USER']}@{config['SERVER_IP']}:{config['APP_DIR']}")
    print(f"  Domain              : https://{config['DOMAIN']}")
    print(f"  Service             : {config['SERVICE_NAME']}")
    if sync_secrets_flag:
        remote_path = PurePosixPath(config["APP_DIR"]).parent / "secrets.json"
        print(f"  Secrets sync        : {SECRETS_FILE.name} -> {remote_path}")
    if dirty:
        print("  NOTE: uncommitted local changes will be deployed as-is.")
    if dry_run:
        print("  Mode                : DRY RUN (payload preview only, no remote changes)")
    print()

    answer = input("Proceed with deploy? [y/N] ").strip().lower()
    if answer != "y":
        _die("Aborted.")


def _main_branch_ref():
    """Best-effort resolution of the repo's main branch name, used as the
    version fallback below. Tries the remote's default branch first
    (origin/HEAD), then common local branch names -- this repo's default
    branch is locally named "master" even though "main" is the assumed
    convention elsewhere, so both are checked rather than hardcoding one.
    """
    result = subprocess.run(
        [TOOLS["git"], "symbolic-ref", "--short", "refs/remotes/origin/HEAD"],
        cwd=ROOT_DIR, capture_output=True, text=True,
    )
    if result.returncode == 0 and result.stdout.strip():
        return result.stdout.strip()
    for candidate in ("main", "master"):
        check = subprocess.run(
            [TOOLS["git"], "rev-parse", "--verify", "--quiet", candidate],
            cwd=ROOT_DIR, capture_output=True, text=True,
        )
        if check.returncode == 0:
            return candidate
    _die("Could not determine the main branch (no origin/HEAD, no local main/master).")


def _determine_release_version():
    """Prefer an explicit version tag pointing at the current commit --
    VITE_RELEASE_VERSION should read as a real version when one exists.
    Otherwise fall back to the main branch's SHA rather than whatever's
    currently checked out, since a deploy can be run from a hotfix/feature
    branch but the release version should still track main.
    """
    tag = subprocess.run(
        [TOOLS["git"], "describe", "--tags", "--exact-match", "HEAD"],
        cwd=ROOT_DIR, capture_output=True, text=True,
    )
    if tag.returncode == 0 and tag.stdout.strip():
        return tag.stdout.strip()
    main_ref = _main_branch_ref()
    return _capture(TOOLS["git"], "rev-parse", "--short", main_ref, cwd=ROOT_DIR)


def _check_submodules_committed():
    """Refuse to deploy instead of silently discarding local submodule
    state. `git submodule update` checks out each submodule to the commit
    SHA recorded in the superproject's index -- if a submodule's working
    copy is on a different commit, has uncommitted changes, or has an
    unresolved conflict, `update` would blow that away without asking.
    A deploy should ship exactly what's committed, so require the user to
    commit (or reset) the submodule(s) -- and update the superproject's
    recorded pointer via `git add <path> && git commit` -- themselves.
    """
    print("--- Checking submodule state ---")
    status_out = _capture(TOOLS["git"], "submodule", "status", "--recursive", cwd=ROOT_DIR)

    out_of_sync = []
    conflicted = []
    for line in status_out.splitlines():
        stripped = line.lstrip()
        if not stripped:
            continue
        flag, rest = stripped[0], stripped[1:].split()
        path = rest[1] if len(rest) > 1 else "?"
        if flag == "+":
            out_of_sync.append(path)
        elif flag == "U":
            conflicted.append(path)
        # '-' (uninitialized) and ' ' (in sync) are both fine to proceed with.

    foreach_out = _capture(
        TOOLS["git"], "submodule", "foreach", "--recursive", "git status --porcelain",
        cwd=ROOT_DIR,
    )
    dirty = []
    current = None
    for line in foreach_out.splitlines():
        m = re.match(r"Entering '(.+)'", line)
        if m:
            current = m.group(1)
            continue
        if line.strip() and current and current not in dirty:
            dirty.append(current)

    problems = []
    if out_of_sync:
        problems.append(
            "checked out commit differs from what's committed in the superproject: "
            + ", ".join(out_of_sync)
        )
    if dirty:
        problems.append("uncommitted changes: " + ", ".join(dirty))
    if conflicted:
        problems.append("unresolved merge conflicts: " + ", ".join(conflicted))

    if problems:
        _die(
            "Submodule(s) are not in a clean, committed state -- refusing to deploy "
            "(this would otherwise silently check them out to the last committed "
            "reference, discarding the local state):\n  "
            + "\n  ".join(problems)
            + "\nCommit or reset the submodule(s), then `git add <path> && git commit` "
            "in the superproject to record the pointer, before deploying."
        )
    print("  All submodules clean and in sync.")


def sync_submodules():
    _check_submodules_committed()
    print("--- Syncing submodules ---")
    _run(TOOLS["git"], "submodule", "update", "--init", "--recursive", cwd=ROOT_DIR)


def sync_secrets(config, dry_run):
    """Copy secrets.production.json to the server as secrets.json, one
    directory above APP_DIR. Never part of the deploy payload itself
    (excluded in DEPLOY_EXCLUDES) -- pushed here as a separate, explicit
    step, and locked down to the app user afterward since it holds live
    credentials.
    """
    if not SECRETS_FILE.exists():
        _die(f"{SECRETS_FILE.name} not found at repo root -- nothing to sync.")

    remote_path = str(PurePosixPath(config["APP_DIR"]).parent / "secrets.json")
    target = f"{config['SERVER_USER']}@{config['SERVER_IP']}:{remote_path}"
    print(f"--- Syncing secrets to {target} ---")

    if dry_run:
        print(f"  (dry run) Would copy {SECRETS_FILE.name} -> {target}")
        return

    _run(TOOLS["scp"], str(SECRETS_FILE), target)
    _run(TOOLS["ssh"], f"{config['SERVER_USER']}@{config['SERVER_IP']}",
         f"chown www-data:www-data {_shquote(remote_path)} && chmod 600 {_shquote(remote_path)}")
    print("  Done.")


def _tar_command(mode):
    """mode is a create-and-file flag combo like '-cf' or '-czf'. The
    archive always goes to stdout ('-', which must immediately follow the
    -f flag) and '.' (relative to ROOT_DIR) is always the payload."""
    cmd = [TOOLS["tar"], "-C", str(ROOT_DIR)]
    for pattern in DEPLOY_EXCLUDES + _module_link_excludes():
        cmd.append(f"--exclude={pattern}")
    cmd += [mode, "-", "."]
    return cmd


def preview_payload():
    """Dry-run: list what the archive would contain (local excludes only --
    unlike rsync -n, this doesn't compare against remote state)."""
    print("--- Files that would be sent (dry run, no remote comparison) ---")
    result = subprocess.run(_tar_command("-cf"), cwd=ROOT_DIR, capture_output=True)
    if result.returncode != 0:
        _die(f"tar failed building preview: {result.stderr.decode(errors='replace')}")
    listing = subprocess.run([TOOLS["tar"], "-tf", "-"], input=result.stdout, capture_output=True)
    lines = listing.stdout.decode(errors="replace").splitlines()
    print(f"  {len(lines)} entries, e.g.:")
    for line in lines[:20]:
        print(f"    {line}")
    if len(lines) > 20:
        print(f"    ... and {len(lines) - 20} more")


def deploy_release(config, release_version):
    """Build a full new release next to the live one, activate it there,
    and only swap it into place if activation succeeds. Never modifies
    APP_DIR in place -- every mutating step targets APP_DIR.new until the
    final two `mv`s. All destructive `rm -rf` targets use ${VAR:?} guards
    so an empty/unset variable aborts instead of resolving to something
    catastrophic.
    """
    print("--- Building and swapping in new release ---")
    app_dir = config["APP_DIR"]
    service = config["SERVICE_NAME"]

    remote_script = f"""
set -e
APP_DIR={app_dir}
NEW_DIR="${{APP_DIR}}.new"
OLD_DIR="${{APP_DIR}}.old"

if [ -e "$OLD_DIR" ]; then
  echo "ERROR: $OLD_DIR already exists -- a previous deploy wasn't cleaned up." >&2
  echo "Confirm $APP_DIR is healthy, then either roll back manually or remove $OLD_DIR before deploying again." >&2
  exit 1
fi

rm -rf "${{NEW_DIR:?}}"
mkdir -p "$NEW_DIR"
tar xzf - -C "$NEW_DIR"

if [ -d "$APP_DIR/{MEDIA_REL_PATH}" ]; then
  mkdir -p "$(dirname "$NEW_DIR/{MEDIA_REL_PATH}")"
  cp -a "$APP_DIR/{MEDIA_REL_PATH}" "$NEW_DIR/{MEDIA_REL_PATH}"
fi

echo "--- Regenerating module manifests (in staging dir) ---"
cd "$NEW_DIR"
source ../venv/bin/activate
python core/install.py regen

echo "--- Installing Python dependencies ---"
pip install -r core/backend/requirements.txt --quiet

echo "--- Building frontend ---"
cd core/frontend
npm ci --legacy-peer-deps
NODE_ENV=production \\
VITE_ENV=production \\
VITE_API_URL="https://{config['DOMAIN']}" \\
VITE_WS_URL="wss://{config['DOMAIN']}" \\
VITE_RECAPTCHA_SITE_KEY="{config['RECAPTCHA_SITE_KEY']}" \\
VITE_GOOGLE_CLIENT_ID="{config['GOOGLE_CLIENT_ID']}" \\
VITE_STRIPE_PUBLISHABLE_KEY="{config.get('STRIPE_PUBLISHABLE_KEY', '')}" \\
VITE_RELEASE_VERSION="{release_version}" \\
VITE_APP_NAME="{config['APP_NAME']}" \\
VITE_APP_ICON="{config.get('APP_ICON', '')}" \\
VITE_NAV_ICON="{config.get('NAV_ICON', '')}" \\
npm run build
cd ../..

echo "--- Running migrations ---"
DJANGO_SETTINGS_MODULE=core.settings.production \\
  python core/backend/manage.py migrate --no-input

echo "--- Collecting static files ---"
DJANGO_SETTINGS_MODULE=core.settings.production \\
  python core/backend/manage.py collectstatic --no-input

echo "--- Setting permissions ---"
chown -R www-data:www-data "$NEW_DIR"

echo "===SWAP-START==="
if [ -d "$APP_DIR" ]; then
  mv "$APP_DIR" "$OLD_DIR"
fi
mv "$NEW_DIR" "$APP_DIR"
echo "===SWAP-DONE==="

echo "--- Restarting {service} ---"
systemctl restart {service}

echo "--- Deploy complete (previous release kept at $OLD_DIR pending smoke test) ---"
"""
    tar_stream = subprocess.run(_tar_command("-czf"), cwd=ROOT_DIR, capture_output=True)
    if tar_stream.returncode != 0:
        _die(f"tar failed building payload: {tar_stream.stderr.decode(errors='replace')}")

    # Stdin is reserved for the tar stream, so the remote script travels as
    # a command-line argument instead (ssh joins argv after user@host into
    # one string and hands it to the remote shell).
    result = subprocess.run(
        [TOOLS["ssh"], f"{config['SERVER_USER']}@{config['SERVER_IP']}",
         f"bash -c {_shquote(remote_script)}"],
        input=tar_stream.stdout,
    )
    if result.returncode != 0:
        # Ask the server whether the swap actually happened, so the error
        # message is accurate about whether the live site was touched.
        rc, out = _ssh_capture(config, f'[ -d "{app_dir}.old" ] && echo swapped || echo not-swapped')
        if rc == 0 and out == "swapped":
            _die(
                f"Deploy failed AFTER the swap (exit {result.returncode}). "
                f"{app_dir} now holds the new release; the previous one is at {app_dir}.old. "
                f"Investigate before running another deploy."
            )
        else:
            _die(
                f"Deploy failed before the swap (exit {result.returncode}). "
                f"Live site at {app_dir} was not modified."
            )


def cleanup_old_release(config):
    print("--- Cleaning up previous release ---")
    app_dir = config["APP_DIR"]
    remote_script = f'OLD_DIR="{app_dir}.old"; rm -rf "${{OLD_DIR:?}}"'
    # ssh re-joins argv after the hostname with plain spaces before handing
    # it to the remote shell -- passing "bash", "-c", script as separate
    # argv elements lets ssh's rejoining split the script back apart at
    # its internal spaces/`;`. Pass the whole thing as one pre-quoted
    # string instead, same as deploy_release().
    _run(TOOLS["ssh"], f"{config['SERVER_USER']}@{config['SERVER_IP']}",
         f"bash -c {_shquote(remote_script)}")


def rollback(config):
    print("--- Rolling back to previous release ---")
    app_dir = config["APP_DIR"]
    service = config["SERVICE_NAME"]
    remote_script = f"""
set -e
APP_DIR={app_dir}
OLD_DIR="${{APP_DIR}}.old"
FAILED_DIR="${{APP_DIR}}.failed"

if [ ! -d "$OLD_DIR" ]; then
  echo "ERROR: $OLD_DIR not found -- nothing to roll back to." >&2
  exit 1
fi

rm -rf "${{FAILED_DIR:?}}"
mv "$APP_DIR" "$FAILED_DIR"
mv "$OLD_DIR" "$APP_DIR"
systemctl restart {service}
echo "--- Rolled back. The failed release is kept at $FAILED_DIR for inspection. ---"
"""
    _run(TOOLS["ssh"], f"{config['SERVER_USER']}@{config['SERVER_IP']}", "bash", "-s", input_text=remote_script)


def smoke_test(config):
    print("--- Smoke test ---")
    time.sleep(5)
    result = subprocess.run(
        [TOOLS["curl"], "--fail", "--silent", "--output", os.devnull,
         "--write-out", "HTTP %{http_code}", f"https://{config['DOMAIN']}"],
        capture_output=True, text=True,
    )
    if result.returncode != 0:
        print(f"Smoke test FAILED: {result.stdout} {result.stderr}", file=sys.stderr)
        return False
    print(f"{result.stdout} — site is up")
    return True


def main():
    parser = argparse.ArgumentParser(description="Deploy the local repo to production.")
    parser.add_argument("--yes", "-y", action="store_true", help="Skip confirmation prompts (also auto-rolls-back on a failed smoke test).")
    parser.add_argument("--dry-run", action="store_true", help="Preview the deploy payload only; skip pushing, remote activation, and smoke test.")
    parser.add_argument("--sync-secrets", action="store_true", help="Also copy secrets.production.json to the server as secrets.json, one directory above APP_DIR. Off by default -- see module docstring.")
    args = parser.parse_args()

    required_tools = ["git", "tar", "ssh", "curl"]
    if args.sync_secrets:
        required_tools.append("scp")
    _require_tools(*required_tools)
    config = _load_deploy_env()
    config["SENTRY_DSN_FRONTEND"] = _load_frontend_sentry_dsn()
    _check_enabled_modules_present()

    release_version = _determine_release_version()
    if not args.yes:
        confirm(config, args.dry_run, args.sync_secrets, release_version)

    sync_submodules()

    if args.sync_secrets:
        sync_secrets(config, args.dry_run)

    if args.dry_run:
        preview_payload()
        print("Dry run complete -- no remote changes made.")
        return

    deploy_release(config, release_version)

    if smoke_test(config):
        cleanup_old_release(config)
        print("Deploy complete.")
        return

    app_dir = config["APP_DIR"]
    print(f"Previous release preserved at {app_dir}.old.", file=sys.stderr)
    if args.yes:
        print("--yes was passed: rolling back automatically.", file=sys.stderr)
        do_rollback = True
    else:
        answer = input("Roll back to the previous release now? [y/N] ").strip().lower()
        do_rollback = answer == "y"

    if do_rollback:
        rollback(config)
    else:
        print("Left as-is. To roll back manually:", file=sys.stderr)
        print(
            f'  ssh {config["SERVER_USER"]}@{config["SERVER_IP"]} '
            f'"mv {app_dir} {app_dir}.failed && mv {app_dir}.old {app_dir} '
            f'&& systemctl restart {config["SERVICE_NAME"]}"',
            file=sys.stderr,
        )
    sys.exit(1)


if __name__ == "__main__":
    main()
