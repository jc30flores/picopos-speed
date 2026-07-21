from rest_framework.permissions import BasePermission, SAFE_METHODS


def _get_profile(user):
    if not user or not user.is_authenticated:
        return None
    from apps.users.models import UserProfile

    return UserProfile.objects.filter(user=user).first()


def _role_is(user, roles: set[str]) -> bool:
    profile = _get_profile(user)
    if not profile or not profile.is_active:
        return False
    return profile.role in roles


KITCHEN_ROLES = {"kitchen", "cocina"}
WAITER_ROLES = {"waiter", "mesero"}


def is_superadmin(user) -> bool:
    return _role_is(user, {"superadmin"})


def is_admin(user) -> bool:
    return bool(is_superadmin(user) or _role_is(user, {"admin"}))


def is_manager(user) -> bool:
    return bool(is_admin(user) or _role_is(user, {"manager"}))


def user_is_kitchen(user) -> bool:
    return _role_is(user, KITCHEN_ROLES)


def user_is_waiter(user) -> bool:
    return _role_is(user, WAITER_ROLES)


def user_can_view_kitchen(user) -> bool:
    return bool(is_superadmin(user) or _role_is(user, KITCHEN_ROLES | WAITER_ROLES | {"admin", "manager", "cashier"}))


def user_can_manage_kitchen_items(user) -> bool:
    return bool(is_superadmin(user) or _role_is(user, KITCHEN_ROLES | {"admin", "manager"}))


def user_can_mark_item_served(user) -> bool:
    return bool(is_superadmin(user) or _role_is(user, KITCHEN_ROLES | WAITER_ROLES | {"admin", "manager"}))


def user_can_access_table_pos(user) -> bool:
    return bool(is_superadmin(user) or _role_is(user, WAITER_ROLES | {"cashier", "admin", "manager"}))


def can_manage_features(user) -> bool:
    return bool(is_superadmin(user) or _role_is(user, {"admin"}))


ADMIN_MANAGED_FEATURE_KEYS = {
    "operation_mode",
    "default_pos_entry",
    "allow_table_merge",
    "allow_table_transfer",
    "allow_split_by_guest",
    "allow_split_by_item",
    "table_map_enabled",
    "inventory_stock_policy",
    "inventory_advanced_enabled",
    "pos_product_images_enabled",
    "cash_close_expected_totals_control_enabled",
    "cash_close_expected_totals_allowed_roles",
    "cash_close_expected_totals_visible_fields",
    "pos_quick_sales_button_mode",
    "pos_quick_sales_history_scope",
    "pos_quick_sales_history_window_minutes",
}


def user_can_manage_feature_key(user, key: str) -> bool:
    if is_superadmin(user):
        return True
    if _role_is(user, {"admin"}):
        return key in ADMIN_MANAGED_FEATURE_KEYS
    return False


def user_can_view_features(user) -> bool:
    return bool(is_superadmin(user) or _role_is(user, {"admin", "manager"}))


def can_manage_dte_settings(user) -> bool:
    return is_superadmin(user)


def can_manage_correlatives(user) -> bool:
    return is_superadmin(user)


def can_view_dte(user) -> bool:
    return is_superadmin(user)


class IsAuthenticatedAndActive(BasePermission):
    def has_permission(self, request, view):
        profile = _get_profile(request.user)
        return bool(profile and profile.is_active)


class IsAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_admin(request.user)


class IsSuperAdmin(BasePermission):
    def has_permission(self, request, view):
        return is_superadmin(request.user)


class IsManager(BasePermission):
    def has_permission(self, request, view):
        return _role_is(request.user, {"manager"})


class IsCashier(BasePermission):
    def has_permission(self, request, view):
        return _role_is(request.user, {"cashier"})


class IsKitchen(BasePermission):
    def has_permission(self, request, view):
        return user_is_kitchen(request.user)


class IsAdminOrManager(BasePermission):
    def has_permission(self, request, view):
        return bool(is_superadmin(request.user) or _role_is(request.user, {"admin", "manager"}))


class IsManagerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(is_superadmin(request.user) or _role_is(request.user, {"admin", "manager"}))


class IsCashierOrManagerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(is_superadmin(request.user) or _role_is(request.user, {"cashier", "admin", "manager"}))


class CanAccessTablePos(BasePermission):
    def has_permission(self, request, view):
        return user_can_access_table_pos(request.user)


class IsKitchenOrManagerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return user_can_manage_kitchen_items(request.user)


class IsKitchenOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(is_superadmin(request.user) or _role_is(request.user, KITCHEN_ROLES | {"admin"}))


class CanViewKitchen(BasePermission):
    def has_permission(self, request, view):
        return user_can_view_kitchen(request.user)


class CanManageKitchenItems(BasePermission):
    message = "No tienes permiso para operar cocina."

    def has_permission(self, request, view):
        if user_is_waiter(request.user):
            self.message = "El rol Mesero solo puede visualizar cocina."
            return False
        self.message = "No tienes permiso para operar cocina."
        return user_can_manage_kitchen_items(request.user)


class CanServeKitchenItems(BasePermission):
    message = "No tienes permiso para marcar pedidos como servidos."

    def has_permission(self, request, view):
        return user_can_mark_item_served(request.user)


class IsAuthenticatedOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return _role_is(request.user, {"admin", "manager", "cashier", "kitchen"})
