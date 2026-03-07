from django.urls import path
from apps.core import views

urlpatterns = [
    path("branches/", views.BranchListView.as_view(), name="branches-list"),
    path("service-types/", views.ServiceTypeListView.as_view(), name="service-types"),
    path("order-types/", views.ServiceTypeAdminListCreateView.as_view(), name="order-types-list-create"),
    path("order-types/<int:pk>/", views.ServiceTypeAdminDetailView.as_view(), name="order-types-detail"),
    path("tax-config/active/", views.ActiveTaxConfigView.as_view(), name="tax-config-active"),
    path("feature-flags/", views.FeatureFlagListView.as_view(), name="feature-flags"),
    path("feature-flags/<int:pk>/", views.FeatureFlagDetailView.as_view(), name="feature-flag-detail"),
    path("customers/", views.CustomerListCreateView.as_view(), name="customers-list-create"),
    path("customers/<int:pk>/", views.CustomerDetailView.as_view(), name="customers-detail"),
    path("customers/default-consumer-final/", views.DefaultConsumerFinalView.as_view(), name="customers-default"),
    path("clients/", views.ClientListCreateView.as_view(), name="clients-list-create"),
    path("clients/<int:pk>/", views.ClientDetailView.as_view(), name="clients-detail"),
    path("clients/default-consumer-final/", views.ClientDefaultConsumerFinalView.as_view(), name="clients-default-consumer-final"),
    path("clients/<int:pk>/set-consumer-final/", views.ClientSetConsumerFinalView.as_view(), name="clients-set-consumer-final"),
    path("geo/departments/", views.GeoDepartmentListView.as_view(), name="geo-departments"),
    path("geo/municipalities/", views.GeoMunicipalityListView.as_view(), name="geo-municipalities"),
    path("activities/", views.ActivityCatalogListView.as_view(), name="activities-catalog"),
]
