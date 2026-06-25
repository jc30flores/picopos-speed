from django.urls import path
from apps.orders import table_views

urlpatterns = [
    path("areas/", table_views.DiningAreaListCreateView.as_view()),
    path("areas/<int:pk>/", table_views.DiningAreaDetailView.as_view()),
    path("", table_views.RestaurantTableListCreateView.as_view()),
    path("<int:pk>/", table_views.RestaurantTableDetailView.as_view()),
    path("layout/", table_views.TableLayoutView.as_view()),
    path("sessions/", table_views.TableSessionListCreateView.as_view()),
    path("sessions/<int:pk>/", table_views.TableSessionDetailView.as_view()),
    path("sessions/<int:pk>/send-to-kitchen/", table_views.TableSessionSendToKitchenView.as_view()),
    path("sessions/<int:pk>/merge/", table_views.TableSessionMergeView.as_view()),
    path("sessions/<int:pk>/move-items/", table_views.TableSessionMoveItemsView.as_view()),
]
