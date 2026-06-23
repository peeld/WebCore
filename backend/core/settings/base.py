"""
Shared settings for all environments.
Environment-specific files (development.py, production.py) import from here.
"""
import os
import sys
from pathlib import Path

from dotenv import load_dotenv

# BASE_DIR = core/backend/
BASE_DIR = Path(__file__).resolve().parent.parent.parent

# Load .env for local development; no-op when file is absent (production uses real env vars).
load_dotenv(BASE_DIR / '.env')

# Required -- fail loudly if missing rather than running with an unsafe default.
SECRET_KEY = os.environ['SECRET_KEY']

DEBUG = False  # Always overridden by environment settings.

ALLOWED_HOSTS = [h.strip() for h in os.environ.get('ALLOWED_HOSTS', 'localhost,127.0.0.1').split(',')]

INSTALLED_APPS = [
    'django.contrib.admin',
    'django.contrib.auth',
    'django.contrib.contenttypes',
    'django.contrib.sessions',
    'django.contrib.messages',
    'django.contrib.staticfiles',
    'django.contrib.sites',
    'rest_framework',
    'corsheaders',
    'allauth',
    'allauth.account',
    'allauth.socialaccount',
    'allauth.socialaccount.providers.google',
    'dj_rest_auth',
    'dj_rest_auth.registration',
    'rest_framework_simplejwt',
    'core_app',
]

SITE_ID = 1

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
    'allauth.account.middleware.AccountMiddleware',
    'django.middleware.common.CommonMiddleware',
    'django.middleware.csrf.CsrfViewMiddleware',
    'django.contrib.auth.middleware.AuthenticationMiddleware',
    'django.contrib.messages.middleware.MessageMiddleware',
    'django.middleware.clickjacking.XFrameOptionsMiddleware',
]

ROOT_URLCONF = 'core.urls'

TEMPLATES = [
    {
        'BACKEND': 'django.template.backends.django.DjangoTemplates',
        'DIRS': [],
        'APP_DIRS': True,
        'OPTIONS': {
            'context_processors': [
                'django.template.context_processors.request',
                'django.contrib.auth.context_processors.auth',
                'django.contrib.messages.context_processors.messages',
            ],
        },
    },
]

WSGI_APPLICATION = 'core.wsgi.application'

AUTH_USER_MODEL = 'core_app.CustomUser'

AUTH_PASSWORD_VALIDATORS = [
    {'NAME': 'django.contrib.auth.password_validation.UserAttributeSimilarityValidator'},
    {'NAME': 'django.contrib.auth.password_validation.MinimumLengthValidator'},
    {'NAME': 'django.contrib.auth.password_validation.CommonPasswordValidator'},
    {'NAME': 'django.contrib.auth.password_validation.NumericPasswordValidator'},
]

REST_FRAMEWORK = {
    'DEFAULT_RENDERER_CLASSES': [
        'rest_framework.renderers.JSONRenderer',
    ],
    'DEFAULT_AUTHENTICATION_CLASSES': [
        'rest_framework_simplejwt.authentication.JWTAuthentication',
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

from datetime import timedelta
SIMPLE_JWT = {
    'ACCESS_TOKEN_LIFETIME':  timedelta(hours=1),
    'REFRESH_TOKEN_LIFETIME': timedelta(days=7),
    'ROTATE_REFRESH_TOKENS':  True,
}

ACCOUNT_LOGIN_METHODS         = {'username'}
ACCOUNT_SIGNUP_FIELDS         = ['email*', 'username*', 'password1*', 'password2*']
ACCOUNT_EMAIL_VERIFICATION    = 'none'

REST_AUTH = {
    'USE_JWT':        True,
    'JWT_AUTH_COOKIE': None,
    'TOKEN_MODEL':    None,
}

FRONTEND_URL = os.environ.get('FRONTEND_URL', 'http://localhost:5173')

RECAPTCHA_SITE_KEY   = os.environ.get('RECAPTCHA_SITE_KEY', '')
RECAPTCHA_SECRET_KEY = os.environ.get('RECAPTCHA_SECRET_KEY', '')

SOCIALACCOUNT_PROVIDERS = {
    'google': {
        'APP': {
            'client_id': os.environ.get('GOOGLE_CLIENT_ID', ''),
            'secret':    os.environ.get('GOOGLE_CLIENT_SECRET', ''),
            'key':       '',
        },
        'SCOPE': ['profile', 'email'],
        'AUTH_PARAMS': {'access_type': 'online'},
    }
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Module auto-discovery -- scans modules/*/backend/<name>/apps.py.
# Exposed as functions so they can be unit-tested in isolation.
MODULES_DIR = BASE_DIR.parent.parent / "modules"


def _topo_sort(graph):
    """Topological sort of module names so dependencies precede dependents.

    graph: dict mapping module_name -> list of required module names.
    Only edges to modules present in the graph are followed (unknown
    requirements are silently ignored -- install.py enforces completeness).
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


def _discover_modules(modules_dir):
    """Return Django app labels for all valid modules, ordered by dependency.

    Reads each module's module.json `requires` field to produce a topological
    ordering so dependencies always appear before dependents in INSTALLED_APPS.
    Falls back gracefully when module.json is absent or malformed.
    Also inserts each module's backend/ directory into sys.path so Django
    can import the app package. Safe to call multiple times (no duplicate paths).
    """
    import json
    import logging

    if not modules_dir.exists():
        return []

    graph = {}  # name -> [required module names]
    for entry in sorted(modules_dir.iterdir()):
        if not entry.is_dir():
            continue
        app_dir = entry / "backend" / entry.name
        if not (app_dir / "apps.py").exists():
            continue

        backend_path = str(entry / "backend")
        if backend_path not in sys.path:
            sys.path.insert(0, backend_path)

        requires = []
        manifest = entry / "module.json"
        if manifest.exists():
            try:
                requires = json.loads(manifest.read_text()).get("requires", [])
                assert isinstance(requires, list), "requires must be a list"
            except (json.JSONDecodeError, AssertionError, OSError) as exc:
                logging.getLogger(__name__).warning(
                    "module.json in %s is invalid (%s); ignoring requires", entry.name, exc
                )

        graph[entry.name] = requires

    return _topo_sort(graph)


# Kept separate from INSTALLED_APPS so urls.py can iterate only module apps.
INSTALLED_MODULE_APPS = _discover_modules(MODULES_DIR)
INSTALLED_APPS += INSTALLED_MODULE_APPS
