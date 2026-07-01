from __future__ import annotations

import os
from pathlib import Path
from typing import Mapping

TRUE_VALUES = {"1", "true", "yes", "on"}
FALSE_VALUES = {"0", "false", "no", "off"}
VALID_MODES = {"legacy", "strict"}
SENSITIVE_NAMES = {"SECRET", "PASSWORD", "TOKEN", "KEY"}

class EnvConfigError(ValueError):
    pass

def is_sensitive(name: str) -> bool:
    upper = name.upper()
    return any(part in upper for part in SENSITIVE_NAMES)

def clean(value: object | None) -> str | None:
    if value is None:
        return None
    return str(value).strip().strip('"').strip("'").strip()

def load_env_file(path: str | Path, *, override: bool = False, environ: dict[str, str] | None = None) -> bool:
    env = os.environ if environ is None else environ
    dotenv = Path(path)
    if not dotenv.exists():
        return False
    for raw_line in dotenv.read_text(encoding="utf-8").splitlines():
        line = raw_line.strip()
        if not line or line.startswith("#") or "=" not in line:
            continue
        key, value = line.split("=", 1)
        key = key.strip()
        if not key or (key in env and not override):
            continue
        env[key] = clean(value) or ""
    return True

def env_mode(environ: Mapping[str, str] | None = None) -> str:
    env = os.environ if environ is None else environ
    mode = clean(env.get("DJANGO_CONFIG_MODE")) or "legacy"
    if mode not in VALID_MODES:
        raise EnvConfigError("DJANGO_CONFIG_MODE debe ser legacy o strict")
    return mode

def optional_str(name: str, default: str | None = None, *, environ: Mapping[str, str] | None = None) -> str | None:
    env = os.environ if environ is None else environ
    value = clean(env.get(name))
    return default if value in (None, "") else value

def required_str(name: str, *, mode: str = "strict", default: str | None = None, environ: Mapping[str, str] | None = None) -> str:
    value = optional_str(name, default if mode == "legacy" else None, environ=environ)
    if value in (None, ""):
        raise EnvConfigError(f"Falta {name}")
    return value

def bool_value(name: str, default: bool | None = None, *, environ: Mapping[str, str] | None = None) -> bool:
    raw = optional_str(name, None, environ=environ)
    if raw is None:
        if default is None:
            raise EnvConfigError(f"Falta {name}")
        return default
    lowered = raw.lower()
    if lowered in TRUE_VALUES:
        return True
    if lowered in FALSE_VALUES:
        return False
    raise EnvConfigError(f"Valor booleano inválido para {name}")

def int_value(name: str, default: int | None = None, *, environ: Mapping[str, str] | None = None) -> int | None:
    raw = optional_str(name, None, environ=environ)
    if raw is None:
        return default
    try:
        return int(raw, 0)
    except ValueError as exc:
        raise EnvConfigError(f"Valor entero inválido para {name}") from exc

def list_value(name: str, default: list[str] | None = None, *, environ: Mapping[str, str] | None = None) -> list[str]:
    raw = optional_str(name, None, environ=environ)
    items = list(default or []) if raw is None else raw.split(",")
    result = []
    seen = set()
    for item in items:
        value = clean(item)
        if value and value not in seen:
            seen.add(value)
            result.append(value)
    return result

def path_value(name: str, default: Path, *, environ: Mapping[str, str] | None = None) -> Path:
    raw = optional_str(name, None, environ=environ)
    return Path(raw) if raw else default

def require_no_secret_leak(error: Exception, secret: str) -> bool:
    return secret not in str(error)
