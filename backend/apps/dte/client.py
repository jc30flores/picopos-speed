from __future__ import annotations

import json
import logging
import os
import time
from dataclasses import dataclass
from urllib.parse import urljoin

import requests
from django.conf import settings

from apps.core.models import Branch
from apps.dte.models import DTETransmissionLog
from apps.dte.services.emisor import get_emisor_nit, payload_emisor_nit
from apps.dte.services.dte_parser import parse_hacienda_response

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


def _pretty_json(payload: dict) -> str:
    return json.dumps(payload, indent=2, ensure_ascii=False, default=str)


def _preview(text: str) -> str:
    raw = (text or "").replace("\n", " ").strip()
    truncate = int(getattr(settings, "DTE_LOG_TRUNCATE_CHARS", 0) or 0)
    if truncate > 0:
        return raw[:truncate]
    return raw


def _payload_dir() -> str:
    return str(getattr(settings, "DTE_LOG_DIR", "tmp/dte_payloads") or "tmp/dte_payloads")


def _write_log_file(*, suffix: str, numero_control: str, codigo_generacion: str, content: str, is_json: bool) -> None:
    if not bool(getattr(settings, "DTE_LOG_TO_FILE", False)):
        return
    os.makedirs(_payload_dir(), exist_ok=True)
    safe_control = (numero_control or "nocontrol").replace("/", "_").replace(":", "_").replace(" ", "_")
    safe_codigo = (codigo_generacion or "nocodigo").replace("/", "_").replace(":", "_").replace(" ", "_")
    ext = "json" if is_json else "txt"
    path = os.path.join(_payload_dir(), f"{safe_control}_{safe_codigo}_{suffix}.{ext}")
    with open(path, "w", encoding="utf-8") as fh:
        fh.write(content)
    DTE_LOGGER.info("[CF01] %s saved_to=%s bytes=%s", suffix.upper(), path, len(content.encode("utf-8")))


def log_dte_request(context: dict, url: str, payload_dict: dict) -> None:
    numero_control = context.get("numero_control") or ""
    codigo_generacion = context.get("codigo_generacion") or ""
    pretty = _pretty_json(payload_dict)

    DTE_LOGGER.info("ENDPOINT DTE: %s", url)
    DTE_LOGGER.info("JSON DTE ENVIO:\n%s", pretty)
    DTE_LOGGER.info(
        "[CF01] REQUEST BEGIN invoice=%s order=%s payment=%s numeroControl=%s codigoGeneracion=%s",
        context.get("invoice_id"),
        context.get("order_id"),
        context.get("payment_id"),
        numero_control,
        codigo_generacion,
    )
    DTE_LOGGER.info("[CF01] REQUEST:\n%s", pretty)
    DTE_LOGGER.info(
        "[CF01] REQUEST END invoice=%s order=%s payment=%s",
        context.get("invoice_id"),
        context.get("order_id"),
        context.get("payment_id"),
    )
    _write_log_file(
        suffix="request",
        numero_control=numero_control,
        codigo_generacion=codigo_generacion,
        content=pretty,
        is_json=True,
    )


def log_dte_response(context: dict, *, status_code: int, body_text: str, parsed_json: dict | None, authorization_present: bool) -> None:
    numero_control = context.get("numero_control") or ""
    codigo_generacion = context.get("codigo_generacion") or ""

    DTE_LOGGER.info("[CF01] Authorization presente=%s", authorization_present)
    if bool(getattr(settings, "DTE_LOG_RESPONSE_FULL", False)):
        DTE_LOGGER.info("[CF01] RESPONSE status=%s:\n%s", status_code, body_text)
    else:
        DTE_LOGGER.info("[CF01] RESPONSE status=%s:\n%s", status_code, _preview(body_text))

    if parsed_json is not None:
        pretty = _pretty_json(parsed_json)
        DTE_LOGGER.info("[CF01] RESPONSE JSON:\n%s", pretty)
        _write_log_file(
            suffix="response",
            numero_control=numero_control,
            codigo_generacion=codigo_generacion,
            content=pretty,
            is_json=True,
        )
    else:
        body_display = body_text if bool(getattr(settings, "DTE_LOG_RESPONSE_FULL", False)) else _preview(body_text)
        DTE_LOGGER.info("[CF01] RESPONSE BODY (non-json):\n%s", body_display)
        _write_log_file(
            suffix="response",
            numero_control=numero_control,
            codigo_generacion=codigo_generacion,
            content=body_display,
            is_json=False,
        )


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
        context = {
            "invoice_id": order_id,
            "order_id": order_id,
            "payment_id": payment_id,
            "numero_control": numero_control,
            "codigo_generacion": codigo_generacion,
        }
        branch = Branch.objects.filter(id=branch_id).first() if branch_id else None
        expected_nit = get_emisor_nit(branch)
        payload_nit = payload_emisor_nit(payload)
        DTE_LOGGER.info("[DTE DEBUG] Emisor NIT final utilizado=%s branch_id=%s", expected_nit, branch_id)
        if expected_nit and payload_nit and payload_nit != expected_nit:
            message = f"NIT emisor inconsistente: payload={payload_nit} esperado={expected_nit}"
            DTE_LOGGER.critical("[DTE CRITICAL] %s", message)
            DTETransmissionLog.objects.create(
                order_id=order_id,
                payment_id=payment_id,
                branch_id=branch_id,
                request_payload=payload,
                response_status=0,
                response_body={"success": False, "error": {"message": message, "type": "EMISOR_NIT_MISMATCH"}},
                success=False,
                error_message=message,
            )
            return DTEClientResult(
                0,
                {"success": False, "error": {"message": message, "type": "EMISOR_NIT_MISMATCH"}},
                message,
                False,
                "",
                "",
                message,
                "EMISOR_NIT_MISMATCH",
                0,
            )

        DTE_LOGGER.info(
            "[CF01] invoice=%s url=%s numeroControl=%s codigoGeneracion=%s dte_type=%s",
            order_id,
            url,
            numero_control,
            codigo_generacion,
            "CF",
        )
        log_dte_request(context, url, payload)

        started = time.perf_counter()
        status_code = 0
        text_body = ""
        parsed_json: dict = {}
        parsed_json_valid = False
        error_message = ""
        error_type = ""

        try:
            response = self.session.post(url, json=payload, headers=self._headers(), timeout=self.timeout)
            status_code = int(response.status_code)
            text_body = response.text or ""
            try:
                parsed_json = response.json() if response.text else {}
                parsed_json_valid = True
            except Exception:
                parsed_json = {"raw": text_body}
                parsed_json_valid = False

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
            parsed_json_valid = True
            text_body = json.dumps(parsed_json, ensure_ascii=False)
        except requests.ConnectionError as exc:
            error_message = str(exc)
            error_type = "CONNECTION_ERROR"
            parsed_json = {"success": False, "error": {"message": error_message, "type": error_type}, "offline": True}
            parsed_json_valid = True
            text_body = json.dumps(parsed_json, ensure_ascii=False)
        except requests.HTTPError as exc:
            response = exc.response
            status_code = int(response.status_code) if response is not None else 0
            text_body = response.text if response is not None else str(exc)
            if not error_type:
                error_type = "AUTH" if status_code in {401, 403} else "VALIDATION" if 400 <= status_code < 500 else "SERVER_ERROR"
            try:
                parsed_json = response.json() if response is not None and response.text else {}
                parsed_json_valid = True
            except Exception:
                parsed_json = {"raw": text_body}
                parsed_json_valid = False
            error_message = text_body[:500]
        except Exception as exc:  # noqa: BLE001
            error_message = str(exc)
            error_type = "NETWORK_ERROR"
            parsed_json = {"success": False, "error": {"message": error_message, "type": error_type}, "offline": True}
            parsed_json_valid = True
            text_body = json.dumps(parsed_json, ensure_ascii=False)
            DTE_LOGGER.exception("[DTE HTTP] unexpected error order=%s payment=%s", order_id, payment_id)

        elapsed_ms = int((time.perf_counter() - started) * 1000)
        log_dte_response(
            context,
            status_code=status_code,
            body_text=text_body,
            parsed_json=parsed_json if parsed_json_valid else None,
            authorization_present=bool((self.api_token or "").strip()),
        )

        parsed_receipt = parse_hacienda_response(parsed_json if isinstance(parsed_json, dict) else {})
        remote_uuid = str(parsed_receipt.get("hacienda_uuid") or "")
        sello = str(parsed_receipt.get("sello_recibido") or parsed_receipt.get("sello_recepcion") or "")
        DTE_LOGGER.info(
            "[CF01] RECEIPT order=%s payment=%s estado=%s sello=%s firma=%s recibido_at=%s",
            order_id,
            payment_id,
            parsed_receipt.get("estado_mh") or parsed_receipt.get("hacienda_state") or "",
            sello or "-",
            parsed_receipt.get("firma") or "-",
            parsed_receipt.get("recibido_at") or "-",
        )

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
