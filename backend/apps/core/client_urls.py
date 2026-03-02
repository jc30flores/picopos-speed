from django.urls import path
from apps.core import views

urlpatterns = [
    path('', views.ClientListCreateView.as_view(), name='clients-list-create'),
    path('default-consumer-final/', views.ClientDefaultConsumerFinalView.as_view(), name='clients-default-consumer-final'),
    path('<int:pk>/', views.ClientDetailView.as_view(), name='clients-detail'),
    path('<int:pk>/set-consumer-final/', views.ClientSetConsumerFinalView.as_view(), name='clients-set-consumer-final'),
    path('geo/departments/', views.GeoDepartmentListView.as_view(), name='geo-departments'),
    path('geo/municipalities/', views.GeoMunicipalityListView.as_view(), name='geo-municipalities'),
    path('activities/', views.ActivityCatalogListView.as_view(), name='activities-catalog'),
]
