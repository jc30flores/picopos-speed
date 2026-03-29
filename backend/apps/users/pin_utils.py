import re

from django.contrib.auth import get_user_model
from django.contrib.auth.hashers import check_password

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
        if check_password(pin, user.password):
            matches.append(user)
    return matches
