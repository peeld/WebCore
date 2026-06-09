"""Development settings — SQLite, console logging, Vite CORS, browsable API."""
from .base import *  # noqa: F401, F403

DEBUG = True

DATABASES = {
    'default': {
        'ENGINE': 'django.db.backends.sqlite3',
        'NAME': BASE_DIR / 'db.sqlite3',  # noqa: F405
    }
}

# Browsable API is useful during development.
REST_FRAMEWORK['DEFAULT_RENDERER_CLASSES'] = [  # noqa: F405
    'rest_framework.renderers.JSONRenderer',
    'rest_framework.renderers.BrowsableAPIRenderer',
]

# Allow the Vite dev server to call the Django API directly (e.g. Postman, curl).
# Browser requests go through the Vite proxy and don't need this, but it's
# useful for direct API testing.
CORS_ALLOWED_ORIGINS = [
    'http://localhost:5173',
    'http://127.0.0.1:5173',
]

LOGGING = {
    'version': 1,
    'disable_existing_loggers': False,
    'formatters': {
        'verbose': {
            'format': '{asctime} {levelname} {name}: {message}',
            'style': '{',
        },
    },
    'handlers': {
        'console': {
            'class': 'logging.StreamHandler',
            'formatter': 'verbose',
        },
    },
    'root': {
        'handlers': ['console'],
        'level': 'DEBUG',
    },
    'loggers': {
        # Quieten noisy Django internals to WARNING in dev.
        'django': {'level': 'WARNING', 'propagate': True},
    },
}
