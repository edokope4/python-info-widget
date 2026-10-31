"""Servicios externos Boostr.cl (santoral e indicadores económicos Chile).

Endpoints documentados en doc/services.txt:
  - GET https://api.boostr.cl/santorales/hoy.json
  - GET https://api.boostr.cl/economy/indicator/{dolar|euro|uf|utm}.json
"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Any

import requests


BASE_URL = "https://api.boostr.cl"
TIMEOUT = 12
HEADERS = {
    "accept": "application/json",
    "User-Agent": "python-info-widget/1.0",
}


@dataclass
class IndicatorResult:
    key: str
    label: str
    value: float | None
    date: str | None
    ok: bool
    error: str | None = None


@dataclass
class SantoralResult:
    names: list[str]
    ok: bool
    error: str | None = None


class BoostrService:
    """Cliente para las APIs públicas de Boostr.cl."""

    INDICATORS = {
        "dolar": "Dólar",
        "euro": "Euro",
        "uf": "UF",
        "utm": "UTM",
    }

    def get_indicator(self, key: str) -> IndicatorResult:
        label = self.INDICATORS.get(key, key.upper())
        url = f"{BASE_URL}/economy/indicator/{key}.json"
        try:
            payload = self._get_json(url)
            data = payload.get("data") if isinstance(payload, dict) else None
            if not isinstance(data, dict):
                raise ValueError("Respuesta sin data")
            value = float(data["value"])
            date = str(data.get("date") or "") or None
            return IndicatorResult(
                key=key, label=label, value=value, date=date, ok=True
            )
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            return IndicatorResult(
                key=key,
                label=label,
                value=None,
                date=None,
                ok=False,
                error=str(exc),
            )

    def get_santoral(self) -> SantoralResult:
        url = f"{BASE_URL}/santorales/hoy.json"
        try:
            payload = self._get_json(url)
            names = self._parse_santoral(payload)
            if not names:
                return SantoralResult(
                    names=[], ok=False, error="Sin nombres en la respuesta"
                )
            return SantoralResult(names=names, ok=True)
        except (requests.RequestException, KeyError, TypeError, ValueError) as exc:
            return SantoralResult(names=[], ok=False, error=str(exc))

    def _get_json(self, url: str) -> Any:
        response = requests.get(url, headers=HEADERS, timeout=TIMEOUT)
        response.raise_for_status()
        return response.json()

    @staticmethod
    def _parse_santoral(payload: Any) -> list[str]:
        """Normaliza distintas formas posibles de la respuesta del santoral."""
        if isinstance(payload, dict):
            data = payload.get("data", payload)
            if isinstance(data, dict):
                for key in ("santorales", "nombres", "names", "saints"):
                    if key in data and isinstance(data[key], list):
                        return [str(n).strip() for n in data[key] if str(n).strip()]
                for key in ("nombre", "name", "santoral"):
                    if key in data and data[key]:
                        return [str(data[key]).strip()]
            if isinstance(data, list):
                return [str(n).strip() for n in data if str(n).strip()]
        if isinstance(payload, list):
            return [str(n).strip() for n in payload if str(n).strip()]
        return []
