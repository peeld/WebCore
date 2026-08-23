"""
secrets.py — loads secrets.json and exposes it as SECRETS.

This file is committed (it's part of core, reusable across sites). The JSON
data file it reads is never committed — copy secrets.json.example to fill it
in. Checked, in order:

  1. <repo root>/../secrets.json   Production. Lives one directory above the
                                    repo root, outside the deploy/rsync
                                    target, so a deploy can never overwrite
                                    or delete it.
  2. core/backend/secrets.json     Development. Copy secrets.json.example
                                    here and fill in real values.

Values never touch os.environ — they're read directly as attributes on
SECRETS, so they aren't inherited by child processes, don't show up in
/proc/*/environ, etc. Fails loudly at import time if no secrets.json is
found, rather than letting Django start with missing credentials.
"""
import json
from pathlib import Path

_BACKEND_DIR = Path(__file__).resolve().parent.parent  # core/backend
_REPO_ROOT = _BACKEND_DIR.parent.parent  # core/backend -> core -> repo root

_CANDIDATES = [
    _REPO_ROOT.parent / 'secrets.json',  # production
    _BACKEND_DIR / 'secrets.json',       # development
]


def _load():
    for path in _CANDIDATES:
        if path.exists():
            with path.open(encoding='utf-8') as f:
                return json.load(f)
    tried = '\n  '.join(str(p) for p in _CANDIDATES)
    raise RuntimeError(
        "No secrets.json found. Copy core/backend/secrets.json.example to "
        "core/backend/secrets.json and fill in real values (development), "
        "or place a filled-in secrets.json one directory above the repo "
        f"root (production). Checked:\n  {tried}"
    )


class _Secrets:
    """Attribute + dict-style (.get) access over the parsed secrets.json."""

    def __init__(self, data):
        self._data = data

    def __getattr__(self, name):
        try:
            return self._data[name]
        except KeyError:
            raise AttributeError(
                f"secrets.json has no key '{name}' — add it to secrets.json "
                f"(and secrets.json.example)."
            ) from None

    def get(self, name, default=None):
        return self._data.get(name, default)


SECRETS = _Secrets(_load())
