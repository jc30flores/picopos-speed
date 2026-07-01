from io import StringIO
from unittest import mock
import apps.dte as dte_module
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from apps.dte.apps import DTEConfig

class DTEBackgroundModeTests(SimpleTestCase):
    def _config(self):
        return DTEConfig("apps.dte", dte_module)

    @override_settings(DTE_BACKGROUND_MODE="external")
    @mock.patch.dict("os.environ", {"RUN_MAIN": "true"})
    def test_external_does_not_start_ready_workers(self):
        config = self._config()
        with mock.patch("apps.dte.monitor.start_monitor") as monitor, mock.patch("apps.dte.outbox.start_outbox_worker") as outbox:
            config.ready()
        monitor.assert_not_called()
        outbox.assert_not_called()

    @override_settings(DTE_BACKGROUND_MODE="disabled")
    @mock.patch.dict("os.environ", {"RUN_MAIN": "true"})
    def test_disabled_does_not_start_ready_workers(self):
        config = self._config()
        with mock.patch("apps.dte.monitor.start_monitor") as monitor, mock.patch("apps.dte.outbox.start_outbox_worker") as outbox:
            config.ready()
        monitor.assert_not_called()
        outbox.assert_not_called()

    @override_settings(DTE_BACKGROUND_MODE="external")
    @mock.patch.dict("os.environ", {"RUN_MAIN": "true", "PICO_INSTALLER_PREFLIGHT": "1"})
    def test_preflight_suppresses_external_background_notice(self):
        config = self._config()
        with mock.patch("apps.dte.apps.logger.debug") as debug:
            config.ready()
        debug.assert_not_called()

    @override_settings(DTE_BACKGROUND_MODE="legacy")
    @mock.patch.dict("os.environ", {"RUN_MAIN": "true"})
    def test_legacy_starts_existing_ready_workers(self):
        config = self._config()
        with mock.patch("apps.dte.monitor.start_monitor") as monitor, mock.patch("apps.dte.outbox.start_outbox_worker") as outbox:
            config.ready()
        monitor.assert_called_once()
        outbox.assert_called_once()

    @override_settings(DTE_BACKGROUND_MODE="external", DTE_BASE_URL="https://dte.picodegallo.com", DTE_API_TOKEN="real-token-value-123456", DTE_API_AUTH_HEADER="Authorization", DTE_API_AUTH_PREFIX="Bearer", DTE_LOG_DIR="/tmp/dte", DTE_MONITOR_ENABLED=True, DTE_OUTBOX_WORKER_ENABLED=True, DTE_MAX_RETRIES=5)
    def test_check_runtime_config_reports_background_mode_json(self):
        out = StringIO()
        call_command("check_runtime_config", "--json", stdout=out)
        text = out.getvalue()
        self.assertIn('"dte_background_mode": "external"', text)
        self.assertNotIn("placeholder", text)
