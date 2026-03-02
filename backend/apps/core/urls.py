from django.urls import path
from apps.core import views

urlpatterns = [
    path("branches/", views.BranchListView.as_view(), name="branches-list"),
    path("service-types/", views.ServiceTypeListView.as_view(), name="service-types"),
    path("tax-config/active/", views.ActiveTaxConfigView.as_view(), name="tax-config-active"),
    path("feature-flags/", views.FeatureFlagListView.as_view(), name="feature-flags"),
    path("feature-flags/<int:pk>/", views.FeatureFlagDetailView.as_view(), name="feature-flag-detail"),
]
