from __future__ import annotations

from pathlib import Path
from urllib.parse import urlparse
from . import env

LEGACY_ALLOWED_HOSTS = ["localhost", "127.0.0.1", "0.0.0.0", "centro-pdg.cuskatech.com"]
LEGACY_CORS = ["http://localhost:8182", "http://127.0.0.1:8182", "https://centro-pdg.cuskatech.com"]
LEGACY_CSRF = ["http://localhost:8182", "http://127.0.0.1:8182", "http://localhost:9102", "https://centro-pdg.cuskatech.com"]

def validate_hosts(hosts: list[str], *, strict: bool) -> list[str]:
    if strict and not hosts:
        raise env.EnvConfigError("Falta ALLOWED_HOSTS")
    for host in hosts:
        if "://" in host:
            raise env.EnvConfigError("ALLOWED_HOSTS no acepta URLs completas")
        if host == "*" and strict:
            raise env.EnvConfigError("ALLOWED_HOSTS no acepta * en strict")
    return hosts

def origins(name: str, extra: str, legacy: list[str], *, strict: bool) -> list[str]:
    base = env.list_value(name, [] if strict else legacy)
    if name in __import__('os').environ:
        base = env.list_value(name, [])
    values = base + env.list_value(extra, [])
    values = env.list_value("__runtime_combined__", values, environ={})
    for origin in values:
        parsed = urlparse(origin)
        if origin == "*" or parsed.scheme not in {"http", "https"} or not parsed.netloc:
            raise env.EnvConfigError(f"Origen inválido en {name}")
    return values

def build_runtime(BASE_DIR: Path):
    mode = env.env_mode()
    strict = mode == "strict"
    secret = env.required_str("DJANGO_SECRET_KEY", mode=mode, default="dev-secret-key")
    debug = env.bool_value("DJANGO_DEBUG", default=True)
    allowed = validate_hosts(env.list_value("ALLOWED_HOSTS", [] if strict else LEGACY_ALLOWED_HOSTS), strict=strict)
    db = {
        "HOST": env.required_str("DB_HOST", mode=mode, default="localhost"),
        "USER": env.required_str("DB_USER", mode=mode, default="jarvis"),
        "PASSWORD": env.required_str("DB_PASSWORD", mode=mode, default="diez2030"),
        "NAME": env.required_str("DB_NAME", mode=mode, default="gallo_db"),
        "PORT": env.required_str("DB_PORT", mode=mode, default="5432"),
    }
    return {
        "mode": mode, "strict": strict, "SECRET_KEY": secret, "DEBUG": debug,
        "ALLOWED_HOSTS": allowed,
        "CORS_ALLOWED_ORIGINS": origins("CORS_ALLOWED_ORIGINS", "CORS_ALLOWED_ORIGINS_EXTRA", LEGACY_CORS, strict=strict),
        "CSRF_TRUSTED_ORIGINS": origins("CSRF_TRUSTED_ORIGINS", "CSRF_TRUSTED_ORIGINS_EXTRA", LEGACY_CSRF, strict=strict),
        "DATABASE": db,
        "MEDIA_ROOT": env.path_value("DJANGO_MEDIA_ROOT", BASE_DIR / "media"),
        "STATIC_ROOT": env.path_value("DJANGO_STATIC_ROOT", BASE_DIR / "static"),
        "DTE_LOG_DIR": str(env.path_value("DTE_LOG_DIR", Path("tmp/dte_payloads"))),
    }
