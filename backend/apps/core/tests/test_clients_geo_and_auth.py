from django.contrib.auth import get_user_model
from django.db import connection
from django.test import TestCase
from rest_framework.test import APIClient

from apps.core.models import Customer
from apps.core.serializers import ClientSerializer


class GeoMunicipalityEndpointTests(TestCase):
    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS geo_departments (
                    code varchar(2) PRIMARY KEY,
                    name text NOT NULL,
                    normalized text,
                    updated_at timestamptz DEFAULT now() NOT NULL,
                    version integer DEFAULT 1 NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS geo_municipalities (
                    id integer PRIMARY KEY,
                    dept_code varchar(4) NOT NULL,
                    muni_code varchar(4) NOT NULL,
                    name text NOT NULL,
                    normalized text,
                    updated_at timestamptz DEFAULT now() NOT NULL,
                    version integer DEFAULT 1 NOT NULL
                )
                """
            )

    def setUp(self):
        self.client = APIClient()
        user = get_user_model().objects.create_user(username="geo_user", password="pw")
        self.client.force_authenticate(user)
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM geo_municipalities")
            cursor.execute("DELETE FROM geo_departments")
            cursor.execute("INSERT INTO geo_departments (code, name) VALUES ('12', 'SAN MIGUEL')")
            cursor.execute(
                "INSERT INTO geo_municipalities (id, dept_code, muni_code, name) VALUES (1, '12', '22', 'SAN MIGUEL')"
            )

    def test_municipalities_endpoint_returns_200_and_schema(self):
        response = self.client.get("/api/clients/geo/municipalities/?department_code=12")
        self.assertEqual(response.status_code, 200)
        self.assertTrue(isinstance(response.json(), list))
        payload = response.json()[0]
        self.assertIn("code", payload)
        self.assertIn("name", payload)
        self.assertEqual(payload["code"], "22")
        self.assertEqual(payload["department_code"], "12")


class AuthEndpointsTests(TestCase):
    def setUp(self):
        self.client = APIClient()

    def test_auth_me_anonymous_returns_401_or_expected(self):
        response = self.client.get("/api/auth/me/")
        self.assertIn(response.status_code, {401, 403})

    def test_csrf_endpoint_returns_200(self):
        response = self.client.get("/api/auth/csrf/")
        self.assertEqual(response.status_code, 200)
        self.assertEqual(response.json().get("detail"), "ok")


class ClientSerializerRulesTests(TestCase):
    databases = {"default"}

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        with connection.cursor() as cursor:
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS geo_departments (
                    code varchar(2) PRIMARY KEY,
                    name text NOT NULL,
                    normalized text,
                    updated_at timestamptz DEFAULT now() NOT NULL,
                    version integer DEFAULT 1 NOT NULL
                )
                """
            )
            cursor.execute(
                """
                CREATE TABLE IF NOT EXISTS geo_municipalities (
                    id integer PRIMARY KEY,
                    dept_code varchar(4) NOT NULL,
                    muni_code varchar(4) NOT NULL,
                    name text NOT NULL,
                    normalized text,
                    updated_at timestamptz DEFAULT now() NOT NULL,
                    version integer DEFAULT 1 NOT NULL
                )
                """
            )

    def setUp(self):
        with connection.cursor() as cursor:
            cursor.execute("DELETE FROM geo_municipalities")
            cursor.execute("DELETE FROM geo_departments")
            cursor.execute("INSERT INTO geo_departments (code, name) VALUES ('12', 'SAN MIGUEL')")
            cursor.execute(
                "INSERT INTO geo_municipalities (id, dept_code, muni_code, name) VALUES (73, '12', '22', 'SAN MIGUEL CENTRO')"
            )

    def test_serializer_cf_defaults(self):
        serializer = ClientSerializer(data={"full_name": "Cliente Rapido", "client_type": "CF"})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        data = serializer.validated_data
        self.assertEqual(data["dui"], "00000000-0")
        self.assertEqual(data["telefono"], "0000-0000")
        self.assertEqual(data["department_code"], "12")
        self.assertEqual(data["municipality_code"], "22")
        self.assertEqual(data["direccion"], "SAN MIGUEL")


    def test_serializer_cf_iva_exempt_persists(self):
        serializer = ClientSerializer(data={"full_name": "Cliente Exento", "client_type": "CF", "is_iva_exempt": True})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        customer = serializer.save()
        self.assertTrue(customer.is_iva_exempt)
        self.assertTrue(ClientSerializer(customer).data["is_iva_exempt"])

    def test_serializer_ccf_normalizes_iva_exempt_false(self):
        serializer = ClientSerializer(
            data={
                "full_name": "Empresa X",
                "company_name": "Empresa X",
                "client_type": "CCF",
                "nit": "06142803911012",
                "nrc": "123456",
                "phone": "71234567",
                "email": "empresa@example.com",
                "direccion": "SAN MIGUEL",
                "department_code": "12",
                "municipality_code": "22",
                "activity_code": "56101",
                "activity_description": "Restaurantes",
                "is_iva_exempt": True,
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        customer = serializer.save()
        self.assertFalse(customer.is_iva_exempt)

    def test_serializer_ccf_required(self):
        serializer = ClientSerializer(data={"full_name": "Empresa X", "client_type": "CCF"})
        self.assertFalse(serializer.is_valid())
        self.assertIn("nit", serializer.errors)
        self.assertIn("company_name", serializer.errors)
        self.assertIn("department_code", serializer.errors)

    def test_serializer_document_and_phone_normalization(self):
        serializer = ClientSerializer(
            data={
                "full_name": "Cliente",
                "client_type": "CF",
                "dui": "000000000",
                "phone": "71234567",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["dui"], "00000000-0")
        self.assertEqual(serializer.validated_data["telefono"], "7123-4567")

    def test_serializer_assigns_default_email_on_create(self):
        serializer = ClientSerializer(data={"full_name": "Cliente Rapido", "client_type": "CF", "email": ""})
        self.assertTrue(serializer.is_valid(), serializer.errors)
        instance = serializer.save()
        self.assertEqual(instance.correo, "facturasPDG23@gmail.com")

    def test_serializer_reassigns_default_email_on_update_when_cleared(self):
        customer = Customer.objects.create(full_name="Cliente Update", client_type="CF", correo="custom@example.com")
        serializer = ClientSerializer(instance=customer, data={"email": ""}, partial=True)
        self.assertTrue(serializer.is_valid(), serializer.errors)
        updated = serializer.save()
        self.assertEqual(updated.correo, "facturasPDG23@gmail.com")

    def test_serializer_ccf_uses_default_email_when_missing(self):
        serializer = ClientSerializer(
            data={
                "full_name": "Empresa X",
                "client_type": "CCF",
                "company_name": "Empresa X",
                "nit": "06141234567890",
                "nrc": "1234567",
                "phone": "71234567",
                "direccion": "Centro",
                "department_code": "12",
                "municipality_code": "22",
                "activity_code": "62010",
            }
        )
        self.assertTrue(serializer.is_valid(), serializer.errors)
        self.assertEqual(serializer.validated_data["correo"], "facturasPDG23@gmail.com")
