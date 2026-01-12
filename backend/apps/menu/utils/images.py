import os
from uuid import uuid4

from django.conf import settings
from django.core.exceptions import ValidationError

ALLOWED_EXTS = {"jpg", "jpeg", "png", "webp"}


def normalize_category(name: str) -> str:
    return (name or "").strip().upper()


def save_menu_image(file_obj, category_name: str) -> dict:
    if not file_obj or not getattr(file_obj, "name", None):
        raise ValidationError("No image file provided")

    original = file_obj.name
    ext = original.rsplit(".", 1)[-1].lower() if "." in original else ""
    if ext not in ALLOWED_EXTS:
        raise ValidationError(f"Formato inválido: .{ext}. Usa: {', '.join(sorted(ALLOWED_EXTS))}")

    category = normalize_category(category_name)
    if not category:
        raise ValidationError("Categoría inválida para guardar imagen")

    folder = os.path.join(str(settings.MENU_IMAGE_ROOT), category)
    os.makedirs(folder, exist_ok=True)

    filename = f"{uuid4().hex}.{ext}"
    abs_path = os.path.join(folder, filename)

    with open(abs_path, "wb+") as destination:
        for chunk in file_obj.chunks():
            destination.write(chunk)

    rel = f"menu_image/{category}/{filename}"
    return {
        "image": rel,
        "image_path": f"{settings.MEDIA_URL.rstrip('/')}/{rel}",
        "abs_path": abs_path,
    }


def delete_menu_image_by_image_field(image_value: str) -> None:
    if not image_value:
        return
    normalized = image_value
    if normalized.startswith("menu_image/"):
        normalized = normalized.replace("menu_image/", "", 1)
    abs_path = os.path.join(str(settings.MENU_IMAGE_ROOT), normalized)
    if os.path.isfile(abs_path):
        try:
            os.remove(abs_path)
        except Exception:
            pass
