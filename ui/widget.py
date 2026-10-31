"""Widget flotante always-on-top, frameless y arrastrable."""

from __future__ import annotations

from PyQt6.QtCore import QPoint, Qt, QThread, QTimer, pyqtSignal
from PyQt6.QtGui import QAction, QColor, QMouseEvent, QPainter, QPainterPath
from PyQt6.QtWidgets import (
    QApplication,
    QHBoxLayout,
    QLabel,
    QMenu,
    QVBoxLayout,
    QWidget,
)

from services.boostr import BoostrService, IndicatorResult, SantoralResult
from services.settings import (
    SERVICE_KEYS,
    SERVICE_LABELS,
    load_settings,
    save_settings,
)
from services.system_metrics import (
    SystemMetrics,
    SystemMetricsService,
    format_rate,
    format_uptime,
)
from services.weather import WeatherData, WeatherService
from ui.config_dialog import ConfigDialog


class _FetchWorker(QThread):
    """Worker genérico para no bloquear la UI al llamar APIs."""

    finished_ok = pyqtSignal(object)
    finished_err = pyqtSignal(str)

    def __init__(self, fn, parent=None) -> None:
        super().__init__(parent)
        self._fn = fn

    def run(self) -> None:
        try:
            self.finished_ok.emit(self._fn())
        except Exception as exc:  # noqa: BLE001
            self.finished_err.emit(str(exc))


class InfoWidget(QWidget):
    """Overlay: métricas locales + servicios Boostr/clima con on/off."""

    CORNER_RADIUS = 16

    def __init__(self) -> None:
        super().__init__()
        self._drag_offset: QPoint | None = None
        self._system = SystemMetricsService()
        self._weather = WeatherService()
        self._boostr = BoostrService()
        self._settings = load_settings()
        self._enabled = self._settings.services
        self._workers: list[QThread] = []
        self._service_rows: dict[str, QLabel] = {}

        self._setup_window()
        self._build_ui()
        self._apply_styles()
        self._setup_timers()
        self._restore_position()
        self._refresh_system()
        self._refresh_external()

    def _setup_window(self) -> None:
        self.setWindowTitle("Info Widget")
        self.setWindowFlags(
            Qt.WindowType.FramelessWindowHint
            | Qt.WindowType.WindowStaysOnTopHint
            | Qt.WindowType.Tool
        )
        self.setAttribute(Qt.WidgetAttribute.WA_TranslucentBackground)
        self.setFixedWidth(210)
        self.setContextMenuPolicy(Qt.ContextMenuPolicy.CustomContextMenu)
        self.customContextMenuRequested.connect(self._show_context_menu)

    def _build_ui(self) -> None:
        root = QVBoxLayout(self)
        root.setContentsMargins(10, 10, 10, 10)
        root.setSpacing(5)

        right = Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter

        header = QHBoxLayout()
        title = QLabel("Sistema")
        title.setObjectName("title")
        title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        self.close_btn = QLabel("✕")
        self.close_btn.setObjectName("closeBtn")
        self.close_btn.setCursor(Qt.CursorShape.PointingHandCursor)
        self.close_btn.setToolTip("Cerrar (o clic derecho → Cerrar)")
        self.close_btn.mousePressEvent = self._on_close_clicked  # type: ignore[method-assign]
        header.addWidget(title)
        header.addStretch()
        header.addWidget(self.close_btn)
        root.addLayout(header)

        self.cpu_label = QLabel("CPU: —")
        self.ram_label = QLabel("RAM: —")
        self.net_label = QLabel("↓ —  ↑ —")
        self.wifi_label = QLabel("WiFi: —")
        self.wifi_label.hide()
        self.eth_label = QLabel("Eth: —")
        self.eth_label.hide()
        self.net_status_label = QLabel("Sin conexión a redes")
        self.net_status_label.hide()
        self.ip_label = QLabel("IP: —")
        self.ip_label.hide()
        self.uptime_label = QLabel("Up: —")
        self.temp_label = QLabel("Temp: —")
        self.temp_label.hide()
        for label in (
            self.cpu_label,
            self.ram_label,
            self.net_label,
            self.wifi_label,
            self.eth_label,
            self.net_status_label,
            self.ip_label,
            self.uptime_label,
            self.temp_label,
        ):
            label.setObjectName("metric")
            label.setAlignment(right)
            root.addWidget(label)

        root.addWidget(self._sep())

        services_title = QLabel("Servicios")
        services_title.setObjectName("section")
        services_title.setAlignment(Qt.AlignmentFlag.AlignLeft | Qt.AlignmentFlag.AlignVCenter)
        root.addWidget(services_title)

        for key in SERVICE_KEYS:
            row = QLabel()
            row.setObjectName("metric")
            row.setWordWrap(True)
            row.setAlignment(right)
            self._service_rows[key] = row
            root.addWidget(row)
            if self._enabled.get(key, True):
                row.setText(f"● {SERVICE_LABELS[key]}: …")
            else:
                row.hide()

    @staticmethod
    def _sep() -> QLabel:
        sep = QLabel("────────────")
        sep.setObjectName("sep")
        sep.setAlignment(Qt.AlignmentFlag.AlignRight | Qt.AlignmentFlag.AlignVCenter)
        return sep

    def _apply_styles(self) -> None:
        self.setStyleSheet(
            """
            QLabel#title, QLabel#section {
                color: #E8EAED;
                font-size: 13px;
                font-weight: 700;
                letter-spacing: 0.3px;
            }
            QLabel#metric {
                color: #F1F3F4;
                font-size: 12px;
            }
            QLabel#sub {
                color: #9AA0A6;
                font-size: 11px;
            }
            QLabel#sep {
                color: #3C4043;
                font-size: 10px;
            }
            QLabel#hint {
                color: #5F6368;
                font-size: 10px;
                margin-top: 1px;
            }
            QLabel#closeBtn {
                color: #9AA0A6;
                font-size: 13px;
                padding: 2px 6px;
            }
            QLabel#closeBtn:hover {
                color: #F28B82;
            }
            """
        )

    def _setup_timers(self) -> None:
        self._system_timer = QTimer(self)
        self._system_timer.timeout.connect(self._refresh_system)
        self._external_timer = QTimer(self)
        self._external_timer.timeout.connect(self._refresh_external)
        self._apply_timer_intervals()

    def _apply_timer_intervals(self) -> None:
        system_ms = max(1, self._settings.system_interval_sec) * 1_000
        external_ms = max(1, self._settings.external_interval_min) * 60 * 1_000
        self._system_timer.start(system_ms)
        self._external_timer.start(external_ms)

    def _restore_position(self) -> None:
        if self._settings.pos_x is None or self._settings.pos_y is None:
            return
        self.move(self._settings.pos_x, self._settings.pos_y)

    def paintEvent(self, event) -> None:  # noqa: N802
        painter = QPainter(self)
        painter.setRenderHint(QPainter.RenderHint.Antialiasing)
        path = QPainterPath()
        path.addRoundedRect(
            0.0,
            0.0,
            float(self.width()),
            float(self.height()),
            float(self.CORNER_RADIUS),
            float(self.CORNER_RADIUS),
        )
        color = QColor(self._settings.bg_color)
        if not color.isValid():
            color = QColor("#0C1C3A")
        color.setAlpha(int(self._settings.bg_alpha))
        painter.fillPath(path, color)

    # --- Drag ---
    def mousePressEvent(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self._drag_offset = (
                event.globalPosition().toPoint() - self.frameGeometry().topLeft()
            )
            event.accept()
        else:
            super().mousePressEvent(event)

    def mouseMoveEvent(self, event: QMouseEvent) -> None:
        if self._drag_offset is not None and event.buttons() & Qt.MouseButton.LeftButton:
            self.move(event.globalPosition().toPoint() - self._drag_offset)
            event.accept()
        else:
            super().mouseMoveEvent(event)

    def mouseReleaseEvent(self, event: QMouseEvent) -> None:
        self._drag_offset = None
        super().mouseReleaseEvent(event)

    # --- Menú / cierre ---
    def _show_context_menu(self, pos) -> None:
        menu = QMenu(self)

        services_menu = menu.addMenu("Servicios")
        for key in SERVICE_KEYS:
            action = QAction(SERVICE_LABELS[key], self)
            action.setCheckable(True)
            action.setChecked(self._enabled.get(key, True))
            action.toggled.connect(lambda checked, k=key: self._toggle_service(k, checked))
            services_menu.addAction(action)

        config_action = QAction("Configuración…", self)
        config_action.triggered.connect(self._open_config)
        menu.addAction(config_action)

        menu.addSeparator()
        refresh = QAction("Actualizar ahora", self)
        refresh.triggered.connect(self._refresh_external)
        menu.addAction(refresh)
        menu.addSeparator()
        close = QAction("Cerrar", self)
        close.triggered.connect(self.close)
        menu.addAction(close)
        menu.exec(self.mapToGlobal(pos))

    def _open_config(self) -> None:
        dialog = ConfigDialog(self._settings, self)
        if dialog.exec():
            dialog.apply_to(self._settings)
            self._apply_timer_intervals()
            self.update()
            self._persist_settings()

    def _toggle_service(self, key: str, enabled: bool) -> None:
        self._enabled[key] = enabled
        self._settings.services = self._enabled
        self._persist_settings()
        row = self._service_rows[key]
        if enabled:
            row.setText(f"● {SERVICE_LABELS[key]}: cargando…")
            row.setStyleSheet("color: #F1F3F4; font-size: 12px;")
            row.show()
            self._fetch_one(key)
        else:
            row.hide()
            row.clear()
        self.adjustSize()

    def _paint_active_row(self, key: str, text: str) -> None:
        if not self._enabled.get(key, True):
            return
        row = self._service_rows[key]
        row.setText(f"● {text}")
        row.setStyleSheet("color: #F1F3F4; font-size: 12px;")
        row.show()
        self.adjustSize()

    def _hide_service_row(self, key: str) -> None:
        row = self._service_rows.get(key)
        if row is None:
            return
        row.hide()
        row.clear()
        self.adjustSize()

    def _on_close_clicked(self, event: QMouseEvent) -> None:
        if event.button() == Qt.MouseButton.LeftButton:
            self.close()

    def closeEvent(self, event) -> None:  # noqa: N802
        self._persist_settings()
        super().closeEvent(event)

    def _persist_settings(self) -> None:
        pos = self.pos()
        self._settings.pos_x = pos.x()
        self._settings.pos_y = pos.y()
        self._settings.services = self._enabled
        save_settings(self._settings)

    # --- Datos ---
    def _refresh_system(self) -> None:
        self._apply_system(self._system.get_metrics())

    def _apply_system(self, m: SystemMetrics) -> None:
        self.cpu_label.setText(f"CPU: {m.cpu_percent:.0f}%")
        self.ram_label.setText(
            f"RAM: {m.ram_percent:.0f}%  ({m.ram_used_gb:.1f}/{m.ram_total_gb:.1f} GB)"
        )
        self.net_label.setText(
            f"↓ {format_rate(m.net_down_bps)}  ↑ {format_rate(m.net_up_bps)}"
        )
        has_wifi = bool(m.wifi_ssid)
        has_eth = bool(m.ethernet_name)

        if has_wifi:
            self.wifi_label.setText(f"WiFi: {m.wifi_ssid}")
            self.wifi_label.show()
        else:
            self.wifi_label.hide()

        if has_eth:
            self.eth_label.setText(f"Eth: {m.ethernet_name}")
            self.eth_label.show()
        else:
            self.eth_label.hide()

        if has_wifi or has_eth:
            self.net_status_label.hide()
            if m.ip_address:
                self.ip_label.setText(f"IP: {m.ip_address}")
                self.ip_label.show()
            else:
                self.ip_label.hide()
        else:
            self.net_status_label.setText("Sin conexión a redes")
            self.net_status_label.show()
            self.ip_label.hide()

        self.uptime_label.setText(f"Up: {format_uptime(m.uptime_seconds)}")
        if m.temperature_c is None:
            self.temp_label.hide()
        else:
            self.temp_label.setText(
                f"Temp: {m.temperature_c:.0f}°C  ({m.temperature_label})"
            )
            self.temp_label.show()
        self.adjustSize()


    def _refresh_external(self) -> None:
        for key in SERVICE_KEYS:
            row = self._service_rows[key]
            if self._enabled.get(key, True):
                row.setText(f"● {SERVICE_LABELS[key]}: cargando…")
                row.setStyleSheet("color: #F1F3F4; font-size: 12px;")
                row.show()
                self._fetch_one(key)
            else:
                row.hide()
                row.clear()
        self.adjustSize()

    def _fetch_one(self, key: str) -> None:
        if key == "weather":
            self._start_worker(self._weather.get_weather, self._apply_weather)
        elif key == "santoral":
            self._start_worker(self._boostr.get_santoral, self._apply_santoral)
        elif key in BoostrService.INDICATORS:
            self._start_worker(
                lambda k=key: self._boostr.get_indicator(k),
                self._apply_indicator,
            )

    def _start_worker(self, fn, on_ok) -> None:
        worker = _FetchWorker(fn, self)

        def _cleanup() -> None:
            if worker in self._workers:
                self._workers.remove(worker)
            worker.deleteLater()

        worker.finished_ok.connect(on_ok)
        worker.finished.connect(_cleanup)
        self._workers.append(worker)
        worker.start()

    def _apply_weather(self, data: WeatherData) -> None:
        if not self._enabled.get("weather", True):
            return
        if not data.ok or data.temperature_c is None:
            self._hide_service_row("weather")
            return
        icon = self._weather_icon(data.description)
        self._paint_active_row(
            "weather", f"Clima: {icon} {data.temperature_c:.0f}°C"
        )

    @staticmethod
    def _weather_icon(description: str) -> str:
        """Mapea la descripción del clima a un icono corto."""
        text = (description or "").casefold()
        rules = (
            (("tormenta", "thunder", "storm"), "⛈"),
            (("nieve", "snow", "sleet", "blizzard"), "❄"),
            (("lluvia", "rain", "drizzle", "chubasco", "shower"), "🌧"),
            (("niebla", "neblina", "mist", "fog", "haze"), "🌫"),
            (("nublado", "nubes", "cloud", "overcast"), "☁"),
            (("parcial", "partly", "dispers"), "⛅"),
            (("despejado", "soleado", "clear", "sunny", "fair"), "☀"),
        )
        for keywords, icon in rules:
            if any(k in text for k in keywords):
                return icon
        return "🌤"

    def _apply_santoral(self, data: SantoralResult) -> None:
        if not self._enabled.get("santoral", True):
            return
        if not data.ok or not data.names:
            self._hide_service_row("santoral")
            return
        names = ", ".join(data.names[:4])
        if len(data.names) > 4:
            names += "…"
        self._paint_active_row("santoral", f"Santoral: {names}")

    def _apply_indicator(self, data: IndicatorResult) -> None:
        if not self._enabled.get(data.key, True):
            return
        if not data.ok or data.value is None:
            self._hide_service_row(data.key)
            return
        value_txt = (
            f"${data.value:,.2f}".replace(",", "X").replace(".", ",").replace("X", ".")
        )
        self._paint_active_row(data.key, f"{data.label}: {value_txt}")
