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
