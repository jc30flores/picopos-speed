from __future__ import annotations

import logging
from functools import lru_cache

from django.db import connection

LOGGER = logging.getLogger(__name__)


@lru_cache(maxsize=1)
def has_whatsapp_order_columns() -> bool:
    try:
        with connection.cursor() as cursor:
            table_names = connection.introspection.table_names(cursor)
            if "orders_order" not in table_names:
                return False
            description = connection.introspection.get_table_description(cursor, "orders_order")
    except Exception:  # noqa: BLE001
        return False
    names = {col.name for col in description}
    return "whatsapp_num_cliente" in names and "whatsapp_num_cliente_country" in names


def reset_schema_cache() -> None:
    has_whatsapp_order_columns.cache_clear()


def ensure_whatsapp_order_columns() -> bool:
    if has_whatsapp_order_columns():
        return True
    vendor = connection.vendor
    try:
        with connection.cursor() as cursor:
            if vendor == "postgresql":
                cursor.execute("ALTER TABLE orders_order ADD COLUMN IF NOT EXISTS whatsapp_num_cliente varchar(32) NOT NULL DEFAULT '';")
                cursor.execute("ALTER TABLE orders_order ADD COLUMN IF NOT EXISTS whatsapp_num_cliente_country varchar(8) NOT NULL DEFAULT '';")
            elif vendor == "sqlite":
                cursor.execute("ALTER TABLE orders_order ADD COLUMN whatsapp_num_cliente varchar(32) NOT NULL DEFAULT '';")
                cursor.execute("ALTER TABLE orders_order ADD COLUMN whatsapp_num_cliente_country varchar(8) NOT NULL DEFAULT '';")
            else:
                return False
    except Exception as exc:  # noqa: BLE001
        LOGGER.warning("orders.schema.ensure_whatsapp_columns.failed vendor=%s error=%s", vendor, exc)
        reset_schema_cache()
        return has_whatsapp_order_columns()
    reset_schema_cache()
    ok = has_whatsapp_order_columns()
    if ok:
        LOGGER.warning("orders.schema.ensure_whatsapp_columns.applied vendor=%s", vendor)
    return ok
