from __future__ import annotations

from datetime import date, datetime
from urllib.parse import urlencode


HACIENDA_CONSULTA_PUBLICA_BASE_URL = "https://admin.factura.gob.sv/consultaPublica"


def _normalize_fecha(fecha_dte: str | date | datetime | None) -> str:
    if fecha_dte is None:
        return ""
    if isinstance(fecha_dte, datetime):
        return fecha_dte.date().isoformat()
    if isinstance(fecha_dte, date):
        return fecha_dte.isoformat()
    return str(fecha_dte).strip()


def build_hacienda_consulta_publica_url(fecha_dte: str | date | datetime | None, codigo_generacion: str | None) -> str:
    fecha = _normalize_fecha(fecha_dte)
    codigo = str(codigo_generacion or "").strip().upper()
    params = {
        "ambiente": "00",
        "codGen": codigo,
        "fechaEmi": fecha,
    }
    return f"{HACIENDA_CONSULTA_PUBLICA_BASE_URL}?{urlencode(params)}"
