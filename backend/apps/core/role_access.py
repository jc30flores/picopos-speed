from __future__ import annotations

import re

AUTH_ALLOWED_PREFIXES = (
    "/api/auth/csrf/",
    "/api/auth/login/",
    "/api/auth/pin-login/",
    "/api/auth/logout/",
    "/api/auth/me/",
)

ROLE_ALLOWED_PATH_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "kitchen": (
        re.compile(r"^/api/kitchen/"),
        re.compile(r"^/api/orders/kitchen/?$"),
        re.compile(r"^/api/orders/active/?$"),
        re.compile(r"^/api/orders/\d+/status/?$"),
        re.compile(r"^/api/core/service-types/?$"),
        re.compile(r"^/api/core/branches/?$"),
        re.compile(r"^/api/printing/jobs/?$"),
        re.compile(r"^/api/printing/jobs/\d+/?$"),
    ),
    "kiosk": (
        re.compile(r"^/api/menu/"),
        re.compile(r"^/api/orders/?$"),
        re.compile(r"^/api/orders/\d+/?$"),
        re.compile(r"^/api/core/service-types/?$"),
        re.compile(r"^/api/core/tax-config/active/?$"),
        re.compile(r"^/api/core/branches/?$"),
    ),
    "worker": (
        re.compile(r"^/api/employees/attendance/today/?$"),
        re.compile(r"^/api/employees/attendance/clock-in/?$"),
        re.compile(r"^/api/employees/attendance/break-start/?$"),
        re.compile(r"^/api/employees/attendance/break-end/?$"),
        re.compile(r"^/api/employees/attendance/clock-out/?$"),
        re.compile(r"^/api/employees/me/attendance/?$"),
    ),
}

ROLE_DENIED_PATH_PATTERNS: dict[str, tuple[re.Pattern[str], ...]] = {
    "cashier": (
        re.compile(r"^/api/reports/"),
        re.compile(r"^/api/cashier/session/history/?$"),
        re.compile(r"^/api/cashier/sessions/\d+/?$"),
        re.compile(r"^/api/cashier/sessions/\d+/ticket\.pdf/?$"),
    ),
    "manager": (
        re.compile(r"^/api/reports/sales-timeseries/?$"),
        re.compile(r"^/api/reports/sales-breakdown/?$"),
        re.compile(r"^/api/cashier/session/history/?$"),
        re.compile(r"^/api/cashier/sessions/\d+/ticket\.pdf/?$"),
    ),
}


def is_api_path_allowed_for_role(role: str, path: str) -> bool:
    if not path.startswith("/api/"):
        return True
    if any(path.startswith(prefix) for prefix in AUTH_ALLOWED_PREFIXES):
        return True
    denied_patterns = ROLE_DENIED_PATH_PATTERNS.get(role)
    if denied_patterns and any(pattern.match(path) for pattern in denied_patterns):
        return False
    patterns = ROLE_ALLOWED_PATH_PATTERNS.get(role)
    if not patterns:
        return True
    return any(pattern.match(path) for pattern in patterns)
