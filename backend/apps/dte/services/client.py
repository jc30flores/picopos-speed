from __future__ import annotations

import json
import logging
import os
import urllib.error
import urllib.request

logger = logging.getLogger(__name__)


class DTEClientError(Exception):
    pass


def send_to_bridge(payload: dict) -> dict:
    mode = os.environ.get("DTE_BRIDGE_MODE", "http").lower()
    if mode == "mock":
        force = str(payload.get("meta", {}).get("mock_status", "accepted")).lower()
        if force == "rejected":
            return {"ok": False, "status": "RECHAZADO", "error": "Mock rejection", "error_code": "MOCK_REJECT"}
        return {
            "ok": True,
            "status": "ACEPTADO",
            "uuid": payload["identificacion"]["codigoGeneracion"],
            "selloRecibido": f"SELLO-{payload['identificacion']['numeroControl']}",
            "provider": "mock",
        }

    base_url = os.environ.get("DTE_BRIDGE_BASE_URL", "").rstrip("/")
    if not base_url:
        raise DTEClientError("DTE_BRIDGE_BASE_URL is required when DTE_BRIDGE_MODE != mock")
    token = os.environ.get("DTE_BRIDGE_TOKEN", "")
    timeout = float(os.environ.get("DTE_BRIDGE_READ_TIMEOUT", "15"))
    req = urllib.request.Request(
        f"{base_url}/dte/send",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    try:
        with urllib.request.urlopen(req, timeout=timeout) as resp:
            return json.loads(resp.read().decode("utf-8"))
    except urllib.error.HTTPError as exc:
        body = exc.read().decode("utf-8") if exc.fp else ""
        logger.warning("DTE bridge HTTP error status=%s", exc.code)
        return {"ok": False, "status": "RECHAZADO" if 400 <= exc.code < 500 else "PENDIENTE", "error": body or str(exc), "error_code": str(exc.code)}
    except Exception as exc:
        logger.warning("DTE bridge network error: %s", exc.__class__.__name__)
        return {"ok": False, "status": "PENDIENTE", "error": str(exc), "error_code": "NETWORK"}
