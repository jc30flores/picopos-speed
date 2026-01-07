import os
import re
import sys

import django

BACKEND_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

if BACKEND_ROOT not in sys.path:
    sys.path.insert(0, BACKEND_ROOT)

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "config.settings")

django.setup()

from django.conf import settings  # noqa: E402
from apps.menu.models import Product  # noqa: E402

MENU_IMAGE_DIR = settings.MEDIA_ROOT

OLD_PATH_PATTERN = re.compile(r"^/menu_image/([^/]+)$")
IMAGE_EXTENSIONS = {".jpg", ".jpeg", ".png", ".webp"}


def list_category_files(category_name: str) -> list[str]:
    category_dir = os.path.join(MENU_IMAGE_DIR, category_name)
    if not os.path.isdir(category_dir):
        return []
    return sorted(
        [
            os.path.join(category_dir, filename)
            for filename in os.listdir(category_dir)
            if os.path.isfile(os.path.join(category_dir, filename))
            and os.path.splitext(filename)[1].lower() in IMAGE_EXTENSIONS
        ],
        key=lambda path: os.path.getmtime(path),
    )


def find_file_in_tree(filename: str) -> list[str]:
    matches = []
    for root, _, files in os.walk(MENU_IMAGE_DIR):
        if filename in files:
            matches.append(os.path.join(root, filename))
    return matches


def to_web_path(file_path: str) -> str:
    rel = os.path.relpath(file_path, MENU_IMAGE_DIR)
    rel = rel.replace(os.sep, "/")
    return f"{settings.MEDIA_URL.rstrip('/')}/{rel}"


def main() -> int:
    updated = 0
    nullified = 0
    skipped = 0

    products = Product.objects.select_related("category").exclude(image_path__isnull=True)

    for product in products:
        image_path = product.image_path or ""
        category_name = (product.category.name or "").strip().upper() if product.category else ""
        normalized_path = image_path.strip()
        relative_path = normalized_path.lstrip("/")
        physical_path = os.path.join(BACKEND_ROOT, relative_path)

        if os.path.isfile(physical_path):
            skipped += 1
            continue

        match = OLD_PATH_PATTERN.match(normalized_path)
        filename = match.group(1) if match else os.path.basename(normalized_path)
        extension = os.path.splitext(filename)[1].lower()

        new_path = None
        if category_name:
            category_files = list_category_files(category_name)
            if filename and category_files:
                candidate = os.path.join(MENU_IMAGE_DIR, category_name, filename)
                if os.path.isfile(candidate):
                    new_path = f"{settings.MEDIA_URL.rstrip('/')}/{category_name}/{filename}"
                else:
                    same_ext = [path for path in category_files if os.path.splitext(path)[1].lower() == extension]
                    if len(same_ext) == 1:
                        new_path = to_web_path(same_ext[0])
                    elif len(category_files) == 1:
                        new_path = to_web_path(category_files[0])
                    elif category_files:
                        newest = category_files[-1]
                        new_path = to_web_path(newest)

        if not new_path and filename:
            matches = find_file_in_tree(filename)
            if len(matches) == 1:
                new_path = to_web_path(matches[0])

        if new_path:
            Product.objects.filter(id=product.id).update(image_path=new_path)
            updated += 1
        else:
            Product.objects.filter(id=product.id).update(image_path=None)
            nullified += 1

    print("Repair summary")
    print(f"  updated: {updated}")
    print(f"  nullified: {nullified}")
    print(f"  skipped: {skipped}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
