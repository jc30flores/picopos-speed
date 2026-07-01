from unittest.mock import Mock, patch

from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from requests.exceptions import RequestException
from io import StringIO

from apps.dte.monitor import DTEHealthMonitor, STATE_DOWN, STATE_UP


@override_settings(
    DTE_BASE_URL="https://dte.picodegallo.com",
    DTE_API_TOKEN="real-token-value-123456",
    DTE_HEALTH_ENDPOINT="/health",
    DTE_HEALTH_TIMEOUT_SECONDS=1,
)
class DTEHealthMonitorResilienceTests(SimpleTestCase):
    @patch("apps.dte.monitor.requests.post")
    @patch("apps.dte.monitor.requests.get")
    def test_monitor_marks_down_on_dns_failure_without_crashing(self, mock_get, mock_post):
        mock_get.side_effect = RequestException("Temporary failure in name resolution")
        monitor = DTEHealthMonitor()
        snapshot = monitor.check_once(force_log=True)
        self.assertEqual(snapshot.state, STATE_DOWN)
        mock_post.assert_not_called()

    @patch("apps.dte.monitor.requests.post")
    @patch("apps.dte.monitor.requests.get")
    def test_monitor_treats_factura_422_as_reachable(self, mock_get, mock_post):
        mock_get.return_value = Mock(status_code=200, text="ok")
        mock_post.return_value = Mock(status_code=422, text='{"detail":"missing dte"}')
        monitor = DTEHealthMonitor()
        snapshot = monitor.check_once(force_log=True)
        self.assertEqual(snapshot.state, STATE_UP)


@override_settings(
    DTE_BASE_URL="replace-with-dte-api-base-url",
    DTE_API_TOKEN="replace-with-dte-api-token",
    DTE_HEALTH_ENDPOINT="/health",
    DTE_CONFIG_PENDING_BACKOFF_SECONDS=60,
)
class DTEPlaceholderConfigTests(SimpleTestCase):
    @patch("apps.dte.monitor.requests.post")
    @patch("apps.dte.monitor.requests.get")
    def test_monitor_does_not_call_invalid_placeholder_url(self, mock_get, mock_post):
        monitor = DTEHealthMonitor()
        snapshot = monitor.check_once(force_log=True)
        self.assertEqual(snapshot.state, STATE_DOWN)
        self.assertIn("CONFIG_PENDING", snapshot.health_body)
        mock_get.assert_not_called()
        mock_post.assert_not_called()

    @patch("apps.dte.management.commands.dte_monitor.check_health_now")
    def test_dte_monitor_command_does_not_call_invalid_placeholder_url(self, mock_check):
        out = StringIO()
        call_command("dte_monitor", "--once", stdout=out)
        self.assertIn("CONFIG_PENDING", out.getvalue())
        mock_check.assert_not_called()

    @patch("apps.dte.management.commands.dte_outbox_worker.process_pending_outbox")
    def test_dte_worker_does_not_call_invalid_placeholder_url(self, mock_process):
        out = StringIO()
        call_command("dte_outbox_worker", "--once", stdout=out)
        self.assertIn("CONFIG_PENDING", out.getvalue())
        mock_process.assert_not_called()
