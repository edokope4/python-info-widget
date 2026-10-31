"""Servicio de métricas del sistema: CPU, RAM, red, WiFi/Ethernet, IP y temperatura."""

from __future__ import annotations

import socket
import subprocess
import sys
import time
from dataclasses import dataclass

import psutil

# Evita ventana de consola al llamar netsh en Windows.
_CREATE_NO_WINDOW = 0x08000000 if sys.platform == "win32" else 0


@dataclass
class SystemMetrics:
    cpu_percent: float
    ram_percent: float
    ram_used_gb: float
    ram_total_gb: float
    net_down_bps: float  # bytes/s recibidos
    net_up_bps: float  # bytes/s enviados
    uptime_seconds: float
    wifi_ssid: str | None
    ethernet_name: str | None
    ip_address: str | None
    temperature_c: float | None
    temperature_label: str


class SystemMetricsService:
    """Obtiene métricas locales mediante psutil / netsh."""

    LINK_CACHE_SECONDS = 15.0

    def __init__(self) -> None:
        self._prev_net = psutil.net_io_counters()
        self._prev_net_ts = time.monotonic()
        psutil.cpu_percent(interval=None)
        self._link_cache_ts = 0.0
        self._wifi_ssid: str | None = None
        self._ethernet_name: str | None = None
        self._ip_address: str | None = None

    def get_metrics(self) -> SystemMetrics:
        cpu = psutil.cpu_percent(interval=None)
        mem = psutil.virtual_memory()
        used_gb = mem.used / (1024**3)
        total_gb = mem.total / (1024**3)
        down_bps, up_bps = self._net_rates()
        uptime = max(time.time() - psutil.boot_time(), 0.0)
        wifi, eth, ip = self._link_info()
        temp_c, temp_label = self._read_temperature()

        return SystemMetrics(
            cpu_percent=cpu,
            ram_percent=mem.percent,
            ram_used_gb=used_gb,
            ram_total_gb=total_gb,
            net_down_bps=down_bps,
            net_up_bps=up_bps,
            uptime_seconds=uptime,
            wifi_ssid=wifi,
            ethernet_name=eth,
            ip_address=ip,
            temperature_c=temp_c,
            temperature_label=temp_label,
        )

    def _net_rates(self) -> tuple[float, float]:
        now = time.monotonic()
        current = psutil.net_io_counters()
        elapsed = max(now - self._prev_net_ts, 1e-6)
        down = (current.bytes_recv - self._prev_net.bytes_recv) / elapsed
        up = (current.bytes_sent - self._prev_net.bytes_sent) / elapsed
        self._prev_net = current
        self._prev_net_ts = now
        return max(down, 0.0), max(up, 0.0)

    def _link_info(self) -> tuple[str | None, str | None, str | None]:
        now = time.monotonic()
        if now - self._link_cache_ts < self.LINK_CACHE_SECONDS:
            return self._wifi_ssid, self._ethernet_name, self._ip_address

        self._wifi_ssid = self._read_wifi_ssid()
        self._ethernet_name = self._read_ethernet_name()
        self._ip_address = self._read_primary_ip()
        self._link_cache_ts = now
        return self._wifi_ssid, self._ethernet_name, self._ip_address

    def _read_wifi_ssid(self) -> str | None:
        if sys.platform == "win32":
            return self._windows_wifi_ssid()
        return None

    def _windows_wifi_ssid(self) -> str | None:
        try:
            result = subprocess.run(
                ["netsh", "wlan", "show", "interfaces"],
                capture_output=True,
                text=True,
                encoding="utf-8",
                errors="replace",
                timeout=4,
                creationflags=_CREATE_NO_WINDOW,
            )
        except (OSError, subprocess.SubprocessError):
            return None

        ssid: str | None = None
        connected = False
        for raw in result.stdout.splitlines():
            line = raw.strip()
            lower = line.casefold()
            if lower.startswith("state") or lower.startswith("estado"):
                value = line.split(":", 1)[-1].strip().casefold()
                connected = value in {"connected", "conectado"}
            if (
                (lower.startswith("ssid") or "ssid" in lower)
                and "bssid" not in lower
            ):
                value = line.split(":", 1)[-1].strip()
                if value:
                    ssid = value
        return ssid if connected or ssid else None

    def _read_ethernet_name(self) -> str | None:
        stats = psutil.net_if_stats()
        addrs = psutil.net_if_addrs()
        for name, st in stats.items():
            if not st.isup:
                continue
            low = name.casefold()
            if any(
                skip in low
                for skip in (
                    "loopback",
                    "vethernet",
                    "virtual",
                    "vpn",
                    "bluetooth",
                    "wi-fi",
                    "wifi",
                    "wlan",
                    "wireless",
                )
            ):
                continue
            if not any(k in low for k in ("ethernet", "eth", "lan", "local area")):
                continue
            if self._has_ipv4(addrs.get(name, [])):
                return name
        return None

    @staticmethod
    def _has_ipv4(addr_list: list) -> bool:
        for addr in addr_list:
            if getattr(addr, "family", None) == socket.AF_INET:
                ip = addr.address or ""
                if ip and not ip.startswith("127."):
                    return True
        return False

    @staticmethod
    def _read_primary_ip() -> str | None:
        try:
            with socket.socket(socket.AF_INET, socket.SOCK_DGRAM) as sock:
                sock.connect(("8.8.8.8", 80))
                ip = sock.getsockname()[0]
                if ip and not ip.startswith("127."):
                    return ip
        except OSError:
            pass

        for addrs in psutil.net_if_addrs().values():
            for addr in addrs:
                if getattr(addr, "family", None) == socket.AF_INET:
                    ip = addr.address or ""
                    if ip and not ip.startswith("127."):
                        return ip
        return None

    def _read_temperature(self) -> tuple[float | None, str]:
        try:
            sensors = psutil.sensors_temperatures()
        except (AttributeError, OSError, RuntimeError):
            return None, ""

        if not sensors:
            return None, ""

        preferred = ("coretemp", "k10temp", "cpu_thermal", "acpitz", "nvme")
        for name in preferred:
            entries = sensors.get(name)
            if entries:
                temps = [e.current for e in entries if e.current is not None]
                if temps:
                    return max(temps), name

        for name, entries in sensors.items():
            temps = [e.current for e in entries if e.current is not None]
            if temps:
                return max(temps), name

        return None, ""


def format_rate(bps: float) -> str:
    """Formatea bytes/s a unidad legible (KB/s, MB/s, …)."""
    units = ("B/s", "KB/s", "MB/s", "GB/s")
    value = float(bps)
    for unit in units:
        if value < 1024 or unit == units[-1]:
            if unit == "B/s":
                return f"{value:.0f} {unit}"
            return f"{value:.1f} {unit}"
        value /= 1024
    return f"{value:.1f} GB/s"


def format_uptime(seconds: float) -> str:
    """Formatea uptime compacto: 3d 4h, 5h 12m, 42m, …"""
    total = int(seconds)
    days, rem = divmod(total, 86_400)
    hours, rem = divmod(rem, 3_600)
    minutes, _ = divmod(rem, 60)
    if days > 0:
        return f"{days}d {hours}h"
    if hours > 0:
        return f"{hours}h {minutes}m"
    return f"{minutes}m"
