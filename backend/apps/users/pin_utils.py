import re

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password

from apps.users.models import UserProfile

PIN_REGEX = re.compile(r"^\d{6}$")


def is_valid_pin_format(value: str) -> bool:
    return bool(PIN_REGEX.fullmatch(str(value or "")))


def find_active_users_matching_pin(pin: str, *, exclude_user_id: int | None = None):
    user_model = get_user_model()
    users = user_model.objects.filter(is_active=True)
    if exclude_user_id is not None:
        users = users.exclude(id=exclude_user_id)

    matches = []
    for user in users.only("id", "password", "username", "email", "is_active"):
        if user_matches_pin(user, pin):
            matches.append(user)
    return matches


def user_matches_pin(user, pin: str) -> bool:
    profile = UserProfile.objects.filter(user_id=user.id).only("pin_hash").first()
    if profile and profile.pin_hash and check_password(pin, profile.pin_hash):
        return True
    return check_password(pin, user.password)
