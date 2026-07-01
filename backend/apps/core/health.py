from django.conf import settings
from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_safe

from apps.dte.config import get_dte_config_status

@require_safe
def live(request):
    return JsonResponse({"status": "ok"})

@require_safe
def ready(request):
    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()
    except Exception:
        return JsonResponse({"status": "unavailable", "database": "error"}, status=503)
    dte_config = get_dte_config_status(getattr(settings, "DTE_BASE_URL", ""), getattr(settings, "DTE_API_TOKEN", ""))
    return JsonResponse({
        "status": "ready",
        "database": "ok",
        "dte": {
            "configured": dte_config.configured,
            "reason": dte_config.reason,
        },
    })
