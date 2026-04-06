from __future__ import annotations

from django.http import JsonResponse

from apps.core.role_access import is_api_path_allowed_for_role
from apps.users.models import UserProfile


class RolePathAccessMiddleware:
    def __init__(self, get_response):
        self.get_response = get_response

    def __call__(self, request):
        user = getattr(request, "user", None)
        if user and user.is_authenticated:
            profile = UserProfile.objects.filter(user=user, is_active=True).only("role").first()
            if profile and not is_api_path_allowed_for_role(profile.role, request.path):
                return JsonResponse({"detail": "Sin permisos"}, status=403)
        return self.get_response(request)
