from __future__ import annotations

import json
import os
import urllib.request


def send_payload(payload: dict) -> dict:
    mode = os.environ.get("DTE_BRIDGE_MODE", "mock").lower()
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
    token = os.environ.get("DTE_BRIDGE_TOKEN", "")
    timeout = float(os.environ.get("DTE_BRIDGE_READ_TIMEOUT", "15"))
    req = urllib.request.Request(
        f"{base_url}/dte/send",
        data=json.dumps(payload).encode("utf-8"),
        headers={"Authorization": f"Bearer {token}", "Content-Type": "application/json"},
        method="POST",
    )
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(resp.read().decode("utf-8"))
