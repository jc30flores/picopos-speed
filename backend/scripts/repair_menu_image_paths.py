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


def list_category_files(category_name: str) -> list[str]:
    category_dir = os.path.join(MENU_IMAGE_DIR, category_name)
    if not os.path.isdir(category_dir):
        return []
    return [
        os.path.join(category_dir, filename)
        for filename in os.listdir(category_dir)
        if os.path.isfile(os.path.join(category_dir, filename))
    ]


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
        match = OLD_PATH_PATTERN.match(image_path.strip())
        if not match:
            skipped += 1
            continue

        filename = match.group(1)
        category_name = (product.category.name or "").strip().upper() if product.category else ""
        candidate = os.path.join(MENU_IMAGE_DIR, category_name, filename)

        new_path = None
        if category_name and os.path.isfile(candidate):
            new_path = f"{settings.MEDIA_URL.rstrip('/')}/{category_name}/{filename}"
        else:
            matches = find_file_in_tree(filename)
            if len(matches) == 1:
                new_path = to_web_path(matches[0])
            elif category_name:
                category_files = list_category_files(category_name)
                if len(category_files) == 1:
                    new_path = to_web_path(category_files[0])

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
