from decimal import Decimal

from django.contrib.auth import get_user_model
from django.test import TestCase
from django.test.utils import override_settings
from django.core.files.uploadedfile import SimpleUploadedFile
from rest_framework.test import APIClient

from apps.core.models import Branch, ServiceType
from apps.menu.models import Category, Modifier, ModifierGroup, Product, PriceChangeAudit
from apps.menu.serializers import CategorySerializer
from apps.orders.models import Order, OrderItem


class AdminMenuOpsTests(TestCase):
    def setUp(self):
        self.client = APIClient()
        User = get_user_model()
        self.admin = User.objects.create_user(username="admin", password="x", role="admin", is_active=True)
        self.client.force_authenticate(user=self.admin)
        self.category = Category.objects.create(name="COMIDA")

    def test_delete_category_with_active_products_returns_409_with_names(self):
        Product.objects.create(name="PAPAS FRITAS", description="", price=Decimal("1.00"), category=self.category, available=True, is_archived=False)
        Product.objects.create(name="PLATO DE PECHUGA", description="", price=Decimal("2.00"), category=self.category, available=True, is_archived=False)

        response = self.client.delete(f"/api/menu/categories/{self.category.id}/")

        self.assertEqual(response.status_code, 409)
        self.assertIn("detail", response.data)
        self.assertEqual(
            response.data["detail"],
            "No se puede eliminar la categoría porque tiene productos activos asociados.",
        )
        self.assertEqual(
            response.data["active_products"],
            ["PAPAS FRITAS", "PLATO DE PECHUGA"],
        )
        self.assertTrue(Category.objects.filter(id=self.category.id).exists())

    def test_delete_category_with_only_archived_products_reassigns_and_deletes(self):
        Product.objects.create(
            name="ARCHIVADO 1",
            description="",
            price=Decimal("1.00"),
            category=self.category,
            available=False,
            is_archived=True,
        )
        Product.objects.create(
            name="ARCHIVADO 2",
            description="",
            price=Decimal("2.00"),
            category=self.category,
            available=False,
            is_archived=True,
        )

        response = self.client.delete(f"/api/menu/categories/{self.category.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Category.objects.filter(id=self.category.id).exists())
        fallback = Category.objects.get(name="SIN CATEGORÍA")
        self.assertTrue(fallback.is_hidden)
        self.assertEqual(Product.objects.filter(category=fallback, is_archived=True).count(), 2)

    def test_delete_category_without_products_returns_204(self):
        response = self.client.delete(f"/api/menu/categories/{self.category.id}/")

        self.assertEqual(response.status_code, 204)
        self.assertFalse(Category.objects.filter(id=self.category.id).exists())



    def test_categories_endpoint_returns_json_list(self):
        response = self.client.get("/api/menu/categories/")

        self.assertEqual(response.status_code, 200)
        self.assertIsInstance(response.data, list)

    def test_category_serializer_does_not_expose_effective_price(self):
        fields = CategorySerializer().get_fields()

        self.assertNotIn("effective_price", fields)

    def test_list_categories_hides_system_categories_by_default(self):
        Category.objects.create(name="SIN CATEGORÍA (ARCHIVADOS)", is_hidden=True)

        response = self.client.get("/api/menu/categories/")

        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.data]
        self.assertNotIn("SIN CATEGORÍA (ARCHIVADOS)", names)

    def test_list_categories_include_hidden_for_admin(self):
        Category.objects.create(name="SIN CATEGORÍA (ARCHIVADOS)", is_hidden=True)

        response = self.client.get("/api/menu/categories/?include_hidden=1")

        self.assertEqual(response.status_code, 200)
        names = [item["name"] for item in response.data]
        self.assertIn("SIN CATEGORÍA (ARCHIVADOS)", names)


    def test_reorder_categories_persists_order(self):
        c2 = Category.objects.create(name="BEBIDAS", position=1)
        c3 = Category.objects.create(name="POSTRES", position=2)

        response = self.client.patch(
            "/api/menu/categories/reorder/",
            {"ordered_ids": [c3.id, self.category.id, c2.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        ordered = self.client.get("/api/menu/categories/")
        names = [item["name"] for item in ordered.data]
        self.assertEqual(names, ["POSTRES", "COMIDA", "BEBIDAS"])

    def test_reorder_categories_accepts_camel_case_payload(self):
        c2 = Category.objects.create(name="BEBIDAS", position=1)
        c3 = Category.objects.create(name="POSTRES", position=2)

        response = self.client.patch(
            "/api/menu/categories/reorder/",
            {"orderedIds": [c2.id, c3.id, self.category.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        ordered = self.client.get("/api/menu/categories/")
        names = [item["name"] for item in ordered.data]
        self.assertEqual(names, ["BEBIDAS", "POSTRES", "COMIDA"])

    def test_reorder_categories_with_duplicates_returns_400(self):
        c2 = Category.objects.create(name="BEBIDAS", position=1)

        response = self.client.patch(
            "/api/menu/categories/reorder/",
            {"ordered_ids": [self.category.id, c2.id, c2.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("duplicados", str(response.data).lower())

    def test_reorder_categories_with_empty_payload_returns_400(self):
        response = self.client.patch(
            "/api/menu/categories/reorder/",
            {"ordered_ids": []},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("vacío", str(response.data).lower())

    def test_reorder_categories_ignores_hidden_system_category(self):
        Category.objects.create(name="SIN CATEGORÍA", position=99, is_hidden=True)
        c2 = Category.objects.create(name="BEBIDAS", position=1)

        response = self.client.patch(
            "/api/menu/categories/reorder/",
            {"ordered_ids": [c2.id, self.category.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)

    def test_create_duplicate_category_returns_400_and_keeps_original_position(self):
        original = Category.objects.create(name="POSTRES", position=7)

        response = self.client.post(
            "/api/menu/categories/",
            {"name": "Postres"},
            format="json",
        )

        self.assertEqual(response.status_code, 400, response.data)
        self.assertIn("name", response.data)
        original.refresh_from_db()
        self.assertEqual(original.position, 7)


    def test_reorder_products_within_category_persists_order(self):
        p1 = Product.objects.create(name="A", description="", price=Decimal("1.00"), category=self.category, sort_order=0, available=True)
        p2 = Product.objects.create(name="B", description="", price=Decimal("1.00"), category=self.category, sort_order=1, available=True)
        p3 = Product.objects.create(name="C", description="", price=Decimal("1.00"), category=self.category, sort_order=2, available=True)

        response = self.client.post(
            "/api/menu/products/reorder/",
            {"category_id": self.category.id, "ordered_ids": [p3.id, p1.id, p2.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 200, response.data)
        ordered = self.client.get(f"/api/menu/products/?category_id={self.category.id}")
        names = [item["name"] for item in ordered.data]
        self.assertEqual(names, ["C", "A", "B"])

    def test_reorder_products_rejects_duplicate_ids(self):
        p1 = Product.objects.create(name="A", description="", price=Decimal("1.00"), category=self.category, sort_order=0, available=True)
        p2 = Product.objects.create(name="B", description="", price=Decimal("1.00"), category=self.category, sort_order=1, available=True)

        response = self.client.post(
            "/api/menu/products/reorder/",
            {"category_id": self.category.id, "ordered_ids": [p1.id, p2.id, p2.id]},
            format="json",
        )

        self.assertEqual(response.status_code, 400)
        self.assertIn("duplicados", str(response.data).lower())
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

    @override_settings(CODE_CHANGE_PRICE="1234")
    def test_change_price_with_wrong_code_returns_403(self):
        product = Product.objects.create(name="ITEM", description="", price=Decimal("2.00"), category=self.category, available=True)
        response = self.client.post(
            f"/api/menu/products/{product.id}/change-price/",
            {"code": "0000", "new_price": "3.00"},
            format="json",
        )
        self.assertEqual(response.status_code, 403)

    @override_settings(CODE_CHANGE_PRICE="1234")
    def test_change_price_with_correct_code_updates_and_creates_audit(self):
        branch = Branch.objects.create(name="Test Branch", code="TB")
        product = Product.objects.create(name="ITEM2", description="", price=Decimal("2.00"), category=self.category, available=True)
        response = self.client.post(
            f"/api/menu/products/{product.id}/change-price/?branch_id={branch.id}",
            {"code": "1234", "new_price": "3.25"},
            format="json",
        )
        self.assertEqual(response.status_code, 200, response.data)
        product.refresh_from_db()
        self.assertEqual(product.price, Decimal("3.25"))
        audit = PriceChangeAudit.objects.filter(product=product).latest("id")
        self.assertEqual(audit.old_price, Decimal("2.00"))
        self.assertEqual(audit.new_price, Decimal("3.25"))
        self.assertEqual(audit.reason, "emergency")
