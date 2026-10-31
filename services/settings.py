"""Persistencia de preferencias del widget."""

from __future__ import annotations

import json
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path

# Claves usadas por el widget (coinciden con doc/services.txt + clima).
SERVICE_KEYS = (
    "santoral",
    "dolar",
    "euro",
    "uf",
    "utm",
    "weather",
)

SERVICE_LABELS = {
    "santoral": "Santoral",
    "dolar": "Dólar",
    "euro": "Euro",
    "uf": "UF",
    "utm": "UTM",
    "weather": "Clima",
}

DEFAULT_SERVICES: dict[str, bool] = {key: True for key in SERVICE_KEYS}
DEFAULT_BG_COLOR = "#0C1C3A"
DEFAULT_BG_ALPHA = 200


@dataclass
class AppSettings:
    services: dict[str, bool] = field(default_factory=lambda: dict(DEFAULT_SERVICES))
    system_interval_sec: int = 2
    external_interval_min: int = 12
    bg_color: str = DEFAULT_BG_COLOR
    bg_alpha: int = DEFAULT_BG_ALPHA
    pos_x: int | None = None
    pos_y: int | None = None


def _config_path() -> Path:
    # En .exe de PyInstaller guardar junto al ejecutable; en desarrollo, en la raíz del proyecto.
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent / "config.json"
    return Path(__file__).resolve().parent.parent / "config.json"


def load_settings() -> AppSettings:
    settings = AppSettings()
    path = _config_path()
    if not path.exists():
        return settings
    try:
        raw = json.loads(path.read_text(encoding="utf-8"))
        if not isinstance(raw, dict):
            return settings

        services = raw.get("services", {})
        if isinstance(services, dict):
            for key in SERVICE_KEYS:
                if key in services:
                    settings.services[key] = bool(services[key])

        settings.system_interval_sec = _clamp_int(
            raw.get("system_interval_sec", settings.system_interval_sec), 1, 60, 2
        )
        settings.external_interval_min = _clamp_int(
            raw.get("external_interval_min", settings.external_interval_min), 1, 180, 12
        )
        settings.bg_color = _normalize_hex(
            raw.get("bg_color", settings.bg_color), DEFAULT_BG_COLOR
        )
        settings.bg_alpha = _clamp_int(
            raw.get("bg_alpha", settings.bg_alpha), 40, 255, DEFAULT_BG_ALPHA
        )

        if "pos_x" in raw and "pos_y" in raw:
            settings.pos_x = int(raw["pos_x"])
            settings.pos_y = int(raw["pos_y"])
    except (OSError, json.JSONDecodeError, TypeError, ValueError):
        pass
    return settings


def save_settings(settings: AppSettings) -> None:
    path = _config_path()
    payload = {
        "services": {
            key: bool(settings.services.get(key, DEFAULT_SERVICES[key]))
            for key in SERVICE_KEYS
        },
        "system_interval_sec": int(settings.system_interval_sec),
        "external_interval_min": int(settings.external_interval_min),
        "bg_color": _normalize_hex(settings.bg_color, DEFAULT_BG_COLOR),
        "bg_alpha": _clamp_int(settings.bg_alpha, 40, 255, DEFAULT_BG_ALPHA),
        "pos_x": settings.pos_x,
        "pos_y": settings.pos_y,
    }
    path.write_text(
        json.dumps(payload, indent=2, ensure_ascii=False) + "\n",
        encoding="utf-8",
    )


def _clamp_int(value: object, low: int, high: int, default: int) -> int:
    try:
        n = int(value)  # type: ignore[arg-type]
    except (TypeError, ValueError):
        return default
    return max(low, min(high, n))


def _normalize_hex(value: object, default: str) -> str:
    if not isinstance(value, str):
        return default
    text = value.strip()
    if re.fullmatch(r"#?[0-9A-Fa-f]{6}", text):
        if not text.startswith("#"):
            text = f"#{text}"
        return text.upper()
    return default
