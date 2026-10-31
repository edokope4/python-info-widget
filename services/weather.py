"""Servicio de clima usando la API pública wttr.in (sin API key)."""

from __future__ import annotations

from dataclasses import dataclass

import requests


@dataclass
class WeatherData:
    location: str
    description: str
    temperature_c: float | None
    feels_like_c: float | None
    humidity: int | None
    ok: bool
    error: str | None = None


class WeatherService:
    """Consulta el clima actual vía wttr.in (JSON)."""

    BASE_URL = "https://wttr.in"
    TIMEOUT = 12

    def __init__(self, location: str = "") -> None:
        # Cadena vacía = ubicación por IP / geo del servicio.
        self.location = location.strip()

    def get_weather(self) -> WeatherData:
        place = self.location or ""
        url = f"{self.BASE_URL}/{place}"
        params = {"format": "j1"}
        headers = {"User-Agent": "python-info-widget/1.0"}

        try:
            response = requests.get(
                url, params=params, headers=headers, timeout=self.TIMEOUT
            )
            response.raise_for_status()
            payload = response.json()
        except requests.RequestException as exc:
            return WeatherData(
                location=self.location or "—",
                description="Sin datos",
                temperature_c=None,
                feels_like_c=None,
                humidity=None,
                ok=False,
                error=str(exc),
            )

        try:
            current = payload["current_condition"][0]
            area = payload.get("nearest_area", [{}])[0]
            city = area.get("areaName", [{}])[0].get("value", self.location or "Local")
            region = area.get("region", [{}])[0].get("value", "")
            location = f"{city}, {region}".strip(", ") if region else city

            desc_list = current.get("weatherDesc", [{}])
            description = desc_list[0].get("value", "—") if desc_list else "—"

            return WeatherData(
                location=location,
                description=description,
                temperature_c=self._to_float(current.get("temp_C")),
                feels_like_c=self._to_float(current.get("FeelsLikeC")),
                humidity=self._to_int(current.get("humidity")),
                ok=True,
            )
        except (KeyError, IndexError, TypeError, ValueError) as exc:
            return WeatherData(
                location=self.location or "—",
                description="Sin datos",
                temperature_c=None,
                feels_like_c=None,
                humidity=None,
                ok=False,
                error=str(exc),
            )

    @staticmethod
    def _to_float(value: object) -> float | None:
        try:
            return float(value) if value is not None else None
        except (TypeError, ValueError):
            return None

    @staticmethod
    def _to_int(value: object) -> int | None:
        try:
            return int(value) if value is not None else None
        except (TypeError, ValueError):
            return None
