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


def is_superadmin(user) -> bool:
    return bool(getattr(user, "is_superuser", False) or _role_is(user, {"superadmin"}))


def is_admin(user) -> bool:
    return bool(is_superadmin(user) or _role_is(user, {"admin"}))


def is_manager(user) -> bool:
    return bool(is_admin(user) or _role_is(user, {"manager"}))


def can_manage_features(user) -> bool:
    return is_superadmin(user)


def can_manage_dte_settings(user) -> bool:
    return is_superadmin(user)


def can_manage_correlatives(user) -> bool:
    return is_superadmin(user)


def can_view_dte(user) -> bool:
    return bool(is_superadmin(user) or _role_is(user, {"admin", "manager", "cashier", "accountant"}))


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
        return _role_is(request.user, {"kitchen"})


class IsAdminOrManager(BasePermission):
    def has_permission(self, request, view):
        return bool(getattr(request.user, "is_superuser", False) or _role_is(request.user, {"admin", "manager"}))


class IsManagerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(getattr(request.user, "is_superuser", False) or _role_is(request.user, {"admin", "manager"}))


class IsCashierOrManagerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(getattr(request.user, "is_superuser", False) or _role_is(request.user, {"cashier", "admin", "manager"}))


class IsKitchenOrManagerOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return _role_is(request.user, {"kitchen", "admin", "manager"})


class IsKitchenOrAdmin(BasePermission):
    def has_permission(self, request, view):
        return bool(is_superadmin(request.user) or _role_is(request.user, {"kitchen", "admin"}))


class IsAuthenticatedOrReadOnly(BasePermission):
    def has_permission(self, request, view):
        if request.method in SAFE_METHODS:
            return True
        return _role_is(request.user, {"admin", "manager", "cashier", "kitchen"})
