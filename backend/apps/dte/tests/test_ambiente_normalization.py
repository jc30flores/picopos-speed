from django.test import SimpleTestCase
import os

from apps.dte.services.dte_service import DTEPreflightError
from apps.dte.services.dte_service import _normalize_ambiente_value
from apps.dte.services.orchestrator import _normalize_ambiente, _ambiente


class AmbienteNormalizationTests(SimpleTestCase):
    def test_dte_service_normalizes_ambiente_values(self):
        self.assertEqual(_normalize_ambiente_value("00"), "00")
        self.assertEqual(_normalize_ambiente_value("test"), "00")
        self.assertEqual(_normalize_ambiente_value("01"), "01")
        self.assertEqual(_normalize_ambiente_value("prod"), "01")
        self.assertEqual(_normalize_ambiente_value("INVALID"), "00")

    def test_normalize_basic_values(self):
        self.assertEqual(_normalize_ambiente("00"), "00")
        self.assertEqual(_normalize_ambiente("01"), "01")
        self.assertEqual(_normalize_ambiente("prod"), "01")

    def test_force_prod_flag(self):
        previous = os.environ.get("DTE_REQUIRE_AMBIENTE_01")
        previous_env = os.environ.get("DTE_AMBIENTE")
        try:
            os.environ["DTE_REQUIRE_AMBIENTE_01"] = "1"
            os.environ["DTE_AMBIENTE"] = "00"
            self.assertEqual(_ambiente(), "01")
        finally:
            if previous is None:
                os.environ.pop("DTE_REQUIRE_AMBIENTE_01", None)
            else:
                os.environ["DTE_REQUIRE_AMBIENTE_01"] = previous
            if previous_env is None:
                os.environ.pop("DTE_AMBIENTE", None)
            else:
                os.environ["DTE_AMBIENTE"] = previous_env

    def test_invalid_environment_value_raises_preflight(self):
        previous_env = os.environ.get("DTE_AMBIENTE")
        try:
            os.environ["DTE_AMBIENTE"] = "INVALID_ENV"
            with self.assertRaises(DTEPreflightError):
                _ambiente()
        finally:
            if previous_env is None:
                os.environ.pop("DTE_AMBIENTE", None)
            else:
                os.environ["DTE_AMBIENTE"] = previous_env
