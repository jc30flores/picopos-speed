from django.urls import path
from apps.printing import views

urlpatterns = [
    path("jobs/", views.PrintJobListCreateView.as_view(), name="print-jobs"),
    path("jobs/refund/", views.RefundPrintJobCreateView.as_view(), name="print-jobs-refund"),
    path("jobs/<int:pk>/", views.PrintJobDetailView.as_view(), name="print-job-detail"),
    path("jobs/<int:pk>/mark-printed/", views.PrintJobMarkPrintedView.as_view(), name="print-job-mark-printed"),
]
