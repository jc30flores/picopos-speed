from __future__ import annotations

import logging
from io import BytesIO

from django.http import HttpResponse
from PIL import Image, ImageDraw, ImageFont, UnidentifiedImageError
from rest_framework.views import APIView

from apps.core.pwa_metadata import get_public_pwa_metadata, safe_hex, ticket_logo_path
from apps.core.pwa_views import etag_response, set_cache_headers


logger = logging.getLogger(__name__)


def _hex_to_rgb(value: str) -> tuple[int, int, int]:
    cleaned = safe_hex(value).lstrip("#")
    return int(cleaned[0:2], 16), int(cleaned[2:4], 16), int(cleaned[4:6], 16)


def _load_logo() -> Image.Image | None:
    path = ticket_logo_path()
    if not path:
        return None
    try:
        image = Image.open(path)
        image.load()
        return image.convert("RGBA")
    except (UnidentifiedImageError, OSError, ValueError):
        logger.warning("pwa.customer_logo_unusable path=%s", path, exc_info=True)
        return None


def _font(size: int):
    candidates = [
        "/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf",
        "/usr/share/fonts/truetype/liberation2/LiberationSans-Bold.ttf",
    ]
    for candidate in candidates:
        try:
            return ImageFont.truetype(candidate, size=size)
        except OSError:
            continue
    return ImageFont.load_default()


def _render_default_icon(size: int, theme_color: str) -> Image.Image:
    background = _hex_to_rgb(theme_color)
    canvas = Image.new("RGBA", (size, size), (*background, 255))
    draw = ImageDraw.Draw(canvas)
    label = "GP"
    font = _font(max(18, size // 3))
    bbox = draw.textbbox((0, 0), label, font=font)
    text_w = bbox[2] - bbox[0]
    text_h = bbox[3] - bbox[1]
    draw.text(((size - text_w) / 2, (size - text_h) / 2 - size * 0.02), label, fill=(255, 255, 255, 255), font=font)
    return canvas


def _render_png_icon(size: int, *, maskable: bool = False) -> bytes:
    metadata = get_public_pwa_metadata()
    theme_color = str(metadata["theme_color"])
    logo = _load_logo()
    if logo is None:
        canvas = _render_default_icon(size, theme_color)
    else:
        canvas = Image.new("RGBA", (size, size), (*_hex_to_rgb(theme_color), 255))
        safe_padding = 0.23 if maskable else 0.14
        max_side = int(size * (1 - safe_padding * 2))
        logo.thumbnail((max_side, max_side), Image.Resampling.LANCZOS)
        x = (size - logo.width) // 2
        y = (size - logo.height) // 2
        canvas.alpha_composite(logo, (x, y))
    output = BytesIO()
    canvas.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _render_customer_logo() -> bytes | None:
    logo = _load_logo()
    if logo is None:
        return None
    logo.thumbnail((1024, 512), Image.Resampling.LANCZOS)
    output = BytesIO()
    logo.save(output, format="PNG", optimize=True)
    return output.getvalue()


def _render_ico() -> bytes:
    images = [Image.open(BytesIO(_render_png_icon(size))).convert("RGBA") for size in (32, 48)]
    output = BytesIO()
    images[0].save(output, format="ICO", sizes=[(32, 32), (48, 48)], append_images=images[1:])
    return output.getvalue()


class PublicPwaIconView(APIView):
    authentication_classes = []
    permission_classes = []

    ICON_SPECS = {
        "icon-192.png": (192, "image/png", False),
        "icon-512.png": (512, "image/png", False),
        "icon-maskable-512.png": (512, "image/png", True),
        "apple-touch-icon.png": (180, "image/png", False),
        "favicon-32.png": (32, "image/png", False),
    }

    def get(self, request, icon_name: str):
        metadata = get_public_pwa_metadata()
        version = str(metadata["version"])
        not_modified = etag_response(request, version)
        if not_modified:
            return not_modified
        versioned = request.GET.get("v") == version
        if icon_name == "customer-logo.png":
            payload = _render_customer_logo()
            if payload is None:
                return HttpResponse(status=404)
            response = HttpResponse(payload, content_type="image/png")
            return set_cache_headers(response, version, max_age=86400, versioned=versioned)
        if icon_name == "favicon.ico":
            payload = _render_ico()
            response = HttpResponse(payload, content_type="image/x-icon")
            return set_cache_headers(response, version, max_age=86400, versioned=versioned)
        spec = self.ICON_SPECS.get(icon_name)
        if not spec:
            return HttpResponse(status=404)
        size, content_type, maskable = spec
        payload = _render_png_icon(size, maskable=maskable)
        response = HttpResponse(payload, content_type=content_type)
        return set_cache_headers(response, version, max_age=86400, versioned=versioned)
