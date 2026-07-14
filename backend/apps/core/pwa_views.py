from __future__ import annotations

import json

from django.http import HttpResponse, HttpResponseNotModified, JsonResponse
from rest_framework.views import APIView

from apps.core.pwa_metadata import get_public_pwa_metadata


def etag_response(request, version: str) -> HttpResponseNotModified | None:
    etag = f'"{version}"'
    if request.headers.get("If-None-Match") == etag:
        response = HttpResponseNotModified()
        response["ETag"] = etag
        return response
    return None


def set_cache_headers(response: HttpResponse, version: str, max_age: int = 3600, versioned: bool = False) -> HttpResponse:
    if versioned:
        response["Cache-Control"] = f"public, max-age={max_age}, immutable"
    else:
        response["Cache-Control"] = "no-cache, max-age=0, must-revalidate"
    response["ETag"] = f'"{version}"'
    response["X-Branding-Version"] = version
    return response


class PublicPwaMetadataView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        metadata = get_public_pwa_metadata()
        response = JsonResponse(metadata)
        return set_cache_headers(response, str(metadata["version"]), max_age=0, versioned=False)


class PublicPwaManifestView(APIView):
    authentication_classes = []
    permission_classes = []

    def get(self, request):
        metadata = get_public_pwa_metadata()
        version = str(metadata["version"])
        not_modified = etag_response(request, version)
        if not_modified:
            return not_modified
        maskable_purpose = "any" if metadata.get("has_customer_logo") else "maskable"
        manifest = {
            "name": metadata["app_name"],
            "short_name": metadata["short_name"],
            "description": metadata["description"],
            "start_url": metadata["start_url"],
            "scope": metadata["scope"],
            "display": metadata["display"],
            "orientation": metadata["orientation"],
            "background_color": metadata["background_color"],
            "theme_color": metadata["theme_color"],
            "icons": [
                {"src": metadata["icon_192_url"], "sizes": "192x192", "type": "image/png", "purpose": "any"},
                {"src": metadata["icon_512_url"], "sizes": "512x512", "type": "image/png", "purpose": "any"},
                {"src": metadata["maskable_icon_url"], "sizes": "512x512", "type": "image/png", "purpose": maskable_purpose},
            ],
        }
        response = HttpResponse(
            json.dumps(manifest, ensure_ascii=False, separators=(",", ":")),
            content_type="application/manifest+json",
        )
        return set_cache_headers(response, version, max_age=300, versioned=request.GET.get("v") == version)
