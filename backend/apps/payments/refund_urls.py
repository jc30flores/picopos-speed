from django.urls import path
from apps.payments import views

urlpatterns = [
    path("", views.RefundListCreateView.as_view(), name="refunds"),
]
