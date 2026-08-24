#!/usr/bin/env python3
"""
install.py -- module lifecycle manager
Usage:
    python install.py add <module_name>
    python install.py remove <module_name>
    python install.py regen

Must be run with the project venv activated (same requirement as manage.py).
"""
import json
import os
import re
import shutil
import subprocess
import sys
from pathlib import Path

ROOT_DIR         = Path(__file__).resolve().parent
MODULES_DIR      = ROOT_DIR / "modules"
SITE_DIR         = ROOT_DIR / "site"
BACKEND_DIR      = ROOT_DIR / "core" / "backend"
FRONTEND_DIR     = ROOT_DIR / "core" / "frontend"
MANIFEST         = FRONTEND_DIR / "src" / "modules.js"
ENABLED_MANIFEST = FRONTEND_DIR / "src" / "enabledModules.js"
MANAGE_PY        = BACKEND_DIR / "manage.py"
MODULES_MANIFEST = ROOT_DIR / "modules.json"


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _die(msg):
    print(f"ERROR: {msg}", file=sys.stderr)
    sys.exit(1)


def _run(*cmd, cwd=None):
    """Run a subprocess command; exit with a clear message on failure."""
    result = subprocess.run(cmd, cwd=cwd)
    if result.returncode != 0:
        _die(f"Command failed (exit {result.returncode}): {' '.join(str(c) for c in cmd)}")


def _link_dir(link: Path, target: Path):
    """Create a directory symlink; fall back to a Windows junction on privilege error."""
    try:
        link.symlink_to(target)
    except OSError as exc:
        if sys.platform != "win32" or getattr(exc, "winerror", None) != 1314:
            raise
        abs_target = (link.parent / target).resolve()
        result = subprocess.run(
            ["cmd", "/c", "mklink", "/J", str(link), str(abs_target)],
            capture_output=True, text=True,
        )
        if result.returncode != 0:
            _die(f"Failed to create junction: {result.stderr.strip()}")


def _is_dir_link(path: Path) -> bool:
    """Return True if path is a symlink or a Windows junction (reparse point)."""
    if path.is_symlink():
        return True
    if sys.platform == "win32" and path.is_dir():
        try:
            attrs = os.stat(str(path), follow_symlinks=False).st_file_attributes
            return bool(attrs & 0x400)  # FILE_ATTRIBUTE_REPARSE_POINT
        except OSError:
            pass
    return False


def _unlink_dir(path: Path):
    """Remove a symlink or Windows junction without touching the target contents."""
    if path.is_symlink():
        path.unlink()
    elif sys.platform == "win32":
        os.rmdir(str(path))


def _npm():
    """Return the npm executable path. Handles npm.cmd on Windows."""
    npm = shutil.which("npm")
    if not npm:
        _die("npm not found in PATH. Install Node.js and ensure npm is on PATH.")
    return npm


def _load_module_json(module_dir):
    """Load and return the parsed module.json for a module directory."""
    path = module_dir / "module.json"
    assert path.exists(), f"module.json missing in {module_dir}"
    with path.open() as f:
        return json.load(f)


def _load_enabled_modules():
    """Return this project's module allow-list from modules.json (repo root).

    modules/ is a shared submodule holding every module available across all
    sites built on this template. modules.json says which of those this
    particular project actually uses -- a module present under modules/ but
    not listed here is treated as not installed: skipped by regen, add's
    dependency checks, generate_manifest, and generate_installed_modules.
    """
    if not MODULES_MANIFEST.exists():
        _die(f'{MODULES_MANIFEST.name} not found at repo root. Create it, e.g. {{"modules": []}}.')
    with MODULES_MANIFEST.open() as f:
        data = json.load(f)
    return list(data.get("modules", []))


def _save_enabled_modules(names):
    MODULES_MANIFEST.write_text(json.dumps({"modules": names}, indent=2) + "\n")


def _topo_sort(graph):
    """Topological sort of module names so dependencies precede dependents.

    graph: dict mapping module_name -> list of required module names.
    Raises ValueError on circular dependency.
    """
    from collections import deque

    installed = set(graph)
    in_degree = {name: 0 for name in installed}
    dependents = {name: [] for name in installed}

    for name, requires in graph.items():
        for req in requires:
            if req in installed:
                in_degree[name] += 1
                dependents[req].append(name)

    queue = deque(sorted(n for n in installed if in_degree[n] == 0))
    result = []
    while queue:
        node = queue.popleft()
        result.append(node)
        for dep in sorted(dependents[node]):
            in_degree[dep] -= 1
            if in_degree[dep] == 0:
                queue.append(dep)

    if len(result) != len(installed):
        cycle = sorted(n for n in installed if n not in result)
        raise ValueError(f"Circular dependency detected among modules: {cycle}")

    return result


# ---------------------------------------------------------------------------
# Dict deep-merge
# ---------------------------------------------------------------------------

def _deep_merge(base, override):
    """Recursively merge override into base in-place. Dicts recurse; lists extend; scalars overwrite."""
    for key, val in override.items():
        if key in base and isinstance(base[key], dict) and isinstance(val, dict):
            _deep_merge(base[key], val)
        elif key in base and isinstance(base[key], list) and isinstance(val, list):
            base[key].extend(val)
        else:
            base[key] = val


# ---------------------------------------------------------------------------
# Route collision detection
# ---------------------------------------------------------------------------

_PATH_RE = re.compile(r"""path\s*:\s*['"`]([^'"`]+)['"`]""")
_PARAM_RE = re.compile(r":[^/]+")


def _extract_paths(module_dir):
    """Return list of path strings from a module's routes.(jsx|js) file."""
    for name in ("routes.jsx", "routes.js"):
        f = module_dir / "frontend" / "src" / name
        if f.exists():
            return _PATH_RE.findall(f.read_text(encoding="utf-8", errors="replace"))
    return []


def _has_site_content():
    """Return True if site/frontend/src/index.js(x) exists — site acts as a pseudo-module."""
    return (SITE_DIR / "frontend" / "src" / "index.js").exists() or \
           (SITE_DIR / "frontend" / "src" / "index.jsx").exists()


def _check_route_collisions(exclude=None):
    """Abort on exact route duplicates; warn on parameterized structural conflicts."""
    enabled = set(_load_enabled_modules())
    exact = {}          # path -> module_name
    parameterized = {}  # normalized -> [(original_path, module_name)]

    sources = [
        (module_dir.name, module_dir)
        for module_dir in sorted(MODULES_DIR.iterdir())
        if module_dir.is_dir() and module_dir.name != exclude and module_dir.name in enabled
        and (module_dir / "module.json").exists()
    ]
    if _has_site_content():
        sources.append(("site", SITE_DIR))

    for name, module_dir in sources:
        for path in dict.fromkeys(_extract_paths(module_dir)):
            if ":" in path or "*" in path:
                normalized = _PARAM_RE.sub(":param", path)
                parameterized.setdefault(normalized, []).append((path, name))
            else:
                if path in exact:
                    _die(
                        f"Route collision: '{path}' is registered by both "
                        f"'{exact[path]}' and '{name}'."
                    )
                exact[path] = name

    for normalized, entries in parameterized.items():
        if len(entries) > 1:
            details = ", ".join(f"'{m}' ({p})" for p, m in entries)
            print(
                f"WARNING: Parameterized route conflict — '{normalized}' "
                f"matched by {details}",
                file=sys.stderr,
            )


# ---------------------------------------------------------------------------
# Manifest generation
# ---------------------------------------------------------------------------

def generate_manifest(exclude=None):
    """Rewrite core/frontend/src/modules.js from the current modules/ state.

    exclude: module name to omit from the manifest (used during 'remove'
             before the directory has been deleted).

    Uses `import * as <name>Module` so that optional exports (providers,
    navItems) can be absent from a module without causing a static import
    error. Missing exports resolve to undefined and are guarded with ?? [].

    site/frontend/src/index.js (if present) is wired in first, ahead of
    every installed module, as a pseudo-module — same export shape as a
    real module (routes, navItems, homeSections, etc.), but loaded via a
    plain relative import instead of the @modules/<name> workspace alias,
    since site/ is this deployment's own content, not an npm package.
    """
    _check_route_collisions(exclude=exclude)
    enabled = set(_load_enabled_modules())

    imports, route_items, nav_items, provider_items, navbar_end_items, admin_card_items, user_section_items, home_section_items = [], [], [], [], [], [], [], []

    if _has_site_content():
        entry = "index.js" if (SITE_DIR / "frontend" / "src" / "index.js").exists() else "index.jsx"
        imports.append(f"import * as siteModule from '../../../site/frontend/src/{entry}';")
        route_items.append("  ...(siteModule.routes ?? []),")
        nav_items.append("  ...(siteModule.navItems ?? []),")
        provider_items.append("  ...(siteModule.providers ?? []),")
        navbar_end_items.append("  ...(siteModule.navbarEnd ?? []),")
        admin_card_items.append("  ...(siteModule.adminCards ?? []),")
        user_section_items.append("  ...(siteModule.userSections ?? []),")
        home_section_items.append("  ...(siteModule.homeSections ?? []),")

    for module_dir in sorted(MODULES_DIR.iterdir()):
        if not module_dir.is_dir():
            continue
        name = module_dir.name
        if name == exclude or name not in enabled:
            continue
        if not (module_dir / "module.json").exists():
            continue
        imports.append(f"import * as {name}Module from '@modules/{name}';")
        route_items.append(f"  ...({name}Module.routes ?? []),")
        nav_items.append(f"  ...({name}Module.navItems ?? []),")
        provider_items.append(f"  ...({name}Module.providers ?? []),")
        navbar_end_items.append(f"  ...({name}Module.navbarEnd ?? []),")
        admin_card_items.append(f"  ...({name}Module.adminCards ?? []),")
        user_section_items.append(f"  ...({name}Module.userSections ?? []),")
        home_section_items.append(f"  ...({name}Module.homeSections ?? []),")

    lines = ["// Generated by install.py -- do not edit by hand."]
    if imports:
        lines.append("")
        lines.extend(imports)
    lines += [
        "",
        "export const moduleRoutes = [",
        *route_items,
        "];",
        "",
        "export const moduleNavItems = [",
        *nav_items,
        "];",
        "",
        "export const moduleProviders = [",
        *provider_items,
        "];",
        "",
        "export const moduleNavbarEnd = [",
        *navbar_end_items,
        "];",
        "",
        "export const moduleAdminCards = [",
        *admin_card_items,
        "];",
        "",
        "export const moduleUserSections = [",
        *user_section_items,
        "];",
        "",
        "export const moduleHomeSections = [",
        *home_section_items,
        "];",
        "",  # trailing newline
    ]

    MANIFEST.write_text("\n".join(lines))
    print(f"  + Regenerated {MANIFEST.relative_to(ROOT_DIR)}")

    # Plain data manifest of enabled module names, importable from *inside* a
    # module's own frontend code (e.g. to check whether some other optional
    # module is active) without importing modules.js itself, which pulls in
    # every module's code and would create an import cycle for a module that
    # imports it back.
    active = sorted(enabled - {exclude} if exclude else enabled)
    ENABLED_MANIFEST.write_text(
        "// Generated by install.py -- do not edit by hand.\n"
        "\n"
        f"export const ENABLED_MODULES = {active!r};\n"
    )
    print(f"  + Regenerated {ENABLED_MANIFEST.relative_to(ROOT_DIR)}")


# ---------------------------------------------------------------------------
# installed_modules.py generation
# ---------------------------------------------------------------------------

def generate_installed_modules(exclude=None):
    """Write backend/core/installed_modules.py from the current modules/ state.

    exclude: module name to omit (used during 'remove').
    """
    enabled = set(_load_enabled_modules())
    graph = {}
    extra_apps_map = {}
    extra_mw_map = {}
    settings_map = {}

    for entry in sorted(MODULES_DIR.iterdir()):
        if not entry.is_dir():
            continue
        if not (entry / "module.json").exists():
            continue
        name = entry.name
        if name == exclude or name not in enabled:
            continue

        data = _load_module_json(entry)
        graph[name] = data.get("requires", [])
        extra_apps_map[name] = data.get("django_apps", [])
        extra_mw_map[name] = data.get("middleware", [])
        settings_map[name] = data.get("settings_defaults", {})

    ordered = _topo_sort(graph)

    seen_apps = set()
    extra_apps = []
    for name in ordered:
        for app in extra_apps_map.get(name, []):
            if app not in seen_apps:
                seen_apps.add(app)
                extra_apps.append(app)

    seen_mw = set()
    extra_middleware = []
    for name in ordered:
        for mw in extra_mw_map.get(name, []):
            if mw not in seen_mw:
                seen_mw.add(mw)
                extra_middleware.append(mw)

    settings_defaults = {}
    for name in ordered:
        for key, value in settings_map.get(name, {}).items():
            if key not in settings_defaults:
                settings_defaults[key] = value
            elif isinstance(settings_defaults[key], dict) and isinstance(value, dict):
                _deep_merge(settings_defaults[key], value)
            elif isinstance(settings_defaults[key], list) and isinstance(value, list):
                settings_defaults[key].extend(value)
            else:
                if settings_defaults[key] != value:
                    print(
                        f"WARNING: Module '{name}' overrides scalar setting '{key}' "
                        f"(last-installed wins).",
                        file=sys.stderr,
                    )
                settings_defaults[key] = value

    out = BACKEND_DIR / "core" / "installed_modules.py"
    lines = [
        "# Generated by install.py — do not edit by hand.",
        "from core.secrets import SECRETS",
        f"INSTALLED_MODULE_APPS   = {ordered!r}",
        f"MODULE_EXTRA_APPS       = {extra_apps!r}",
        f"MODULE_EXTRA_MIDDLEWARE = {extra_middleware!r}",
        f"MODULE_SETTINGS         = {_render_settings_dict(settings_defaults)}",
        "",
    ]
    out.write_text("\n".join(lines))
    print(f"  + Regenerated {out.relative_to(ROOT_DIR)}")


# ---------------------------------------------------------------------------
# Settings rendering
# ---------------------------------------------------------------------------

def _render_settings_dict(d, indent=4):
    """Render a settings dict as Python source.

    Empty-string values become SECRETS.get('KEY', '') so that the generated
    file reads from secrets.json (see core/backend/core/secrets.py) rather
    than hardcoding blanks. All other values are rendered as literals.
    """
    pad = ' ' * indent
    lines = ['{']
    for key, val in d.items():
        if val == '':
            lines.append(f"{pad}{key!r}: SECRETS.get({key!r}, ''),")
        else:
            lines.append(f"{pad}{key!r}: {val!r},")
    lines.append('}')
    return '\n'.join(lines)


# ---------------------------------------------------------------------------
# Module wiring (shared by add and regen)
# ---------------------------------------------------------------------------

def _wire_module(name, manifest=None):
    """Install Python packages and create the backend symlink for one module.

    Idempotent — safe to call on an already-wired module.
    """
    module_dir = MODULES_DIR / name
    if manifest is None:
        manifest = _load_module_json(module_dir)

    # Python dependencies — prefer pip_packages in module.json, fall back to requirements.txt
    pip_packages = manifest.get("pip_packages", [])
    if pip_packages:
        print(f"  [{name}] Installing Python packages...")
        _run(sys.executable, "-m", "pip", "install", *pip_packages, "-q")
    else:
        req_file = module_dir / "backend" / "requirements.txt"
        if req_file.exists() and req_file.stat().st_size > 0:
            print(f"  [{name}] Installing Python packages...")
            _run(sys.executable, "-m", "pip", "install", "-r", str(req_file), "-q")

    # Backend symlink: core/backend/<name> -> ../../modules/<name>/backend/<name>
    app_src = MODULES_DIR / name / "backend" / name
    if not app_src.exists():
        _die(f"Django app directory not found: {app_src}")
    backend_link = BACKEND_DIR / name
    if not backend_link.exists():
        target = Path("../../modules") / name / "backend" / name
        _link_dir(backend_link, target)
        print(f"  [{name}] Linked core/backend/{name} -> {target}")

    # Frontend symlink: core/frontend/modules/<name> -> ../../../modules/<name>/frontend
    #
    # package.json's npm workspaces glob points at core/frontend/modules/*
    # rather than directly at ../../modules/*/frontend -- modules/ is a
    # shared submodule holding every module across all sites, and globbing
    # it directly would register every module physically present there as
    # an npm workspace regardless of modules.json, leaving package-lock.json
    # perpetually out of sync with whatever the shared submodule happens to
    # contain. Symlinking only the enabled modules in here keeps the
    # workspace set -- and therefore the lock file -- limited to what
    # modules.json actually lists.
    frontend_src = MODULES_DIR / name / "frontend"
    if frontend_src.exists():
        frontend_link_dir = FRONTEND_DIR / "modules"
        frontend_link_dir.mkdir(parents=True, exist_ok=True)
        frontend_link = frontend_link_dir / name
        if not frontend_link.exists():
            target = Path("../../../modules") / name / "frontend"
            _link_dir(frontend_link, target)
            print(f"  [{name}] Linked core/frontend/modules/{name} -> {target}")


def _wire_site():
    """Link core/frontend/public -> ../../site/frontend/public.

    Keeps this deployment's branding assets (favicon, logos) out of core's
    repo while still serving them from Vite's public dir. Idempotent.
    """
    public_link = FRONTEND_DIR / "public"
    if _is_dir_link(public_link):
        return
    if public_link.exists():
        _die(f"{public_link} exists and is not a link — remove it manually first.")
    site_public = SITE_DIR / "frontend" / "public"
    site_public.mkdir(parents=True, exist_ok=True)
    _link_dir(public_link, Path("../../site/frontend/public"))
    print(f"  + Linked core/frontend/public -> site/frontend/public")


# ---------------------------------------------------------------------------
# Add
# ---------------------------------------------------------------------------

def add(name):
    module_dir = MODULES_DIR / name
    if not module_dir.is_dir():
        _die(f"modules/{name} not found.")
    if not (module_dir / "module.json").exists():
        _die(f"modules/{name}/module.json missing.")

    manifest = _load_module_json(module_dir)
    print(f"Installing module: {name}")

    enabled = _load_enabled_modules()

    # Verify declared dependencies are enabled for this project
    for dep in manifest.get("requires", []):
        if dep not in enabled:
            _die(f"'{name}' requires module '{dep}' which is not enabled -- add it to {MODULES_MANIFEST.name} first.")
        print(f"  + Dependency '{dep}' present")

    if name not in enabled:
        enabled.append(name)
        _save_enabled_modules(enabled)
        print(f"  + Added '{name}' to {MODULES_MANIFEST.name}")

    _wire_module(name, manifest)

    # Regenerate manifests
    generate_manifest()
    generate_installed_modules()

    # npm install (picks up new workspace entry via symlink)
    # --legacy-peer-deps: some packages (e.g. @stripe/react-stripe-js) declare
    # peer deps against React ≤18 even though they work fine with React 19.
    print("  Installing frontend packages...")
    _run(_npm(), "install", "--legacy-peer-deps", cwd=FRONTEND_DIR)

    # Django migrations
    print("  Running migrations...")
    _run(sys.executable, str(MANAGE_PY), "migrate")

    # Remind about any manual settings that can't be automated
    settings_doc = module_dir / "backend" / manifest.get("django_app", name) / "module_settings.py"
    if settings_doc.exists():
        print(f"\nNOTE: {settings_doc.relative_to(ROOT_DIR)} contains additional settings")
        print("  Review that file and merge any required values into core/backend/core/settings/.")

    print(f"\nDone. Module '{name}' installed.")


# ---------------------------------------------------------------------------
# Remove
# ---------------------------------------------------------------------------

def remove(name, run_migrations=False):
    module_dir = MODULES_DIR / name
    if not module_dir.is_dir():
        _die(f"modules/{name} not found.")

    print(f"Removing module: {name}")

    enabled = _load_enabled_modules()

    # Block removal if another enabled module depends on this one
    for other_name in enabled:
        if other_name == name:
            continue
        other_dir = MODULES_DIR / other_name
        if not (other_dir / "module.json").exists():
            continue
        other = _load_module_json(other_dir)
        if name in other.get("requires", []):
            _die(f"Cannot remove '{name}' -- module '{other_name}' depends on it.")

    # Determine app label and whether there are real migrations to roll back
    module_json_path = module_dir / "module.json"
    manifest = _load_module_json(module_dir) if module_json_path.exists() else {}
    app_label = manifest.get("django_app", name)
    migrations_dir = module_dir / "backend" / app_label / "migrations"
    has_migrations = migrations_dir.is_dir() and any(
        f.suffix == ".py" and f.name != "__init__.py"
        for f in migrations_dir.iterdir()
        if f.is_file()
    )

    # Migrate zero BEFORE manifests are regenerated — app must still be in INSTALLED_APPS
    if has_migrations and run_migrations:
        print(f"  Rolling back migrations for '{app_label}'...")
        _run(sys.executable, str(MANAGE_PY), "migrate", app_label, "zero")

    # Regenerate manifests excluding this module
    generate_manifest(exclude=name)
    generate_installed_modules(exclude=name)

    # Remove backend symlink/junction
    backend_link = BACKEND_DIR / name
    if _is_dir_link(backend_link):
        _unlink_dir(backend_link)
        print(f"  - Removed link core/backend/{name}")

    # Remove frontend symlink/junction
    frontend_link = FRONTEND_DIR / "modules" / name
    if _is_dir_link(frontend_link):
        _unlink_dir(frontend_link)
        print(f"  - Removed link core/frontend/modules/{name}")

    if name in enabled:
        enabled.remove(name)
        _save_enabled_modules(enabled)
        print(f"  - Removed '{name}' from {MODULES_MANIFEST.name}")

    print(f"Done. Module '{name}' removed.")
    if not has_migrations:
        print(f"  (No migrations for '{app_label}' — nothing to roll back)")
    elif not run_migrations:
        print(f"NOTE: Roll back migrations before deleting the module directory:")
        print(f"      python core/backend/manage.py migrate {app_label} zero")
        print(f"      (Or re-run: python install.py remove --run-migrations {name})")
    print(f"NOTE: Delete modules/{name} (and its git submodule entry) when ready.")


# ---------------------------------------------------------------------------
# Regen
# ---------------------------------------------------------------------------

def regen():
    """Wire this project's enabled modules (symlinks + pip packages) and
    regenerate manifests.

    Runs the same setup as 'add' for every module listed in modules.json, in
    dependency order, making it safe to use as the sole deploy-time module
    activation step. Modules present under modules/ but not listed in
    modules.json are ignored entirely -- modules/ is a shared submodule
    holding every module available across all sites built on this template.
    """
    enabled = _load_enabled_modules()

    # Collect enabled modules and resolve dependency order
    graph = {}
    manifests = {}
    for module_dir in sorted(MODULES_DIR.iterdir()):
        if not module_dir.is_dir() or not (module_dir / "module.json").exists():
            continue
        if module_dir.name not in enabled:
            continue
        data = _load_module_json(module_dir)
        graph[module_dir.name] = data.get("requires", [])
        manifests[module_dir.name] = data

    missing = [name for name in enabled if name not in graph]
    if missing:
        _die(f"{MODULES_MANIFEST.name} lists module(s) not found under modules/: {', '.join(missing)}")

    for name, requires in graph.items():
        unmet = [r for r in requires if r not in graph]
        if unmet:
            _die(f"Module '{name}' requires {unmet}, which is not enabled in {MODULES_MANIFEST.name}.")

    ordered = _topo_sort(graph)

    print("Wiring site...")
    _wire_site()

    print("Wiring modules...")
    for name in ordered:
        _wire_module(name, manifests[name])

    print("Regenerating manifests...")
    generate_manifest()
    generate_installed_modules()
    print("Done.")


# ---------------------------------------------------------------------------
# Entrypoint
# ---------------------------------------------------------------------------

COMMANDS = {"add": add, "remove": remove, "regen": regen}


def main():
    if len(sys.argv) < 2 or sys.argv[1] not in COMMANDS:
        print("Usage: python install.py add|remove <module_name>", file=sys.stderr)
        print("       python install.py remove [--run-migrations] <module_name>", file=sys.stderr)
        print("       python install.py regen", file=sys.stderr)
        sys.exit(1)
    cmd = sys.argv[1]
    if cmd == "regen":
        regen()
    elif cmd == "remove":
        rest = sys.argv[2:]
        flags = [a for a in rest if a.startswith("--")]
        positional = [a for a in rest if not a.startswith("--")]
        unknown = [f for f in flags if f != "--run-migrations"]
        if unknown:
            _die(f"Unknown flag(s) for remove: {' '.join(unknown)}")
        if len(positional) != 1:
            print("Usage: python install.py remove [--run-migrations] <module_name>", file=sys.stderr)
            sys.exit(1)
        remove(positional[0], run_migrations="--run-migrations" in flags)
    elif len(sys.argv) != 3:
        print(f"Usage: python install.py {cmd} <module_name>", file=sys.stderr)
        sys.exit(1)
    else:
        COMMANDS[cmd](sys.argv[2])


if __name__ == "__main__":
    main()
