"""Production settings — PostgreSQL, Sentry, rotating file log, strict security."""
import logging
from core.secrets import SECRETS
from .base import *  # noqa: F401, F403

DEBUG = False

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.postgresql',
        'NAME': SECRETS.DB_NAME,
        'USER': SECRETS.DB_USER,
        'PASSWORD': SECRETS.DB_PASSWORD,
        'HOST': SECRETS.get('DB_HOST', 'localhost'),
        'PORT': SECRETS.get('DB_PORT', '5432'),
    }
}

# Sentry — optional; silently skipped if DSN is not set.
_sentry_dsn = SECRETS.get('SENTRY_DSN_BACKEND')
if _sentry_dsn:
    import sentry_sdk
    from sentry_sdk.integrations.logging import LoggingIntegration
    sentry_sdk.init(
        dsn=_sentry_dsn,
        traces_sample_rate=0.1,
        send_default_pii=False,
        integrations=[
            LoggingIntegration(level=logging.ERROR, event_level=logging.ERROR),
        ],
    )

CORS_ALLOWED_ORIGINS = SECRETS.get('CORS_ALLOWED_ORIGINS', [])

# Security headers
SECURE_PROXY_SSL_HEADER = ('HTTP_X_FORWARDED_PROTO', 'https')
SECURE_HSTS_SECONDS = 31536000
SECURE_HSTS_INCLUDE_SUBDOMAINS = True
SECURE_SSL_REDIRECT = True
SESSION_COOKIE_SECURE = True
CSRF_COOKIE_SECURE = True

STRIPE_SECRET_KEY = SECRETS.get("STRIPE_SECRET_KEY", "")

# Default lives inside the app dir (already owned/writable by the deploy
# user) rather than /var/log, so a missing LOG_FILE secret can't crash
# startup with "Unable to configure handler 'file'".
_LOG_FILE = Path(SECRETS.get('LOG_FILE') or (BASE_DIR / 'logs' / 'app.log'))
_LOG_FILE.parent.mkdir(parents=True, exist_ok=True)

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name} {process:d} {thread:d}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'file': {
            'class': 'logging.handlers.RotatingFileHandler',
            'filename': str(_LOG_FILE),
            'maxBytes': 10 * 1024 * 1024,  # 10 MB
            'backupCount': 5,
            'formatter': 'verbose',
            'encoding': 'utf-8',
        },
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['file', 'console'],
        'level': 'WARNING',
    },
}
