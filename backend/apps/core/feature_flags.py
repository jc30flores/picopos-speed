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
