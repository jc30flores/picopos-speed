from __future__ import annotations

import json
import logging
import time
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
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
    error_type: str


class DTEClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or getattr(settings, "DTE_BASE_URL", "") or "").strip().rstrip("/")
        self.auth_header = getattr(settings, "DTE_API_AUTH_HEADER", "Authorization")
        self.auth_prefix = getattr(settings, "DTE_API_AUTH_PREFIX", "Bearer")
        self.api_token = getattr(settings, "DTE_API_TOKEN", "")
        self.timeout = int(getattr(settings, "DTE_TIMEOUT_SECONDS", 30) or 30)
        self.user_agent = getattr(settings, "DTE_USER_AGENT", "PicoPOS-DTE/1.0")

    def _build_url(self, path: str) -> str:
        base_url = (self.base_url or getattr(settings, "DTE_BASE_URL", "") or "").strip()
        if not base_url:
            raise ValueError("DTE_BASE_URL is not configured")
        if not (base_url.startswith("http://") or base_url.startswith("https://")):
            raise ValueError("DTE_BASE_URL must start with http:// or https://")
        return urljoin(f"{base_url.rstrip('/')}/", path.lstrip("/"))

    def _headers(self) -> dict[str, str]:
        token_value = f"{self.auth_prefix} {self.api_token}".strip()
        return {
            self.auth_header: token_value,
            "Accept": "application/json",
            "Content-Type": "application/json",
            "User-Agent": self.user_agent,
        }

    def send(
        self,
        *,
        path: str,
        payload: dict,
        order_id: int | None = None,
        payment_id: int | None = None,
        branch_id: int | None = None,
        attempt_number: int = 1,
    ) -> DTEClientResult:
        try:
            url = self._build_url(path)
        except Exception as exc:  # noqa: BLE001
            logger.exception("[DTE] URL BUILD ERROR path=%s", path)
            body = {"success": False, "error": {"message": str(exc), "type": "CONFIG_ERROR"}}
            DTETransmissionLog.objects.create(
                order_id=order_id,
                payment_id=payment_id,
                branch_id=branch_id,
                request_payload=payload,
                response_status=0,
                response_body=body,
                success=False,
                error_message=str(exc),
            )
            return DTEClientResult(0, body, str(exc), False, "", "", str(exc), "CONFIG_ERROR")

        started = time.perf_counter()
        status_code = 0
        text_body = ""
        parsed_json: dict = {}
        error_message = ""
        error_type = ""

        try:
            response = requests.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
            status_code = int(response.status_code)
            text_body = response.text or ""
            try:
                parsed_json = response.json() if response.text else {}
            except Exception:
                parsed_json = {"raw": text_body}

            if status_code in {200, 201}:
                pass
            elif status_code in {401, 403}:
                error_type = "AUTH"
            elif 400 <= status_code < 500:
                error_type = "VALIDATION"
            elif status_code >= 500:
                error_type = "SERVER_ERROR"

            response.raise_for_status()
        except requests.Timeout as exc:
            error_message = str(exc)
            error_type = "TIMEOUT"
            parsed_json = {"success": False, "error": {"message": error_message, "type": error_type}, "offline": True}
            text_body = json.dumps(parsed_json, ensure_ascii=False)
        except requests.ConnectionError as exc:
            error_message = str(exc)
            error_type = "CONNECTION_ERROR"
            parsed_json = {"success": False, "error": {"message": error_message, "type": error_type}, "offline": True}
            text_body = json.dumps(parsed_json, ensure_ascii=False)
        except requests.HTTPError as exc:
            response = exc.response
            status_code = int(response.status_code) if response is not None else 0
            text_body = response.text if response is not None else str(exc)
            if not error_type:
                if status_code in {401, 403}:
                    error_type = "AUTH"
                elif 400 <= status_code < 500:
                    error_type = "VALIDATION"
                else:
                    error_type = "SERVER_ERROR"
            error_message = text_body[:500]
        except Exception as exc:  # noqa: BLE001
            error_message = str(exc)
            error_type = "NETWORK_ERROR"
            parsed_json = {"success": False, "error": {"message": error_message, "type": error_type}, "offline": True}
            text_body = json.dumps(parsed_json, ensure_ascii=False)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "[DTE SEND] order_id=%s status_code=%s elapsed_ms=%s attempt_number=%s",
            order_id,
            status_code,
            elapsed_ms,
            attempt_number,
        )

        rh = parsed_json.get("respuesta_hacienda") if isinstance(parsed_json, dict) else {}
        rh = rh if isinstance(rh, dict) else {}
        remote_uuid = str(parsed_json.get("uuid") or rh.get("codigoGeneracion") or "") if isinstance(parsed_json, dict) else ""
        sello = str(rh.get("selloRecibido") or parsed_json.get("selloRecibido") or "") if isinstance(parsed_json, dict) else ""

        success = status_code in {200, 201}
        if not error_message and isinstance(parsed_json, dict):
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
            error_type=error_type,
        )
