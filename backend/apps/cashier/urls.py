from django.urls import path
from apps.cashier import views

urlpatterns = [
    path("session/current/", views.CashSessionCurrentView.as_view(), name="cashier-session-current"),
    path("session/open/", views.CashSessionOpenView.as_view(), name="cashier-session-open"),
    path("session/close/", views.CashSessionCloseView.as_view(), name="cashier-session-close"),
    path("transactions/", views.CashTransactionListCreateView.as_view(), name="cashier-transactions"),
    path("registers/", views.RegisterListCreateView.as_view(), name="cashier-registers"),
    path("shifts/open/", views.ShiftOpenView.as_view(), name="cashier-shift-open"),
    path("shifts/current/", views.ShiftCurrentView.as_view(), name="cashier-shift-current"),
    path("shifts/<int:pk>/close/", views.ShiftCloseView.as_view(), name="cashier-shift-close"),
    path("shifts/<int:pk>/summary/", views.ShiftSummaryView.as_view(), name="cashier-shift-summary"),
    path("shifts/<int:pk>/closeout-printjob/", views.ShiftCloseoutPrintJobView.as_view(), name="cashier-shift-closeout"),
]
