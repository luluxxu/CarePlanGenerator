"""
Minimal Django settings for the MVP.

刻意精简：
- 不引入 auth / contenttypes / admin，省去 migrate 步骤
- DEBUG=True 直接出错就显示堆栈，方便调试
- 没有 CSRF middleware，省得在最小 demo 里折腾 token
"""

from pathlib import Path

BASE_DIR = Path(__file__).resolve().parent.parent

SECRET_KEY = "dev-only-not-secure-do-not-use-in-prod"
DEBUG = True
ALLOWED_HOSTS = ["*"]

INSTALLED_APPS = [
    "care_plan",
]

MIDDLEWARE = [
    "django.middleware.common.CommonMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {"context_processors": []},
    },
]

WSGI_APPLICATION = "config.wsgi.application"

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"
STATIC_URL = "/static/"

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "formatters": {
        "simple": {
            "format": "{asctime} {levelname:7s} {name}: {message}",
            "style": "{",
            "datefmt": "%H:%M:%S",
        },
    },
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
            "formatter": "simple",
        },
    },
    "loggers": {
        "care_plan": {
            "handlers": ["console"],
            "level": "INFO",
            "propagate": False,
        },
    },
}
