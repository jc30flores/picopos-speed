from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Modifier, ModifierGroup, Product
from apps.orders.models import Order, OrderItem


class AdminMenuOpsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.admin = User.objects.create_user(username="admin", password="x", role="admin", is_active=True)
        self.client.force_authenticate(user=self.admin)
        self.category = Category.objects.create(name="COMIDA")

    def test_delete_category_with_products_returns_409(self):
        Product.objects.create(name="Item", description="", price=Decimal("1.00"), category=self.category, available=True)
        response = self.client.delete(f"/api/menu/categories/{self.category.id}/")
        self.assertEqual(response.status_code, 409)

    def test_delete_product_with_history_archives(self):
        product = Product.objects.create(name="Item", description="", price=Decimal("2.00"), category=self.category, available=True)
        branch = Branch.objects.create(name="B", code="B")
        service_type = ServiceType.objects.create(key="dine-in", label="En local")
        order = Order.objects.create(order_number=1, branch=branch, service_type=service_type, total=Decimal("2.00"))
        OrderItem.objects.create(order=order, product=product, product_name_snapshot="Item", price_snapshot=Decimal("2.00"), quantity=1)

        response = self.client.delete(f"/api/menu/products/{product.id}/")
        self.assertEqual(response.status_code, 200)
        product.refresh_from_db()
        self.assertTrue(product.is_archived)

        list_response = self.client.get("/api/menu/products/")
        self.assertFalse(any(item["id"] == product.id for item in list_response.json()))

    def test_reorder_modifier_group_options(self):
        group = ModifierGroup.objects.create(name="Extras", required=False)
        m1 = Modifier.objects.create(group=group, name="A", price=Decimal("1.00"), sort_order=0)
        m2 = Modifier.objects.create(group=group, name="B", price=Decimal("2.00"), sort_order=1)
        response = self.client.patch(
            f"/api/menu/modifier-groups/{group.id}/options/reorder/",
            {"ordered_ids": [m2.id, m1.id]},
            format="json",
        )
        self.assertEqual(response.status_code, 200)
        m1.refresh_from_db(); m2.refresh_from_db()
        self.assertEqual((m2.sort_order, m1.sort_order), (0, 1))

    def test_update_modifier_group_updates_existing_without_duplicates(self):
        group = ModifierGroup.objects.create(name="Arroz", required=False)
        m1 = Modifier.objects.create(group=group, name="Casero", price=Decimal("0.00"), sort_order=0)
        m2 = Modifier.objects.create(group=group, name="Integral", price=Decimal("0.50"), sort_order=1)

        response = self.client.patch(
            f"/api/menu/modifier-groups/{group.id}/",
            {
                "name": "Arroz",
                "required": False,
                "min_selection": 0,
                "max_selection": 1,
                "modifiers": [
                    {"id": m1.id, "name": "Casero", "price": "0.00", "is_active": True},
                    {"id": m2.id, "name": "Integral Premium", "price": "0.75", "is_active": True},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(Modifier.objects.filter(group=group).count(), 2)
        self.assertTrue(Modifier.objects.filter(group=group, name="Integral Premium").exists())

    def test_update_modifier_group_removes_missing_options(self):
        group = ModifierGroup.objects.create(name="Frijoles", required=False)
        keep = Modifier.objects.create(group=group, name="Negros", price=Decimal("0.00"), sort_order=0)
        Modifier.objects.create(group=group, name="Rojos", price=Decimal("0.00"), sort_order=1)

        response = self.client.patch(
            f"/api/menu/modifier-groups/{group.id}/",
            {
                "name": "Frijoles",
                "required": False,
                "min_selection": 0,
                "max_selection": 1,
                "modifiers": [
                    {"id": keep.id, "name": "Negros", "price": "0.00", "is_active": True},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        self.assertEqual(list(Modifier.objects.filter(group=group).values_list("name", flat=True)), ["Negros"])

    def test_update_modifier_group_duplicate_name_returns_400(self):
        group = ModifierGroup.objects.create(name="Salsas", required=False)
        m1 = Modifier.objects.create(group=group, name="Verde", price=Decimal("0.00"), sort_order=0)
        m2 = Modifier.objects.create(group=group, name="Roja", price=Decimal("0.00"), sort_order=1)

        response = self.client.patch(
            f"/api/menu/modifier-groups/{group.id}/",
            {
                "name": "Salsas",
                "required": False,
                "min_selection": 0,
                "max_selection": 2,
                "modifiers": [
                    {"id": m1.id, "name": "Verde", "price": "0.00", "is_active": True},
                    {"id": m2.id, "name": "Verde", "price": "0.00", "is_active": True},
                ],
            },
            format="json",
        )
        self.assertEqual(response.status_code, 400)

    def test_modifier_group_name_is_normalized_to_uppercase(self):
        response = self.client.post(
            "/api/menu/modifier-groups/",
            {
                "name": "  salsas   premium ",
                "required": False,
                "min_selection": 0,
                "max_selection": 1,
                "modifiers": [{"name": "  salsa verde ", "price": "0.00", "is_active": True}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 201, response.data)
        self.assertEqual(response.data["name"], "SALSAS PREMIUM")
        self.assertEqual(response.data["modifiers"][0]["name"], "SALSA VERDE")

    def test_modifier_group_duplicate_case_insensitive_returns_400(self):
        ModifierGroup.objects.create(name="SALSAS", required=False)

        response = self.client.post(
            "/api/menu/modifier-groups/",
            {
                "name": "  salsas ",
                "required": False,
                "min_selection": 0,
                "max_selection": 1,
                "modifiers": [{"name": "ROJA", "price": "0.00", "is_active": True}],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Ya existe un grupo de modificadores con ese nombre.", str(response.data))

    def test_delete_modifier_group_assigned_to_product_unassigns_and_deletes(self):
        product = Product.objects.create(name="Item", description="", price=Decimal("2.00"), category=self.category, available=True)
        group = ModifierGroup.objects.create(name="Extras", required=False)
        product.modifier_groups.add(group)

        response = self.client.delete(f"/api/menu/modifier-groups/{group.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(ModifierGroup.objects.filter(id=group.id).exists())
        product.refresh_from_db()
        self.assertFalse(product.modifier_groups.filter(id=group.id).exists())

    def test_upload_images_for_modifier_group_and_option(self):
        group = ModifierGroup.objects.create(name="Salsas", required=False)
        option = Modifier.objects.create(group=group, name="Verde", price=Decimal("0.00"), sort_order=0)

        group_image = SimpleUploadedFile("grupo.png", b"fakepngcontent", content_type="image/png")
        option_image = SimpleUploadedFile("opcion.png", b"fakepngcontent", content_type="image/png")

        group_response = self.client.patch(
            f"/api/menu/modifier-groups/{group.id}/image/",
            {"image": group_image},
            format="multipart",
        )
        option_response = self.client.patch(
            f"/api/menu/modifiers/{option.id}/image/",
            {"image": option_image},
            format="multipart",
        )

        self.assertEqual(group_response.status_code, 200, group_response.data)
        self.assertEqual(option_response.status_code, 200, option_response.data)

        group.refresh_from_db()
        option.refresh_from_db()
        self.assertTrue(group.image_path)
        self.assertTrue(option.image_path)

    def test_update_modifier_group_missing_existing_id_returns_clear_400(self):
        group = ModifierGroup.objects.create(name="Guarniciones", required=False)
        Modifier.objects.create(group=group, name="Chips", price=Decimal("0.00"), sort_order=0)

        response = self.client.patch(
            f"/api/menu/modifier-groups/{group.id}/",
            {
                "name": "Guarniciones",
                "required": False,
                "min_selection": 0,
                "max_selection": 1,
                "modifiers": [
                    {"name": "Chips", "price": "0.00", "is_active": True},
                ],
            },
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("Incluye el campo 'id'", str(response.data))
