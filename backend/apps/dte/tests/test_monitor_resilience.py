from unittest.mock import Mock, patch

from django.test import TestCase, override_settings
from requests.exceptions import RequestException

from apps.dte.monitor import DTEHealthMonitor, STATE_DOWN, STATE_UP


@override_settings(
    DTE_BASE_URL="https://example.test",
    DTE_HEALTH_ENDPOINT="/health",
    DTE_HEALTH_TIMEOUT_SECONDS=1,
)
class DTEHealthMonitorResilienceTests(TestCase):
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
