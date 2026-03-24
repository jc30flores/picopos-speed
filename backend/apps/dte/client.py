from __future__ import annotations

import json
import logging
import time
import urllib.error
import urllib.request
from dataclasses import dataclass

from django.conf import settings

from apps.dte.models import DTETransmissionLog

logger = logging.getLogger(__name__)


@dataclass
class DTEClientResult:
    status_code: int
    json_body: dict
    text_body: str
    success: bool
    remote_uuid: str
    sello_recibido: str
    error_message: str


def _mask_token(token: str) -> str:
    token = (token or "").strip()
    if len(token) <= 10:
        return "***"
    return f"{token[:6]}...{token[-4:]}"


class DTEClient:
    def __init__(self):
        self.base_url = (getattr(settings, "DTE_BASE_URL", "") or "").rstrip("/")
        self.auth_header = getattr(settings, "DTE_API_AUTH_HEADER", "Authorization")
        self.auth_prefix = getattr(settings, "DTE_API_AUTH_PREFIX", "Bearer")
        self.api_token = getattr(settings, "DTE_API_TOKEN", "")
        self.timeout = int(getattr(settings, "DTE_TIMEOUT_SECONDS", 30) or 30)
        self.debug = str(getattr(settings, "DTE_DEBUG", "0")) in {"1", "true", "True"}

    def _headers(self) -> dict[str, str]:
        token_value = f"{self.auth_prefix} {self.api_token}".strip()
        return {
            self.auth_header: token_value,
            "Content-Type": "application/json",
        }

    def _curl_for_log(self, url: str, payload: dict) -> str:
        payload_minified = json.dumps(payload, ensure_ascii=False, separators=(",", ":"))
        payload_shell = payload_minified.replace("'", "'\"'\"'")
        return (
            f"curl -X POST \"{url}\" \\\n"
            f"  -H \"{self.auth_header}: {self.auth_prefix} {_mask_token(self.api_token)}\" \\\n"
            f"  -H \"Content-Type: application/json\" \\\n"
            f"  -d '{payload_shell}'"
        )

    def send(
        self,
        *,
        path: str,
        payload: dict,
        order_id: int | None = None,
        payment_id: int | None = None,
        branch_id: int | None = None,
    ) -> DTEClientResult:
        url = f"{self.base_url}{path}" if self.base_url else path
        started = time.perf_counter()
        status_code = 0
        text_body = ""
        parsed_json: dict = {}
        error_message = ""

        logger.info("[DTE] DTE ENDPOINT >>> url=%s", url)
        logger.info("[DTE] CURL >>>\n%s", self._curl_for_log(url, payload))

        try:
            req = urllib.request.Request(
                url,
                data=json.dumps(payload, ensure_ascii=False).encode("utf-8"),
                headers=self._headers(),
                method="POST",
            )
            response = urllib.request.urlopen(req, timeout=self.timeout)
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            status_code = response.getcode()
            text_body = response.read().decode("utf-8", errors="replace")
            try:
                parsed_json = json.loads(text_body) if text_body else {}
            except Exception:
                parsed_json = {"raw": text_body}

            logger.info(
                "[DTE] RESP <<< status=%s elapsed_ms=%s order_id=%s payment_id=%s branch_id=%s",
                status_code,
                elapsed_ms,
                order_id,
                payment_id,
                branch_id,
            )
            if self.debug:
                logger.info("[DTE] RESP TEXT <<< %s", text_body)
                logger.info("[DTE] RESP JSON <<< %s", json.dumps(parsed_json, ensure_ascii=False, indent=2))
        except urllib.error.HTTPError as exc:
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            status_code = exc.code
            text_body = exc.read().decode("utf-8", errors="replace") if exc.fp else ""
            try:
                parsed_json = json.loads(text_body) if text_body else {}
            except Exception:
                parsed_json = {"raw": text_body}
            error_message = str(parsed_json.get("error", {}).get("message") or text_body or f"HTTP {exc.code}") if isinstance(parsed_json, dict) else text_body
            logger.error(
                "[DTE] HTTP ERROR status=%s order_id=%s payment_id=%s branch_id=%s elapsed_ms=%s",
                status_code,
                order_id,
                payment_id,
                branch_id,
                elapsed_ms,
            )
        except Exception as exc:  # noqa: BLE001
            elapsed_ms = int((time.perf_counter() - started) * 1000)
            error_message = str(exc)
            parsed_json = {"success": False, "error": {"message": error_message, "type": "NETWORK_ERROR"}, "offline": True}
            text_body = json.dumps(parsed_json, ensure_ascii=False)
            logger.exception(
                "[DTE] SEND ERROR order_id=%s payment_id=%s branch_id=%s elapsed_ms=%s",
                order_id,
                payment_id,
                branch_id,
                elapsed_ms,
            )

        rh = parsed_json.get("respuesta_hacienda") if isinstance(parsed_json, dict) else {}
        rh = rh if isinstance(rh, dict) else {}
        remote_uuid = str(parsed_json.get("uuid") or rh.get("codigoGeneracion") or "") if isinstance(parsed_json, dict) else ""
        sello = str(rh.get("selloRecibido") or parsed_json.get("selloRecibido") or "") if isinstance(parsed_json, dict) else ""

        if sello == "SELLO-MOCK":
            logger.warning("Proveedor devolvió SELLO-MOCK (posible sandbox/mock). Verifica ambiente/base_url/token.")

        success = False
        if status_code and status_code < 400 and isinstance(parsed_json, dict):
            success = bool(parsed_json.get("success") is True)

        if not success and not error_message and isinstance(parsed_json, dict):
            maybe_err = parsed_json.get("error")
            if isinstance(maybe_err, dict):
                error_message = str(maybe_err.get("message") or "")

        DTETransmissionLog.objects.create(
            order_id=order_id,
            payment_id=payment_id,
            branch_id=branch_id,
            request_payload=payload,
            response_status=status_code,
            response_body=parsed_json if isinstance(parsed_json, dict) else {"raw": text_body},
            success=success,
            remote_uuid=remote_uuid,
            sello_recibido=sello,
            error_message=error_message,
        )

        return DTEClientResult(
            status_code=status_code,
            json_body=parsed_json if isinstance(parsed_json, dict) else {"raw": text_body},
            text_body=text_body,
            success=success,
            remote_uuid=remote_uuid,
            sello_recibido=sello,
            error_message=error_message,
        )
