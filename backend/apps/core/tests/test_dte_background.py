from io import StringIO
from unittest import mock
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from apps.dte.apps import DTEConfig

class DTEBackgroundModeTests(SimpleTestCase):
    @override_settings(DTE_BACKGROUND_MODE="external")
    @mock.patch.dict("os.environ", {"RUN_MAIN": "true"})
    def test_external_does_not_start_ready_workers(self):
        config = DTEConfig("dte", mock.MagicMock())
        config.path = "/tmp"
        with mock.patch("apps.dte.monitor.start_monitor") as monitor, mock.patch("apps.dte.outbox.start_outbox_worker") as outbox:
            config.ready()
        monitor.assert_not_called()
        outbox.assert_not_called()

    @override_settings(DTE_BACKGROUND_MODE="disabled")
    @mock.patch.dict("os.environ", {"RUN_MAIN": "true"})
    def test_disabled_does_not_start_ready_workers(self):
        config = DTEConfig("dte", mock.MagicMock())
        config.path = "/tmp"
        with mock.patch("apps.dte.monitor.start_monitor") as monitor, mock.patch("apps.dte.outbox.start_outbox_worker") as outbox:
            config.ready()
        monitor.assert_not_called()
        outbox.assert_not_called()

    @override_settings(DTE_BACKGROUND_MODE="legacy")
    @mock.patch.dict("os.environ", {"RUN_MAIN": "true"})
    def test_legacy_starts_existing_ready_workers(self):
        config = DTEConfig("dte", mock.MagicMock())
        config.path = "/tmp"
        with mock.patch("apps.dte.monitor.start_monitor") as monitor, mock.patch("apps.dte.outbox.start_outbox_worker") as outbox:
            config.ready()
        monitor.assert_called_once()
        outbox.assert_called_once()

    @override_settings(DTE_BACKGROUND_MODE="external", DTE_BASE_URL="https://dte.example.test", DTE_API_TOKEN="placeholder", DTE_API_AUTH_HEADER="Authorization", DTE_API_AUTH_PREFIX="Bearer", DTE_LOG_DIR="/tmp/dte", DTE_MONITOR_ENABLED=True, DTE_OUTBOX_WORKER_ENABLED=True, DTE_MAX_RETRIES=5)
    def test_check_runtime_config_reports_background_mode_json(self):
        out = StringIO()
        call_command("check_runtime_config", "--json", stdout=out)
        text = out.getvalue()
        self.assertIn('"dte_background_mode": "external"', text)
        self.assertNotIn("placeholder", text)
