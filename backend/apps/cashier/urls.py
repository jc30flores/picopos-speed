from django.urls import path
from apps.cashier import views

urlpatterns = [
    path("registers/", views.RegisterListCreateView.as_view(), name="cashier-registers"),
    path("session/current/", views.CashSessionCurrentView.as_view(), name="cashier-session-current"),
    path("session/open/", views.CashSessionOpenView.as_view(), name="cashier-session-open"),
    path("session/close/", views.CashSessionCloseView.as_view(), name="cashier-session-close"),
    path("session/history/", views.CashSessionHistoryView.as_view(), name="cashier-session-history"),
    path("sessions/", views.CashSessionListView.as_view(), name="cashier-sessions"),
    path("sessions/<int:pk>/", views.CashSessionDetailView.as_view(), name="cashier-session-detail"),
    path("sessions/<int:pk>/ticket.pdf", views.CashSessionTicketPDFView.as_view(), name="cashier-session-ticket-pdf"),
    path("transactions/", views.CashTransactionListCreateView.as_view(), name="cashier-transactions"),
    path("drawer/open/", views.CashDrawerOpenView.as_view(), name="cashier-drawer-open"),
    path("drawer/status/", views.CashDrawerStatusView.as_view(), name="cashier-drawer-status"),
    # legacy
    path("shifts/open/", views.ShiftOpenView.as_view(), name="cashier-shift-open"),
    path("shifts/current/", views.ShiftCurrentView.as_view(), name="cashier-shift-current"),
    path("shifts/<int:pk>/close/", views.ShiftCloseView.as_view(), name="cashier-shift-close"),
    path("shifts/<int:pk>/summary/", views.ShiftSummaryView.as_view(), name="cashier-shift-summary"),
    path("shifts/<int:pk>/closeout-printjob/", views.ShiftCloseoutPrintJobView.as_view(), name="cashier-shift-closeout"),
]
