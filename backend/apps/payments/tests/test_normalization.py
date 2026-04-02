from django.test import TestCase

from apps.payments.normalization import normalize_payment_method_code
from apps.core.service_types import normalize_service_type


class NormalizationTests(TestCase):
    def test_payment_method_aliases(self):
        self.assertEqual(normalize_payment_method_code("CARD"), "card_credit")
        self.assertEqual(normalize_payment_method_code("card_debit"), "card_debit")
        self.assertEqual(normalize_payment_method_code("PEDIDOSYA"), "pedidos_ya")

    def test_service_type_aliases(self):
        self.assertEqual(normalize_service_type("DINE IN"), "dine_in")
        self.assertEqual(normalize_service_type("dine-in"), "dine_in")
        self.assertEqual(normalize_service_type("para llevar"), "takeout")
