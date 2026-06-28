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
REPO_ROOT = BASE_DIR.parent.parent  # core/backend -> core -> repo root

# Production: .env lives one level above the repo (outside rsync target).
# Local dev: falls back to core/backend/.env.
load_dotenv(REPO_ROOT.parent / '.env') or load_dotenv(BASE_DIR / '.env')

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

AWS_ACCESS_KEY_ID     = os.environ.get('AWS_ACCESS_KEY_ID', '')
AWS_SECRET_ACCESS_KEY = os.environ.get('AWS_SECRET_ACCESS_KEY', '')
AWS_SES_REGION_NAME   = os.environ.get('AWS_SES_REGION_NAME', 'us-east-1')
AWS_SES_REGION_ENDPOINT = f'email.{AWS_SES_REGION_NAME}.amazonaws.com'
DEFAULT_FROM_EMAIL    = os.environ.get('DEFAULT_FROM_EMAIL', '')

LANGUAGE_CODE = 'en-us'
TIME_ZONE = 'UTC'
USE_I18N = True
USE_TZ = True

STATIC_URL = '/static/'
STATIC_ROOT = BASE_DIR / 'staticfiles'

MEDIA_URL  = '/media/'
MEDIA_ROOT = BASE_DIR / 'media'

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'ERROR',
    },
}

DEFAULT_AUTO_FIELD = 'django.db.models.BigAutoField'

try:
    from core.installed_modules import (
        INSTALLED_MODULE_APPS,
        MODULE_EXTRA_APPS,
        MODULE_EXTRA_MIDDLEWARE,
        MODULE_SETTINGS,
    )
except ImportError:
    INSTALLED_MODULE_APPS = []
    MODULE_EXTRA_APPS = []
    MODULE_EXTRA_MIDDLEWARE = []
    MODULE_SETTINGS = {}

INSTALLED_APPS += INSTALLED_MODULE_APPS + MODULE_EXTRA_APPS
MIDDLEWARE += MODULE_EXTRA_MIDDLEWARE


def _deep_merge_setting(existing, override):
    for key, val in override.items():
        if key in existing and isinstance(existing[key], dict) and isinstance(val, dict):
            _deep_merge_setting(existing[key], val)
        elif key in existing and isinstance(existing[key], list) and isinstance(val, list):
            existing[key].extend(val)
        else:
            existing[key] = val

for _k, _v in MODULE_SETTINGS.items():
    _existing = globals().get(_k)
    if isinstance(_existing, dict) and isinstance(_v, dict):
        _deep_merge_setting(_existing, _v)
    elif isinstance(_existing, list) and isinstance(_v, list):
        _existing.extend(_v)
    else:
        globals()[_k] = _v
