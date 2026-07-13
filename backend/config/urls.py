from django.contrib import admin
from django.urls import path, include
from django.conf import settings
from django.conf.urls.static import static
from apps.core.views import (
    AppearanceSettingsView,
    DTECorrelativeDetailView,
    DTECorrelativesView,
    DTEGlobalSettingsView,
    DTETestConnectionView,
    FeatureSettingsOptionsView,
    FeatureSettingsView,
    PublicAppearanceView,
    TicketLogoView,
    TicketSettingsView,
)

urlpatterns = [
    path("admin/", admin.site.urls),
    path("api/core/", include("apps.core.urls")),
    path("api/menu/", include("apps.menu.urls")),
    path("api/orders/", include("apps.orders.urls")),
    path("api/tables/", include("apps.orders.table_urls")),
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
    path("api/inventory/", include("apps.inventory.urls")),
    path("api/settings/features/", FeatureSettingsView.as_view(), name="settings-features"),
    path("api/settings/features/options/", FeatureSettingsOptionsView.as_view(), name="settings-features-options"),
    path("api/settings/appearance/", AppearanceSettingsView.as_view(), name="settings-appearance"),
    path("api/public/appearance/", PublicAppearanceView.as_view(), name="public-appearance"),
    path("api/settings/dte/", DTEGlobalSettingsView.as_view(), name="settings-dte"),
    path("api/settings/dte/correlatives/", DTECorrelativesView.as_view(), name="settings-dte-correlatives"),
    path("api/settings/dte/correlatives/initialize/", DTECorrelativesView.as_view(), name="settings-dte-correlatives-initialize"),
    path("api/settings/dte/correlatives/<int:pk>/", DTECorrelativeDetailView.as_view(), name="settings-dte-correlative-detail"),
    path("api/settings/dte/test-connection/", DTETestConnectionView.as_view(), name="settings-dte-test-connection"),
    path("api/settings/ticket/", TicketSettingsView.as_view(), name="settings-ticket"),
    path("api/settings/ticket/logo/", TicketLogoView.as_view(), name="settings-ticket-logo"),
]

if settings.DEBUG:
    urlpatterns += static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
