from __future__ import annotations

from django.conf import settings
from django.core.files.storage import default_storage


def _to_relative_path(value: str) -> str | None:
    raw = (value or "").strip()
    if not raw:
        return None
    if raw.startswith("http://") or raw.startswith("https://"):
        return None

    media_prefix = settings.MEDIA_URL.rstrip("/") + "/"
    if raw.startswith(media_prefix):
        return raw[len(media_prefix) :].lstrip("/")
    if raw.startswith("/media/"):
        return raw[len("/media/") :].lstrip("/")
    if raw.startswith("/menu_image/"):
        return f"menu_image/{raw.split('/menu_image/', 1)[1]}".lstrip("/")

    return raw.lstrip("/")


def safe_media_url(*, image=None, image_path: str | None = None) -> str | None:
    if image is not None and getattr(image, "name", None):
        name = str(image.name).lstrip("/")
        if name and default_storage.exists(name):
            return default_storage.url(name)

    for candidate in (image_path, image if isinstance(image, str) else None):
        if not candidate:
            continue
        value = str(candidate).strip()
        if value.startswith("http://") or value.startswith("https://"):
            return value
        rel = _to_relative_path(value)
        if rel and default_storage.exists(rel):
            return default_storage.url(rel)

    return None
