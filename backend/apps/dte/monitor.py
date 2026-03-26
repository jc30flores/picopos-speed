from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import requests
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

DTE_LOGGER = logging.getLogger("apps.dte")

CACHE_STATUS_CODE = "dte:health:status_code"
CACHE_BODY = "dte:health:body"
CACHE_LAST_CHECKED = "dte:health:last_checked_at"
CACHE_IS_UP = "dte:health:is_up"


@dataclass
class HealthSnapshot:
    status_code: int | None
    body: str
    is_up: bool
    last_checked_at: float | None


class DTEHealthMonitor:
    _started = False
    _lock = threading.Lock()

    def __init__(self):
        self.base_url = (getattr(settings, "DTE_BASE_URL", "") or "").rstrip("/")
        endpoint = (getattr(settings, "DTE_HEALTH_ENDPOINT", "/health") or "/health").strip()
        self.endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        self.health_url = f"{self.base_url}{self.endpoint}" if self.base_url else ""
        self.interval = int(getattr(settings, "DTE_MONITOR_INTERVAL_SECONDS", 10) or 10)
        self.timeout = int(getattr(settings, "DTE_HEALTH_TIMEOUT_SECONDS", 5) or 5)
        self.user_agent = getattr(settings, "DTE_USER_AGENT", "PicoPOS-DTE/1.0")

    @staticmethod
    def _preview(text: str, max_len: int = 500) -> str:
        raw = (text or "").replace("\n", " ").strip()
        return raw[:max_len]

    @classmethod
    def get_cached_snapshot(cls) -> HealthSnapshot:
        return HealthSnapshot(
            status_code=cache.get(CACHE_STATUS_CODE),
            body=cache.get(CACHE_BODY, "") or "",
            is_up=bool(cache.get(CACHE_IS_UP, False)),
            last_checked_at=cache.get(CACHE_LAST_CHECKED),
        )

    def _store(self, *, status_code: int | None, body: str, is_up: bool) -> None:
        now_ts = timezone.now().timestamp()
        cache.set(CACHE_STATUS_CODE, status_code, timeout=None)
        cache.set(CACHE_BODY, body, timeout=None)
        cache.set(CACHE_IS_UP, is_up, timeout=None)
        cache.set(CACHE_LAST_CHECKED, now_ts, timeout=None)

    def check_once(self, force_log: bool = False) -> HealthSnapshot:
        previous = self.get_cached_snapshot()
        status_code: int | None = None
        body = ""
        is_up = False

        if not self.health_url:
            body = "DTE health URL is empty"
            self._store(status_code=None, body=body, is_up=False)
            DTE_LOGGER.info("[DTE MONITOR] API DOWN error=%s", body)
            return self.get_cached_snapshot()

        try:
            response = requests.get(
                self.health_url,
                timeout=self.timeout,
                headers={"Accept": "application/json", "User-Agent": self.user_agent},
            )
            status_code = int(response.status_code)
            body = response.text or ""
            is_up = status_code == 200
            self._store(status_code=status_code, body=body, is_up=is_up)

            changed = previous.is_up != is_up or previous.status_code != status_code
            if changed or force_log:
                if is_up:
                    DTE_LOGGER.info("[DTE MONITOR] API UP code=%s body_preview=%s", status_code, self._preview(body))
                else:
                    DTE_LOGGER.info("[DTE MONITOR] API DOWN code=%s body_preview=%s", status_code, self._preview(body))
        except Exception as exc:  # noqa: BLE001
            self._store(status_code=None, body=str(exc), is_up=False)
            changed = previous.is_up is not False
            if changed or force_log:
                DTE_LOGGER.exception("[DTE MONITOR] API DOWN error=%s", exc)

        return self.get_cached_snapshot()

    def loop(self) -> None:
        first_check = True
        while True:
            snapshot = self.check_once(force_log=first_check)
            first_check = False
            if snapshot.is_up:
                from apps.dte.outbox import process_pending_outbox

                try:
                    processed = process_pending_outbox()
                    if processed:
                        DTE_LOGGER.info("[DTE MONITOR] pending_processed=%s", processed)
                except Exception:  # noqa: BLE001
                    DTE_LOGGER.exception("[DTE MONITOR] process_pending_outbox failed")
            time.sleep(self.interval)

    def start(self) -> bool:
        enabled = bool(getattr(settings, "DTE_MONITOR_ENABLED", True))
        if not enabled:
            DTE_LOGGER.info("[DTE MONITOR] disabled via DTE_MONITOR_ENABLED")
            return False

        with self._lock:
            if self.__class__._started:
                return False
            DTE_LOGGER.info("[DTE MONITOR] starting thread interval=%ss health_url=%s", self.interval, self.health_url)
            thread = threading.Thread(target=self.loop, daemon=True, name="dte-health-monitor")
            thread.start()
            self.__class__._started = True
            return True


def get_monitor() -> DTEHealthMonitor:
    return DTEHealthMonitor()


def start_monitor() -> None:
    get_monitor().start()


def check_health_now(force_log: bool = False) -> HealthSnapshot:
    return get_monitor().check_once(force_log=force_log)
