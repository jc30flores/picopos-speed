from django.db import connection
from django.http import JsonResponse
from django.views.decorators.http import require_safe

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
    return JsonResponse({"status": "ready", "database": "ok"})
