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
        with self.assertRaises(ValueError):
            _normalize_ambiente("INVALID")

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

    def test_ambiente_uses_mh_when_dte_ambiente_missing(self):
        previous_dte = os.environ.get("DTE_AMBIENTE")
        previous_mh = os.environ.get("MH_AMBIENTE")
        try:
            os.environ.pop("DTE_AMBIENTE", None)
            os.environ["MH_AMBIENTE"] = "01"
            self.assertEqual(_ambiente(), "01")
        finally:
            if previous_dte is None:
                os.environ.pop("DTE_AMBIENTE", None)
            else:
                os.environ["DTE_AMBIENTE"] = previous_dte
            if previous_mh is None:
                os.environ.pop("MH_AMBIENTE", None)
            else:
                os.environ["MH_AMBIENTE"] = previous_mh

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
