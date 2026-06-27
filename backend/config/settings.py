from pathlib import Path
import logging
import os

from .env import bool_value as _env_bool, int_value as _env_int, list_value as _env_list, optional_str as _env_str, load_env_file
from .runtime import build_runtime


def _env_float(name: str, default: float) -> float:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return float(value)
    except ValueError:
        return default

BASE_DIR = Path(__file__).resolve().parent.parent

DOTENV_OVERRIDE = _env_bool("DOTENV_OVERRIDE", default=False)
ENV_PATH = BASE_DIR / ".env"
DJANGO_ENV_FILE = os.environ.get("DJANGO_ENV_FILE", "").strip()
EXTERNAL_ENV_PATH = Path(DJANGO_ENV_FILE) if DJANGO_ENV_FILE else None
DOTENV_FOUND = load_env_file(EXTERNAL_ENV_PATH or ENV_PATH, override=DOTENV_OVERRIDE)
if EXTERNAL_ENV_PATH and not DOTENV_FOUND:
    DOTENV_FOUND = load_env_file(ENV_PATH, override=DOTENV_OVERRIDE)
RUNTIME_CONFIG = build_runtime(BASE_DIR)
DJANGO_CONFIG_MODE = RUNTIME_CONFIG["mode"]
SECRET_KEY = RUNTIME_CONFIG["SECRET_KEY"]
DEBUG = RUNTIME_CONFIG["DEBUG"]
ALLOWED_HOSTS = RUNTIME_CONFIG["ALLOWED_HOSTS"]
INSTALLED_APPS = [
    "django.contrib.admin",
    "django.contrib.auth",
    "django.contrib.contenttypes",
    "django.contrib.sessions",
    "django.contrib.messages",
    "django.contrib.staticfiles",
    "django.contrib.postgres",
    "corsheaders",
    "rest_framework",
    "apps.core",
    "apps.users",
    "apps.menu",
    "apps.orders",
    "apps.kitchen",
    "apps.reports",
    "apps.employees",
    "apps.payments",
    "apps.printing",
    "apps.cashier",
    "apps.dte",
    "apps.inventory",
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
    "apps.core.middleware.RolePathAccessMiddleware",
    "django.contrib.messages.middleware.MessageMiddleware",
    "django.middleware.clickjacking.XFrameOptionsMiddleware",
]

ROOT_URLCONF = "config.urls"

TEMPLATES = [
    {
        "BACKEND": "django.template.backends.django.DjangoTemplates",
        "DIRS": [],
        "APP_DIRS": True,
        "OPTIONS": {
            "context_processors": [
                "django.template.context_processors.debug",
                "django.template.context_processors.request",
                "django.contrib.auth.context_processors.auth",
                "django.contrib.messages.context_processors.messages",
            ],
        },
    }
]

WSGI_APPLICATION = "config.wsgi.application"
ASGI_APPLICATION = "config.asgi.application"

DATABASES = {
    "default": {
        "ENGINE": "django.db.backends.postgresql",
        **RUNTIME_CONFIG["DATABASE"],
        "OPTIONS": {
            "options": "-c timezone=America/El_Salvador",
        },
    }
}

AUTH_PASSWORD_VALIDATORS = [
    {
        "NAME": "django.contrib.auth.password_validation.UserAttributeSimilarityValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.MinimumLengthValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.CommonPasswordValidator",
    },
    {
        "NAME": "django.contrib.auth.password_validation.NumericPasswordValidator",
    },
]

LANGUAGE_CODE = "en-us"
TIME_ZONE = "America/El_Salvador"
USE_I18N = True
USE_TZ = True

STATIC_URL = "/static/"
STATIC_ROOT = RUNTIME_CONFIG["STATIC_ROOT"]

MEDIA_URL = "/media/"
MEDIA_ROOT = RUNTIME_CONFIG["MEDIA_ROOT"]
MEDIA_ROOT.mkdir(parents=True, exist_ok=True)

MENU_IMAGE_ROOT = MEDIA_ROOT / "menu_image"
MENU_IMAGE_ROOT.mkdir(parents=True, exist_ok=True)

DEFAULT_AUTO_FIELD = "django.db.models.BigAutoField"

REST_FRAMEWORK = {
    "DEFAULT_RENDERER_CLASSES": ["rest_framework.renderers.JSONRenderer"],
    "DEFAULT_PARSER_CLASSES": ["rest_framework.parsers.JSONParser"],
    "DEFAULT_AUTHENTICATION_CLASSES": [
        "rest_framework.authentication.SessionAuthentication",
    ],
    "DEFAULT_PERMISSION_CLASSES": [
        "rest_framework.permissions.IsAuthenticated",
    ],
}

CORS_ALLOWED_ORIGINS = RUNTIME_CONFIG["CORS_ALLOWED_ORIGINS"]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = RUNTIME_CONFIG["CSRF_TRUSTED_ORIGINS"]

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = _env_bool("SESSION_COOKIE_SECURE", default=not DEBUG)
CSRF_COOKIE_SECURE = _env_bool("CSRF_COOKIE_SECURE", default=not DEBUG)

SESSION_COOKIE_SAMESITE = _env_str("SESSION_COOKIE_SAMESITE", "Lax")
CSRF_COOKIE_SAMESITE = _env_str("CSRF_COOKIE_SAMESITE", "Lax")
SESSION_ENGINE = "django.contrib.sessions.backends.db"
AUTHENTICATION_BACKENDS = ["django.contrib.auth.backends.ModelBackend"]

PRINT_WIDTH = 42
PRINT_DRIVER = "dummy"

CASH_DRAWER_ENABLED = _env_bool("CASH_DRAWER_ENABLED", default=False)
CASH_DRAWER_MODE = os.environ.get("CASH_DRAWER_MODE", "mock").strip().lower()
CASH_DRAWER_USB_VENDOR_ID = _env_int("CASH_DRAWER_USB_VENDOR_ID", _env_int("CASH_DRAWER_VENDOR_ID"))
CASH_DRAWER_USB_PRODUCT_ID = _env_int("CASH_DRAWER_USB_PRODUCT_ID", _env_int("CASH_DRAWER_PRODUCT_ID"))
CASH_DRAWER_USB_INTERFACE = _env_int("CASH_DRAWER_USB_INTERFACE", _env_int("CASH_DRAWER_INTERFACE"))
CASH_DRAWER_USB_IN_ENDPOINT = _env_int("CASH_DRAWER_USB_IN_ENDPOINT", _env_int("CASH_DRAWER_IN_EP"))
CASH_DRAWER_USB_OUT_ENDPOINT = _env_int("CASH_DRAWER_USB_OUT_ENDPOINT", _env_int("CASH_DRAWER_OUT_EP"))
CASH_DRAWER_PIN = _env_int("CASH_DRAWER_PIN")
CASH_DRAWER_PULSE_ON = _env_int("CASH_DRAWER_PULSE_ON", 25) or 25
CASH_DRAWER_PULSE_OFF = _env_int("CASH_DRAWER_PULSE_OFF", 250) or 250
CASH_DRAWER_PULSE_COMMAND = os.environ.get("CASH_DRAWER_PULSE_COMMAND", "").strip()

PRINTER_ENABLED = _env_bool("PRINTER_ENABLED", default=CASH_DRAWER_ENABLED)
PRINTER_MODE = os.environ.get("PRINTER_MODE", "usb").strip().lower()
PRINTER_USB_VENDOR_ID = _env_int("PRINTER_USB_VENDOR_ID", CASH_DRAWER_USB_VENDOR_ID)
PRINTER_USB_PRODUCT_ID = _env_int("PRINTER_USB_PRODUCT_ID", CASH_DRAWER_USB_PRODUCT_ID)
PRINTER_USB_INTERFACE = _env_int("PRINTER_USB_INTERFACE", CASH_DRAWER_USB_INTERFACE)
PRINTER_USB_IN_ENDPOINT = _env_int("PRINTER_USB_IN_ENDPOINT", CASH_DRAWER_USB_IN_ENDPOINT)
PRINTER_USB_OUT_ENDPOINT = _env_int("PRINTER_USB_OUT_ENDPOINT", CASH_DRAWER_USB_OUT_ENDPOINT)

RECEIPT_PRINTER_MODE = os.environ.get("RECEIPT_PRINTER_MODE", PRINTER_MODE).strip().lower()
RECEIPT_PRINTER_USB_VENDOR_ID = _env_int("RECEIPT_PRINTER_USB_VENDOR_ID", PRINTER_USB_VENDOR_ID or CASH_DRAWER_USB_VENDOR_ID)
RECEIPT_PRINTER_USB_PRODUCT_ID = _env_int("RECEIPT_PRINTER_USB_PRODUCT_ID", PRINTER_USB_PRODUCT_ID or CASH_DRAWER_USB_PRODUCT_ID)
RECEIPT_PRINTER_USB_INTERFACE = _env_int("RECEIPT_PRINTER_USB_INTERFACE", PRINTER_USB_INTERFACE or CASH_DRAWER_USB_INTERFACE)
RECEIPT_PRINTER_USB_OUT_ENDPOINT = _env_int("RECEIPT_PRINTER_USB_OUT_ENDPOINT", PRINTER_USB_OUT_ENDPOINT or CASH_DRAWER_USB_OUT_ENDPOINT)
RECEIPT_PRINTER_CUT_ENABLED = _env_bool("RECEIPT_PRINTER_CUT_ENABLED", default=True)
PRINTER_SIZE = _env_float("PRINTER_SIZE", 80.0)
PRINTER_SIZE_MM = _env_float("PRINTER_SIZE_MM", PRINTER_SIZE)

MH_AMBIENTE = os.environ.get("MH_AMBIENTE", "00").strip() or "00"
DTE_BACKGROUND_MODE = os.environ.get("DTE_BACKGROUND_MODE", "legacy").strip().lower() or "legacy"
DTE_BASE_URL = os.environ.get("DTE_BASE_URL", "").strip()
DTE_API_TOKEN = os.environ.get("DTE_API_TOKEN", "").strip()
DTE_API_AUTH_HEADER = os.environ.get("DTE_API_AUTH_HEADER", "Authorization").strip() or "Authorization"
DTE_API_AUTH_PREFIX = os.environ.get("DTE_API_AUTH_PREFIX", "Bearer").strip() or "Bearer"
DTE_TIMEOUT_SECONDS = _env_int("DTE_TIMEOUT_SECONDS", 30) or 30
DTE_CONNECT_TIMEOUT = float(os.environ.get("DTE_CONNECT_TIMEOUT", "5") or 5)
DTE_READ_TIMEOUT = float(os.environ.get("DTE_READ_TIMEOUT", str(DTE_TIMEOUT_SECONDS)) or DTE_TIMEOUT_SECONDS)
DTE_DEBUG = _env_bool("DTE_DEBUG", default=False)
DTE_USER_AGENT = os.environ.get("DTE_USER_AGENT", "PicoPOS-DTE/1.0").strip() or "PicoPOS-DTE/1.0"
DTE_HEALTH_ENDPOINT = os.environ.get("DTE_HEALTH_ENDPOINT", "/health").strip() or "/health"
DTE_HEALTH_TIMEOUT_SECONDS = _env_int("DTE_HEALTH_TIMEOUT_SECONDS", 5) or 5
BRANCH_ID = _env_int("BRANCH_ID")
POS_BRANCH_ID = _env_int("POS_BRANCH_ID")
DEFAULT_BRANCH_ID = _env_int("DEFAULT_BRANCH_ID")
ACTIVE_BRANCH_CODE = os.environ.get("ACTIVE_BRANCH_CODE", "").strip()
DTE_MONITOR_INTERVAL_SECONDS = _env_int("DTE_MONITOR_INTERVAL_SECONDS", 10) or 10
DTE_MONITOR_MAX_BACKOFF_SECONDS = _env_int("DTE_MONITOR_MAX_BACKOFF_SECONDS", 30) or 30
DTE_MONITOR_ENABLED = _env_bool("DTE_MONITOR_ENABLED", default=True)
DTE_OUTBOX_WORKER_ENABLED = _env_bool("DTE_OUTBOX_WORKER_ENABLED", default=True)
DTE_MAX_RETRIES = _env_int("DTE_MAX_RETRIES", 5) or 5
DTE_RETRY_BACKOFF_SECONDS = _env_int("DTE_RETRY_BACKOFF_SECONDS", 30) or 30
DTE_BACKOFF_BASE_SECONDS = _env_int("DTE_BACKOFF_BASE_SECONDS", 10) or 10
DTE_BACKOFF_MAX_SECONDS = _env_int("DTE_BACKOFF_MAX_SECONDS", 600) or 600
DTE_PENDING_BATCH_SIZE = _env_int("DTE_PENDING_BATCH_SIZE", 50) or 50
DTE_OUTBOX_INTERVAL = float(os.environ.get("DTE_OUTBOX_INTERVAL", "2") or 2)
DTE_OUTBOX_CONCURRENCY = _env_int("DTE_OUTBOX_CONCURRENCY", 1) or 1
DTE_LOG_IDLE_EVERY_SECONDS = _env_int("DTE_LOG_IDLE_EVERY_SECONDS", 300) or 300
DTE_LOG_SILENT_IDLE = _env_bool("DTE_LOG_SILENT_IDLE", default=True)
DTE_CIRCUIT_FAIL_THRESHOLD = _env_int("DTE_CIRCUIT_FAIL_THRESHOLD", 3) or 3
DTE_CIRCUIT_OPEN_SECONDS = _env_int("DTE_CIRCUIT_OPEN_SECONDS", 60) or 60
DTE_ERROR_LOG_COOLDOWN_SECONDS = _env_int("DTE_ERROR_LOG_COOLDOWN_SECONDS", 30) or 30
DTE_LOG_PAYLOAD_FULL = _env_bool("DTE_LOG_PAYLOAD_FULL", default=False)
DTE_DEBUG_LOG_PAYLOAD = _env_bool("DTE_DEBUG_LOG_PAYLOAD", default=DTE_LOG_PAYLOAD_FULL)
DTE_LOG_PAYLOAD_TO_FILE = _env_bool("DTE_LOG_PAYLOAD_TO_FILE", default=DTE_LOG_PAYLOAD_FULL)
DTE_LOG_PAYLOAD_DIR = os.environ.get("DTE_LOG_PAYLOAD_DIR", "tmp/dte_payloads").strip() or "tmp/dte_payloads"
DTE_LOG_PAYLOAD_MAX_CHARS = _env_int("DTE_LOG_PAYLOAD_MAX_CHARS", 0) or 0
DTE_LOG_VERBOSE = _env_bool("DTE_LOG_VERBOSE", default=False)
DTE_LOG_LEVEL = (os.environ.get("DTE_LOG_LEVEL", "INFO") or "INFO").upper()
DTE_LOG_RESPONSE_FULL = _env_bool("DTE_LOG_RESPONSE_FULL", default=False)
DTE_LOG_TO_FILE = _env_bool("DTE_LOG_TO_FILE", default=DTE_LOG_PAYLOAD_FULL)
DTE_LOG_DIR = RUNTIME_CONFIG["DTE_LOG_DIR"]
DTE_LOG_TRUNCATE_CHARS = _env_int("DTE_LOG_TRUNCATE_CHARS", 0) or 0
DTE_LOG_INCLUDE_SIGNED_DOCUMENT = _env_bool("DTE_LOG_INCLUDE_SIGNED_DOCUMENT", default=False)
DTE_EMISOR_NIT = os.environ.get("DTE_EMISOR_NIT", "").strip()
CODE_CHANGE_PRICE = os.environ.get("CODE_CHANGE_PRICE", "").strip()

logging.getLogger(__name__).info(
    "[DTE CONFIG] base_url=%r mh_ambiente=%r",
    DTE_BASE_URL,
    MH_AMBIENTE,
)

LOGGING = {
    "version": 1,
    "disable_existing_loggers": False,
    "handlers": {
        "console": {
            "class": "logging.StreamHandler",
        },
    },
    "loggers": {
        "apps.dte": {
            "handlers": ["console"],
            "level": DTE_LOG_LEVEL,
            "propagate": True,
        },
    },
}
