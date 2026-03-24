from pathlib import Path
import os

try:
    from dotenv import load_dotenv
except Exception:  # pragma: no cover
    load_dotenv = None


def _load_env_file(base_dir: Path) -> None:
    env_path = base_dir / ".env"
    if load_dotenv is not None:
        load_dotenv(env_path, override=True)
        return
    if not env_path.exists():
        return
    for raw_line in env_path.read_text().splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        os.environ[key.strip()] = value.strip()


BASE_DIR = Path(__file__).resolve().parent.parent
_load_env_file(BASE_DIR)


def _env_bool(name: str, default: bool = False) -> bool:
    return os.environ.get(name, str(default)).strip().lower() in {"1", "true", "yes", "on"}


def _env_int(name: str, default: int | None = None) -> int | None:
    value = os.environ.get(name)
    if value is None or value == "":
        return default
    try:
        return int(value, 0)
    except ValueError:
        return default


SECRET_KEY = os.environ.get("DJANGO_SECRET_KEY", "dev-secret-key")
DEBUG = os.environ.get("DJANGO_DEBUG", "true").lower() == "true"

ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "pico-de-gallo-pos.cuskatech.com"]

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
]

MIDDLEWARE = [
    "corsheaders.middleware.CorsMiddleware",
    "django.middleware.security.SecurityMiddleware",
    "django.contrib.sessions.middleware.SessionMiddleware",
    "django.middleware.common.CommonMiddleware",
    "django.middleware.csrf.CsrfViewMiddleware",
    "django.contrib.auth.middleware.AuthenticationMiddleware",
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
        "HOST": os.environ.get("DB_HOST", "localhost"),
        "USER": os.environ.get("DB_USER", "jarvis"),
        "PASSWORD": os.environ.get("DB_PASSWORD", "diez2030"),
        "NAME": os.environ.get("DB_NAME", "gallo_db"),
        "PORT": os.environ.get("DB_PORT", "5432"),
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
STATIC_ROOT = BASE_DIR / "static"

MEDIA_URL = "/media/"
MEDIA_ROOT = BASE_DIR / "media"
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

CORS_ALLOWED_ORIGINS = [
    "http://localhost:8182",
    "http://127.0.0.1:8182",
    "https://pico-de-gallo-pos.cuskatech.com",
]

CORS_ALLOW_CREDENTIALS = True

CSRF_TRUSTED_ORIGINS = [
    "http://localhost:8182",
    "http://127.0.0.1:8182",
    "http://localhost:9102",
    "https://pico-de-gallo-pos.cuskatech.com",
]

USE_X_FORWARDED_HOST = True
SECURE_PROXY_SSL_HEADER = ("HTTP_X_FORWARDED_PROTO", "https")

SESSION_COOKIE_SECURE = not DEBUG
CSRF_COOKIE_SECURE = not DEBUG

SESSION_COOKIE_SAMESITE = "Lax"
CSRF_COOKIE_SAMESITE = "Lax"

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
