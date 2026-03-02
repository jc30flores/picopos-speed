from __future__ import annotations

import json
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


def _health_headers() -> dict[str, str]:
    headers = {
        "User-Agent": "PicoPOS-DTE-Health/1.0",
        "Accept": "application/json",
        "Content-Type": "application/json",
    }
    use_auth = _env("DTE_HEALTH_USE_AUTH", "0") in {"1", "true", "True"}
    token = _env("DTE_API_TOKEN", "").strip()
    if use_auth and token:
        auth_header = _env("DTE_API_AUTH_HEADER", "Authorization")
        auth_prefix = _env("DTE_API_AUTH_PREFIX", "Bearer").strip()
        headers[auth_header] = f"{auth_prefix} {token}".strip()
    return headers


def _safe_headers_for_log(headers: dict[str, str]) -> dict[str, str]:
    cleaned = dict(headers)
    for key in list(cleaned):
        if key.lower() == "authorization":
            cleaned[key] = "***"
    return cleaned


def _log_fail(url: str, status: int, error: str, body: str, headers: dict[str, str]):
    short_body = (body or "")[:200]
    msg = f"[DTE] Health check failed url={url} status={status} error={error} body={short_body}"
    logger.error(msg)
    print(msg)
    headers_msg = f"[DTE] Health request headers={_safe_headers_for_log(headers)}"
    logger.error(headers_msg)
    print(headers_msg)
    if status == 403:
        advice = "[DTE] 403 puede ser por bloqueo de User-Agent o auth; se está enviando UA+Authorization, revise token/endpoint."
        logger.error(advice)
        print(advice)


def _loop(url: str, interval: int, timeout: int):
    last_ok = None
    last_fail_log_at = 0.0

    while True:
        ok = False
        status = 0
        body = ""
        err_text = ""
        headers = _health_headers()
        try:
            req = urllib.request.Request(url, method="GET", headers=headers)
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                status = int(resp.getcode() or 0)
                body = resp.read().decode("utf-8", errors="replace")
                if status == 200:
                    ok = True
                    try:
                        parsed = json.loads(body) if body else {}
                        if isinstance(parsed, dict) and parsed.get("status") not in {None, "healthy"}:
                            ok = False
                            err_text = f"unexpected_json_status={parsed.get('status')}"
                    except Exception:
                        pass
                if not ok and not err_text:
                    err_text = f"http_status={status}"
        except urllib.error.HTTPError as exc:
            status = int(exc.code or 0)
            try:
                body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            except Exception:
                body = ""
            err_text = str(exc)
        except Exception as exc:
            err_text = str(exc)

        now = time.time()
        if ok:
            if last_ok is False:
                msg = f"[DTE] Health recovered url={url} status=200"
                logger.info(msg)
                print(msg)
        else:
            should_log = (last_ok is not False) or (now - last_fail_log_at >= 60)
            if should_log:
                _log_fail(url=url, status=status, error=err_text, body=body, headers=headers)
                last_fail_log_at = now

        last_ok = ok
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
