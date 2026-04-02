from concurrent.futures import ThreadPoolExecutor

from django.test import TransactionTestCase

from apps.core.models import Branch
from apps.dte.services.control import reserve_next_control


class DTEControlCounterConcurrencyTests(TransactionTestCase):
    reset_sequences = True

    def setUp(self):
        self.branch = Branch.objects.create(name="Main", code="MAIN")

    def test_reserve_next_control_is_unique_under_concurrency(self):
        def run_once(_):
            return reserve_next_control(branch=self.branch, document_type="CF_01", series="X001X001")

        with ThreadPoolExecutor(max_workers=8) as pool:
            numbers = list(pool.map(run_once, range(12)))

        self.assertEqual(len(numbers), 12)
        self.assertEqual(len(set(numbers)), 12)
