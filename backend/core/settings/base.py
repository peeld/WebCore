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
    'rest_framework',
    'corsheaders',
    'core_app',
]

MIDDLEWARE = [
    'corsheaders.middleware.CorsMiddleware',
    'django.middleware.security.SecurityMiddleware',
    'django.contrib.sessions.middleware.SessionMiddleware',
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
        'rest_framework.authentication.SessionAuthentication',
    ],
    'DEFAULT_PERMISSION_CLASSES': [
        'rest_framework.permissions.IsAuthenticated',
    ],
}

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

# Module auto-discovery -- scans modules/*/backend/<name>/apps.py.
# Exposed as a function so it can be unit-tested in isolation.
MODULES_DIR = BASE_DIR.parent.parent / "modules"


def _discover_modules(modules_dir):
    """Return sorted list of Django app labels found in modules_dir.

    Also inserts each module's backend/ directory into sys.path so Django
    can import the app package. Safe to call multiple times (no duplicate paths).
    """
    apps = []
    if not modules_dir.exists():
        return apps
    for entry in sorted(modules_dir.iterdir()):
        if not entry.is_dir():
            continue
        app_dir = entry / "backend" / entry.name
        if (app_dir / "apps.py").exists():
            backend_path = str(entry / "backend")
            if backend_path not in sys.path:
                sys.path.insert(0, backend_path)
            apps.append(entry.name)
    return apps


# Kept separate from INSTALLED_APPS so urls.py can iterate only module apps.
INSTALLED_MODULE_APPS = _discover_modules(MODULES_DIR)
INSTALLED_APPS += INSTALLED_MODULE_APPS
