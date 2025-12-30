from django.urls import path
from apps.cashier import views

urlpatterns = [
    path("registers/", views.RegisterListCreateView.as_view(), name="cashier-registers"),
    path("shifts/open/", views.ShiftOpenView.as_view(), name="cashier-shift-open"),
    path("shifts/current/", views.ShiftCurrentView.as_view(), name="cashier-shift-current"),
    path("shifts/<int:pk>/close/", views.ShiftCloseView.as_view(), name="cashier-shift-close"),
    path("shifts/<int:pk>/summary/", views.ShiftSummaryView.as_view(), name="cashier-shift-summary"),
    path("shifts/<int:pk>/closeout-printjob/", views.ShiftCloseoutPrintJobView.as_view(), name="cashier-shift-closeout"),
]
