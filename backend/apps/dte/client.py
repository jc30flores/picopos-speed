from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from django.conf import settings

from apps.dte.models import DTETransmissionLog

DTE_LOGGER = logging.getLogger("apps.dte")


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
    elapsed_ms: int


def _preview(text: str) -> str:
    raw = (text or "").replace("\n", " ").strip()
    truncate = int(getattr(settings, "DTE_LOG_TRUNCATE_CHARS", 0) or 0)
    if truncate > 0:
        return raw[:truncate]
    return raw


def _pretty_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def _sanitize_for_log(payload: dict) -> dict:
    if bool(getattr(settings, "DTE_LOG_INCLUDE_SIGNED_DOCUMENT", False)):
        return payload
    data = dict(payload or {})
    for key in ["documento_firmado", "signed_document", "firma"]:
        if key in data:
            data[key] = "<omitted>"
    if "dte" in data and isinstance(data["dte"], dict):
        dte = dict(data["dte"])
        if "documento_firmado" in dte:
            dte["documento_firmado"] = "<omitted>"
        data["dte"] = dte
    return data


def _maybe_write_file(*, suffix: str, numero_control: str, codigo_generacion: str, content: str) -> None:
    if not bool(getattr(settings, "DTE_LOG_TO_FILE", False)):
        return
    base_dir = str(getattr(settings, "DTE_LOG_DIR", "tmp/dte_payloads") or "tmp/dte_payloads")
    os.makedirs(base_dir, exist_ok=True)
    safe_control = (numero_control or "nocontrol").replace("/", "_").replace(":", "_").replace(" ", "_")
    safe_codigo = (codigo_generacion or "nocodigo").replace("/", "_").replace(":", "_").replace(" ", "_")
    ext = "json" if suffix.endswith("request") or suffix.endswith("response_json") else "txt"
    path = os.path.join(base_dir, f"{safe_control}_{safe_codigo}_{suffix}.{ext}")
    with open(path, "w", encoding="utf-8") as f:
        f.write(content)
    DTE_LOGGER.info("[CF01] %s saved_to=%s bytes=%s", suffix.upper(), path, len(content.encode("utf-8")))


class DTEClient:
    def __init__(self, base_url: str | None = None):
        self.base_url = (base_url or getattr(settings, "DTE_BASE_URL", "") or "").strip().rstrip("/")
        self.auth_header = getattr(settings, "DTE_API_AUTH_HEADER", "Authorization")
        self.auth_prefix = getattr(settings, "DTE_API_AUTH_PREFIX", "Bearer")
        self.api_token = getattr(settings, "DTE_API_TOKEN", "")
        self.timeout = int(getattr(settings, "DTE_TIMEOUT_SECONDS", 30) or 30)
        self.user_agent = getattr(settings, "DTE_USER_AGENT", "PicoPOS-DTE/1.0")
        self.session = requests.Session()

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
            DTE_LOGGER.exception("[DTE HTTP] URL BUILD ERROR path=%s", path)
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
            return DTEClientResult(0, body, str(exc), False, "", "", str(exc), "CONFIG_ERROR", 0)

        ident = (payload or {}).get("dte", {}).get("identificacion", {})
        numero_control = str(ident.get("numeroControl") or "")
        codigo_generacion = str(ident.get("codigoGeneracion") or "")
        dte_type = str(ident.get("tipoDte") or "CF")
        sanitized_payload = _sanitize_for_log(payload)
        payload_pretty = _pretty_json(sanitized_payload)

        if bool(getattr(settings, "DTE_LOG_VERBOSE", False)) or bool(getattr(settings, "DTE_LOG_PAYLOAD_FULL", False)):
            DTE_LOGGER.info("ENDPOINT DTE: %s", url)
            DTE_LOGGER.info(
                "[CF01] invoice=%s url=%s numeroControl=%s codigoGeneracion=%s dte_type=%s",
                order_id,
                url,
                numero_control,
                codigo_generacion,
                dte_type,
            )
            DTE_LOGGER.info("JSON DTE ENVIO:\n%s", payload_pretty)
            DTE_LOGGER.info("[CF01] REQUEST:\n%s", payload_pretty)
            _maybe_write_file(
                suffix="request",
                numero_control=numero_control,
                codigo_generacion=codigo_generacion,
                content=payload_pretty,
            )

        started = time.perf_counter()
        status_code = 0
        text_body = ""
        parsed_json: dict = {}
        error_message = ""
        error_type = ""

        try:
            response = self.session.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
            status_code = int(response.status_code)
            text_body = response.text or ""
            try:
                parsed_json = response.json() if response.text else {}
            except Exception:
                parsed_json = {"raw": text_body}

            if status_code in {401, 403}:
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
                error_type = "AUTH" if status_code in {401, 403} else "VALIDATION" if 400 <= status_code < 500 else "SERVER_ERROR"
            error_message = text_body[:500]
        except Exception as exc:  # noqa: BLE001
            error_message = str(exc)
            error_type = "NETWORK_ERROR"
            parsed_json = {"success": False, "error": {"message": error_message, "type": error_type}, "offline": True}
            text_body = json.dumps(parsed_json, ensure_ascii=False)
            DTE_LOGGER.exception("[DTE HTTP] unexpected error order=%s payment=%s", order_id, payment_id)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        DTE_LOGGER.info("[CF01] Authorization presente=%s", bool((self.api_token or "").strip()))

        if bool(getattr(settings, "DTE_LOG_RESPONSE_FULL", False)):
            DTE_LOGGER.info("[CF01] RESPONSE status=%s:\n%s", status_code, text_body)
        else:
            DTE_LOGGER.info("[CF01] RESPONSE status=%s:\n%s", status_code, _preview(text_body))

        try:
            response_pretty = _pretty_json(parsed_json if isinstance(parsed_json, dict) else {"raw": text_body})
            DTE_LOGGER.info("[CF01] RESPONSE JSON:\n%s", response_pretty)
            _maybe_write_file(
                suffix="response_json",
                numero_control=numero_control,
                codigo_generacion=codigo_generacion,
                content=response_pretty,
            )
        except Exception:
            body_display = text_body if bool(getattr(settings, "DTE_LOG_RESPONSE_FULL", False)) else _preview(text_body)
            DTE_LOGGER.info("[CF01] RESPONSE BODY (non-json):\n%s", body_display)
            _maybe_write_file(
                suffix="response",
                numero_control=numero_control,
                codigo_generacion=codigo_generacion,
                content=body_display,
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

        log_row = DTETransmissionLog.objects.create(
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

        DTE_LOGGER.info(
            "INFO DTE_MH_PERSIST invoice_id=%s dte_record_id=%s estado=%s sello_present=%s",
            order_id,
            log_row.id,
            (parsed_json.get("estado") if isinstance(parsed_json, dict) else ""),
            bool(sello),
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
            elapsed_ms=elapsed_ms,
        )
