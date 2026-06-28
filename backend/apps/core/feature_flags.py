from apps.core.models import FeatureFlag


def is_feature_enabled(key: str, *, default: bool = False) -> bool:
    if not key:
        return default
    value = (
        FeatureFlag.objects.filter(key=key)
        .values_list("is_enabled", flat=True)
        .first()
    )
    if value is None:
        return default
    return bool(value)


def get_feature_metadata(key: str) -> dict:
    row = FeatureFlag.objects.filter(key=key).values_list("metadata", flat=True).first()
    if isinstance(row, dict):
        return row
    return {}


def can_view_cash_expected_totals(user) -> tuple[bool, set[str]]:
    if getattr(user, "is_superuser", False):
        return True, set()
    role = getattr(getattr(user, "profile", None), "role", None)
    if role == "admin":
        return True, set()
    enabled = is_feature_enabled("FF_CASH_CLOSE_EXPECTED_TOTALS_CONTROL_ENABLED", default=True)
    if not enabled:
        return True, set()
    metadata = get_feature_metadata("FF_CASH_CLOSE_EXPECTED_TOTALS_CONTROL_ENABLED")
    allowed_roles = set(metadata.get("allowed_roles") or [])
    visible_fields = set(metadata.get("visible_fields") or [])
    if role not in allowed_roles:
        return False, set()
    return True, visible_fields


QUICK_SALES_FLAG_KEY = "pos_quick_sales_button"
QUICK_SALES_MODES = {"last_sale", "history", "hidden"}
QUICK_SALES_HISTORY_SCOPES = {"current_shift", "time_window"}
QUICK_SALES_HISTORY_WINDOWS = {15, 30, 60, 120, 240, 1440}


def get_pos_quick_sales_settings() -> dict:
    flag, _ = FeatureFlag.objects.get_or_create(
        key=QUICK_SALES_FLAG_KEY,
        defaults={
            "label": "Botón rápido de ventas en POS",
            "description": "Controla si el botón rápido del POS reimprime la última venta, muestra historial o se oculta.",
            "is_enabled": True,
            "metadata": {
                "mode": "last_sale",
                "history_scope": "current_shift",
                "history_window_minutes": 60,
            },
        },
    )
    metadata = dict(flag.metadata or {})
    mode = str(metadata.get("mode") or "last_sale").strip().lower()
    if not flag.is_enabled and mode != "hidden":
        mode = "hidden"
    if mode not in QUICK_SALES_MODES:
        mode = "last_sale"
    history_scope = str(metadata.get("history_scope") or "current_shift").strip().lower()
    if history_scope not in QUICK_SALES_HISTORY_SCOPES:
        history_scope = "current_shift"
    try:
        history_window_minutes = int(metadata.get("history_window_minutes") or 60)
    except (TypeError, ValueError):
        history_window_minutes = 60
    if history_window_minutes not in QUICK_SALES_HISTORY_WINDOWS:
        history_window_minutes = 60
    return {
        "mode": mode,
        "history_scope": history_scope,
        "history_window_minutes": history_window_minutes,
    }


def set_pos_quick_sales_settings(*, mode=None, history_scope=None, history_window_minutes=None) -> dict:
    flag, _ = FeatureFlag.objects.get_or_create(
        key=QUICK_SALES_FLAG_KEY,
        defaults={
            "label": "Botón rápido de ventas en POS",
            "description": "Controla si el botón rápido del POS reimprime la última venta, muestra historial o se oculta.",
            "is_enabled": True,
            "metadata": {},
        },
    )
    current = get_pos_quick_sales_settings()
    if mode is not None:
        mode = str(mode or "last_sale").strip().lower()
        if mode not in QUICK_SALES_MODES:
            raise ValueError("Modo inválido.")
        current["mode"] = mode
    if history_scope is not None:
        history_scope = str(history_scope or "current_shift").strip().lower()
        if history_scope not in QUICK_SALES_HISTORY_SCOPES:
            raise ValueError("Alcance de historial inválido.")
        current["history_scope"] = history_scope
    if history_window_minutes is not None:
        try:
            window = int(history_window_minutes)
        except (TypeError, ValueError):
            raise ValueError("Ventana de historial inválida.")
        if window not in QUICK_SALES_HISTORY_WINDOWS:
            raise ValueError("Ventana de historial inválida.")
        current["history_window_minutes"] = window
    flag.is_enabled = current["mode"] != "hidden"
    flag.metadata = {
        "mode": current["mode"],
        "history_scope": current["history_scope"],
        "history_window_minutes": current["history_window_minutes"],
    }
    flag.save(update_fields=["is_enabled", "metadata"])
    return current
