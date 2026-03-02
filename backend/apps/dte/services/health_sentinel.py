from __future__ import annotations

import logging
import os
import threading
import time
import urllib.error
import urllib.request


logger = logging.getLogger(__name__)
_started = False
_lock = threading.Lock()


def _env(name: str, default: str = "") -> str:
    return os.environ.get(name, default)


def _health_url() -> str:
    explicit = _env("DTE_HEALTH_URL", "").strip()
    if explicit:
        return explicit
    base = _env("DTE_BASE_URL", "").rstrip("/")
    return f"{base}/health" if base else ""


def _is_enabled() -> bool:
    return _env("DTE_SENTINEL_ENABLED", "1") not in {"0", "false", "False"}


def _loop(url: str, interval: int, timeout: int):
    last_state = None
    while True:
        ok = False
        try:
            req = urllib.request.Request(url, method="GET")
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                ok = resp.getcode() == 200
                if not ok and last_state is not False:
                    logger.error("[DTE] Health check failed status=%s url=%s", resp.getcode(), url)
        except Exception as exc:
            if last_state is not False:
                logger.error("[DTE] Health check failed url=%s error=%s", url, exc)

        if ok and last_state is False:
            logger.info("[DTE] Health recovered url=%s", url)
        last_state = ok
        time.sleep(interval)


def start_health_sentinel() -> str:
    global _started

    url = _health_url()
    if not _is_enabled() or not url:
        return url or "(disabled)"

    with _lock:
        if _started:
            return url
        interval = int(_env("DTE_HEALTH_INTERVAL_SECONDS", "5"))
        timeout = int(_env("DTE_HEALTH_TIMEOUT_SECONDS", "3"))
        t = threading.Thread(target=_loop, args=(url, interval, timeout), daemon=True, name="dte-health-sentinel")
        t.start()
        _started = True
    return url
