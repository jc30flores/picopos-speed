import os
from pathlib import Path
from unittest import mock
from django.core.management import call_command
from django.test import SimpleTestCase, override_settings
from django.urls import reverse
from django.db import connection
from io import StringIO

from config import env
from config.runtime import validate_hosts, origins

class EnvHelpersTests(SimpleTestCase):
    def test_bool_values_and_invalid(self):
        for raw in ["true", "yes", "1", "on"]:
            self.assertTrue(env.bool_value("X", environ={"X": raw}))
        for raw in ["false", "no", "0", "off"]:
            self.assertFalse(env.bool_value("X", environ={"X": raw}))
        with self.assertRaises(env.EnvConfigError):
            env.bool_value("X", environ={"X": "maybe"})

    def test_lists_absent_modes_dotenv_and_secret_errors(self):
        self.assertEqual(env.list_value("X", environ={"X": " a, b,,a "}), ["a", "b"])
        self.assertEqual(env.required_str("X", mode="legacy", default="fallback", environ={}), "fallback")
        with self.assertRaisesMessage(env.EnvConfigError, "Falta DB_PASSWORD") as ctx:
            env.required_str("DB_PASSWORD", mode="strict", environ={})
        self.assertNotIn("supersecret", str(ctx.exception))
        data = {}
        tmp = Path("/tmp/picopos-test.env")
        tmp.write_text("A=1\r\nA=2\r\nB = yes\r\n", encoding="utf-8")
        env.load_env_file(tmp, override=False, environ=data)
        self.assertEqual(data["A"], "1")
        env.load_env_file(tmp, override=True, environ=data)
        self.assertEqual(data["A"], "2")

class RuntimeConfigTests(SimpleTestCase):
    def test_hosts_and_origins_validation(self):
        self.assertEqual(validate_hosts(["localhost"], strict=True), ["localhost"])
        with self.assertRaises(env.EnvConfigError):
            validate_hosts(["https://example.com"], strict=True)
        with self.assertRaises(env.EnvConfigError):
            validate_hosts([], strict=True)
        with mock.patch.dict(os.environ, {"CORS_ALLOWED_ORIGINS":"http://localhost:8182", "CORS_ALLOWED_ORIGINS_EXTRA":"https://example.com"}, clear=False):
            self.assertEqual(origins("CORS_ALLOWED_ORIGINS", "CORS_ALLOWED_ORIGINS_EXTRA", [], strict=True), ["http://localhost:8182", "https://example.com"])
        with mock.patch.dict(os.environ, {"CSRF_TRUSTED_ORIGINS":"bad"}, clear=False):
            with self.assertRaises(env.EnvConfigError):
                origins("CSRF_TRUSTED_ORIGINS", "CSRF_TRUSTED_ORIGINS_EXTRA", [], strict=True)

class HealthTests(SimpleTestCase):
    def test_live(self):
        response = self.client.get("/api/health/live/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json(), {"status": "ok"})
        self.assertEqual(self.client.head("/api/health/live/").status_code, 200)
        self.assertEqual(self.client.post("/api/health/live/").status_code, 405)

    def test_ready_ok_and_error(self):
        cursor = mock.MagicMock()
        cursor.__enter__.return_value.fetchone.return_value = (1,)
        fake_connection = mock.MagicMock()
        fake_connection.cursor.return_value = cursor
        with mock.patch("apps.core.health.connection", fake_connection):
            response = self.client.get("/api/health/ready/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json()["database"], "ok")
        bad_connection = mock.MagicMock()
        bad_connection.cursor.side_effect = Exception("password=secret traceback")
        with mock.patch("apps.core.health.connection", bad_connection):
            response = self.client.get("/api/health/ready/")
        self.assertEqual(response.status_code, 503)
        body = response.content.decode()
        self.assertNotIn("secret", body)
        self.assertNotIn("traceback", body.lower())

class RuntimeCommandTests(SimpleTestCase):
    def test_human_and_json_output_no_secrets(self):
        out = StringIO()
        call_command("check_runtime_config", stdout=out)
        self.assertIn("[OK] DJANGO_CONFIG_MODE", out.getvalue())
        self.assertNotIn("diez2030", out.getvalue())
        out = StringIO()
        call_command("check_runtime_config", "--json", stdout=out)
        self.assertIn('"checks"', out.getvalue())

    @override_settings(DATABASES={"default":{"PASSWORD":"", "HOST":"", "PORT":"", "NAME":"", "USER":""}}, SECRET_KEY="dev-secret-key")
    def test_strict_fails(self):
        with self.assertRaises(Exception):
            call_command("check_runtime_config", "--strict", stdout=StringIO())
