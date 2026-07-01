from django.test import SimpleTestCase

from apps.dte.config import get_dte_config_status


class DTEConfigReadinessTests(SimpleTestCase):
    def test_placeholder_base_url_is_not_ready(self):
        status = get_dte_config_status("replace-with-dte-api-base-url", "real-token-value-123456")
        self.assertFalse(status.configured)
        self.assertEqual(status.reason, "placeholder_base_url")

    def test_valid_https_url_and_token_are_ready(self):
        status = get_dte_config_status("https://dte.picodegallo.com", "real-token-value-123456")
        self.assertTrue(status.configured)
        self.assertEqual(status.reason, "configured")
