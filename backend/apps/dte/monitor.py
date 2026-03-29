from __future__ import annotations

import logging
import threading
import time
from dataclasses import dataclass

import requests
from requests.exceptions import RequestException
from django.conf import settings
from django.core.cache import cache
from django.utils import timezone

DTE_LOGGER = logging.getLogger("apps.dte")

CACHE_HEALTH_IS_UP = "dte:health:is_up"
CACHE_HEALTH_STATUS_CODE = "dte:health:status_code"
CACHE_HEALTH_BODY = "dte:health:health_body"
CACHE_FACTURA_CODE = "dte:health:factura_code"
CACHE_FACTURA_BODY = "dte:health:factura_body"
CACHE_STATE = "dte:health:state"
CACHE_LAST_CHECKED = "dte:health:last_checked_at"

STATE_UP = "UP"
STATE_DOWN = "DOWN"
STATE_DEGRADED = "DEGRADED"


@dataclass
class HealthSnapshot:
    is_up: bool
    state: str
    health_status_code: int | None
    health_body: str
    factura_code: int | None
    factura_body: str
    last_checked_at: float | None


class DTEHealthMonitor:
    _started = False
    _lock = threading.Lock()

    def __init__(self):
        self.base_url = (getattr(settings, "DTE_BASE_URL", "") or "").rstrip("/")
        endpoint = (getattr(settings, "DTE_HEALTH_ENDPOINT", "/health") or "/health").strip()
        self.health_endpoint = endpoint if endpoint.startswith("/") else f"/{endpoint}"
        self.health_url = f"{self.base_url}{self.health_endpoint}" if self.base_url else ""
        self.factura_url = f"{self.base_url}/api/v1/dte/factura" if self.base_url else ""
        self.interval = int(getattr(settings, "DTE_MONITOR_INTERVAL_SECONDS", 10) or 10)
        self.timeout = int(getattr(settings, "DTE_HEALTH_TIMEOUT_SECONDS", 5) or 5)
        self.max_backoff = int(getattr(settings, "DTE_MONITOR_MAX_BACKOFF_SECONDS", 30) or 30)
        self.user_agent = getattr(settings, "DTE_USER_AGENT", "PicoPOS-DTE/1.0")

    @staticmethod
    def _preview(text: str, max_len: int = 500) -> str:
        return (text or "").replace("\n", " ").strip()[:max_len]

    def _headers(self) -> dict[str, str]:
        token = (getattr(settings, "DTE_API_TOKEN", "") or "").strip()
        auth_prefix = (getattr(settings, "DTE_API_AUTH_PREFIX", "Bearer") or "Bearer").strip()
        auth_header = (getattr(settings, "DTE_API_AUTH_HEADER", "Authorization") or "Authorization").strip()
        headers = {
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }
        if token:
            headers[auth_header] = f"{auth_prefix} {token}".strip()
        return headers

    @classmethod
    def get_cached_snapshot(cls) -> HealthSnapshot:
        return HealthSnapshot(
            is_up=bool(cache.get(CACHE_HEALTH_IS_UP, False)),
            state=str(cache.get(CACHE_STATE, STATE_DOWN) or STATE_DOWN),
            health_status_code=cache.get(CACHE_HEALTH_STATUS_CODE),
            health_body=cache.get(CACHE_HEALTH_BODY, "") or "",
            factura_code=cache.get(CACHE_FACTURA_CODE),
            factura_body=cache.get(CACHE_FACTURA_BODY, "") or "",
            last_checked_at=cache.get(CACHE_LAST_CHECKED),
        )

    def _save_snapshot(self, *, state: str, health_status_code: int | None, health_body: str, factura_code: int | None, factura_body: str) -> None:
        cache.set(CACHE_STATE, state, timeout=None)
        cache.set(CACHE_HEALTH_IS_UP, state == STATE_UP, timeout=None)
        cache.set(CACHE_HEALTH_STATUS_CODE, health_status_code, timeout=None)
        cache.set(CACHE_HEALTH_BODY, health_body, timeout=None)
        cache.set(CACHE_FACTURA_CODE, factura_code, timeout=None)
        cache.set(CACHE_FACTURA_BODY, factura_body, timeout=None)
        cache.set(CACHE_LAST_CHECKED, timezone.now().timestamp(), timeout=None)

    def _determine_state(self, health_code: int | None, factura_code: int | None, error_text: str = "") -> str:
        if error_text:
            return STATE_DOWN
        if health_code != 200:
            return STATE_DOWN
        if factura_code is None:
            return STATE_UP
        if factura_code in {200, 401, 403, 404, 422}:
            return STATE_UP
        if factura_code in {500, 502, 503, 504}:
            return STATE_DEGRADED
        return STATE_DEGRADED

    def check_once(self, force_log: bool = False) -> HealthSnapshot:
        previous = self.get_cached_snapshot()
        health_code = None
        health_body = ""
        factura_code = None
        factura_body = ""
        error_text = ""

        if not self.base_url:
            error_text = "DTE_BASE_URL missing"
            state = STATE_DOWN
            self._save_snapshot(state=state, health_status_code=None, health_body=error_text, factura_code=None, factura_body="")
            DTE_LOGGER.info("[DTE MONITOR] STATE=%s health=%s factura=%s error=%s", state, None, None, error_text)
            return self.get_cached_snapshot()

        reason = ""
        try:
            health_resp = requests.get(self.health_url, timeout=self.timeout, headers=self._headers())
            health_code = int(health_resp.status_code)
            health_body = health_resp.text or ""
        except RequestException as exc:
            error_text = f"health_error={exc}"
            if "name resolution" in str(exc).lower() or "nodename nor servname provided" in str(exc).lower():
                reason = "dns"
            elif "timed out" in str(exc).lower():
                reason = "timeout"
            else:
                reason = "network"

        if not error_text:
            try:
                factura_resp = requests.post(self.factura_url, timeout=self.timeout, headers=self._headers(), json={"test": "ping"})
                factura_code = int(factura_resp.status_code)
                factura_body = factura_resp.text or ""
            except RequestException as exc:
                if not error_text:
                    error_text = f"factura_error={exc}"
                reason = reason or ("dns" if "name resolution" in str(exc).lower() else "network")

        state = self._determine_state(health_code, factura_code, error_text)
        self._save_snapshot(
            state=state,
            health_status_code=health_code,
            health_body=health_body if not error_text else error_text,
            factura_code=factura_code,
            factura_body=factura_body,
        )

        changed = (previous.state != state) or (previous.health_status_code != health_code) or (previous.factura_code != factura_code)
        if changed or force_log:
            if state == STATE_UP:
                if factura_code == 422:
                    DTE_LOGGER.info("[DTE MONITOR] factura_reachable=true (422 expected)")
                DTE_LOGGER.info(
                    "[DTE MONITOR] STATE=%s health=%s factura=%s body_preview=%s",
                    state,
                    health_code,
                    factura_code,
                    self._preview(factura_body or health_body),
                )
            else:
                DTE_LOGGER.info(
                    "[DTE MONITOR] STATE=%s reason=%s health=%s factura=%s health_body_preview=%s factura_body_preview=%s error=%s",
                    state,
                    reason or "unknown",
                    health_code,
                    factura_code,
                    self._preview(health_body if not error_text else error_text),
                    self._preview(factura_body),
                    self._preview(error_text),
                )

        return self.get_cached_snapshot()

    def loop(self) -> None:
        first = True
        previous_state = self.get_cached_snapshot().state
        retry_backoff = 1
        while True:
            try:
                snapshot = self.check_once(force_log=first)
                first = False
                if snapshot.state == STATE_DOWN:
                    DTE_LOGGER.info("[DTE MONITOR] STATE=DOWN next_retry_in=%ss", retry_backoff)
                retry_backoff = 1 if snapshot.state == STATE_UP else min(retry_backoff * 2, self.max_backoff)
            except Exception as exc:  # noqa: BLE001
                DTE_LOGGER.warning("[DTE MONITOR] STATE=DOWN reason=loop err=%s next_retry_in=%ss", self._preview(str(exc), 180), retry_backoff)
                time.sleep(retry_backoff)
                retry_backoff = min(retry_backoff * 2, self.max_backoff)
                continue

            if snapshot.state == STATE_UP and previous_state != STATE_UP:
                from apps.dte.outbox import process_pending_outbox

                threading.Thread(target=process_pending_outbox, kwargs={"limit": int(getattr(settings, "DTE_PENDING_BATCH_SIZE", 50) or 50)}, daemon=True, name="dte-pending-processor").start()
            previous_state = snapshot.state
            time.sleep(self.interval if snapshot.state == STATE_UP else retry_backoff)

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
