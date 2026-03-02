from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/core/", include("apps.core.urls")),
    path("api/menu/", include("apps.menu.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("api/kitchen/", include("apps.kitchen.urls")),
    path("api/employees/", include("apps.employees.urls")),
    path("api/reports/", include("apps.reports.urls")),
    path("api/auth/", include("apps.users.urls")),
    path("api/payments/", include("apps.payments.urls")),
    path("api/refunds/", include("apps.payments.refund_urls")),
    path("api/printing/", include("apps.printing.urls")),
    path("api/cashier/", include("apps.cashier.urls")),
    path("api/dte/", include("apps.dte.urls")),
    path("api/clients/", include("apps.core.client_urls")),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
