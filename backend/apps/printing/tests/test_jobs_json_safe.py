from datetime import datetime, timezone
from decimal import Decimal
from unittest.mock import patch

from django.test import SimpleTestCase

from apps.printing.services.jobs import create_print_job, json_safe


class PrintJobJsonSafeTests(SimpleTestCase):
    def test_json_safe_serializes_datetime_and_decimal(self):
        payload = {
            "when": datetime(2026, 4, 1, 12, 30, tzinfo=timezone.utc),
            "amount": Decimal("10.25"),
        }
        safe = json_safe(payload)
        self.assertEqual(safe["when"], "2026-04-01T12:30:00Z")
        self.assertEqual(safe["amount"], "10.25")

    @patch("apps.printing.services.jobs.PrintJob.objects.create")
    @patch("apps.printing.services.jobs.render_customer_ticket")
    def test_create_print_job_uses_json_safe_meta(self, render_mock, create_mock):
        render_mock.return_value = {
            "text": "ok",
            "html": "<pre>ok</pre>",
            "meta": {"receipt_context": {"order_datetime": datetime(2026, 4, 1, 12, 30, tzinfo=timezone.utc)}},
        }
        dummy_order = type("Order", (), {"id": 1})()

        create_print_job(dummy_order, "customer")

        called_meta = create_mock.call_args.kwargs["meta"]
        self.assertIsInstance(called_meta["receipt_context"]["order_datetime"], str)
