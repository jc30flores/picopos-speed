from __future__ import annotations

import logging
import threading
import time

import requests
from django.conf import settings

from apps.dte.outbox import process_pending_dtes

logger = logging.getLogger(__name__)

DTE_API_STATUS = "UNKNOWN"
_STARTED = False
_LOCK = threading.Lock()


def _health_url() -> str:
    base = (getattr(settings, "DTE_BASE_URL", "") or "").rstrip("/")
    endpoint = (getattr(settings, "DTE_HEALTH_ENDPOINT", "/health") or "/health").strip()
    endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
    return f"{base}{endpoint}" if base else ""


def _health_timeout() -> int:
    return int(getattr(settings, "DTE_HEALTH_TIMEOUT_SECONDS", 5) or 5)


def _mark_status(is_up: bool) -> None:
    global DTE_API_STATUS
    new = "UP" if is_up else "DOWN"
    if new != DTE_API_STATUS:
        DTE_API_STATUS = new
        if new == "UP":
            logger.info("[DTE MONITOR] API UP")
        else:
            logger.warning("[DTE MONITOR] API DOWN")


def check_health_once() -> bool:
    url = _health_url()
    if not url:
        _mark_status(False)
        return False

    try:
        response = requests.get(url, timeout=_health_timeout(), headers={"Accept": "application/json", "User-Agent": getattr(settings, "DTE_USER_AGENT", "PicoPOS-DTE/1.0")})
        is_ok = response.status_code == 200
        _mark_status(is_ok)
        return is_ok
    except Exception:
        _mark_status(False)
        return False


def _loop() -> None:
    interval = int(getattr(settings, "DTE_MONITOR_INTERVAL_SECONDS", 10) or 10)
    while True:
        is_up = check_health_once()
        if is_up:
            processed = process_pending_dtes()
            if processed:
                logger.info("[DTE MONITOR] processed_pending=%s", processed)
        time.sleep(interval)


def start_monitor() -> None:
    global _STARTED
    with _LOCK:
        if _STARTED:
            return
        t = threading.Thread(target=_loop, daemon=True, name="dte-monitor")
        t.start()
        _STARTED = True
