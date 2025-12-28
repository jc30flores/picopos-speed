from django.core.management.base import BaseCommand
from apps.menu.models import Category, Product
from apps.orders.models import Order


class Command(BaseCommand):
    help = "Run basic ORM checks to ensure API models are accessible."

    def handle(self, *args, **options):
        self.stdout.write(f"Categories: {Category.objects.count()}")
        self.stdout.write(f"Products: {Product.objects.count()}")
        self.stdout.write(f"Orders: {Order.objects.count()}")
