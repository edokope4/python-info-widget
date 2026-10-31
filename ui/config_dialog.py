"""Diálogo de configuración del widget."""

from __future__ import annotations

from PyQt6.QtCore import Qt
from PyQt6.QtGui import QColor
from PyQt6.QtWidgets import (
    QColorDialog,
    QDialog,
    QDialogButtonBox,
    QFormLayout,
    QHBoxLayout,
    QLabel,
    QPushButton,
    QSpinBox,
    QVBoxLayout,
    QWidget,
)

from services.settings import DEFAULT_BG_ALPHA, DEFAULT_BG_COLOR, AppSettings


class ConfigDialog(QDialog):
    """Permite ajustar intervalos y color de fondo."""

    def __init__(self, settings: AppSettings, parent=None) -> None:
        super().__init__(parent)
        self.setWindowTitle("Configuración")
        self.setModal(True)
        self.setWindowFlags(self.windowFlags() | Qt.WindowType.WindowStaysOnTopHint)
        self.setFixedWidth(300)

        self._color = QColor(settings.bg_color)
        if not self._color.isValid():
            self._color = QColor(DEFAULT_BG_COLOR)

        root = QVBoxLayout(self)

        intervals_title = QLabel("Intervalos de actualización")
        intervals_title.setStyleSheet("font-weight: 600; margin-bottom: 4px;")
        root.addWidget(intervals_title)

        form = QFormLayout()
        form.setSpacing(10)

        self.system_spin = QSpinBox()
        self.system_spin.setRange(1, 60)
        self.system_spin.setSuffix(" s")
        self.system_spin.setValue(settings.system_interval_sec)
        self.system_spin.setToolTip("CPU, RAM, red, IP, uptime…")
        form.addRow("Sistema:", self.system_spin)

        self.external_spin = QSpinBox()
        self.external_spin.setRange(1, 180)
        self.external_spin.setSuffix(" min")
        self.external_spin.setValue(settings.external_interval_min)
        self.external_spin.setToolTip("Clima, dólar, euro, UF, UTM, santoral…")
        form.addRow("Servicios:", self.external_spin)

        root.addLayout(form)

        appearance_title = QLabel("Apariencia")
        appearance_title.setStyleSheet("font-weight: 600; margin-top: 8px; margin-bottom: 4px;")
        root.addWidget(appearance_title)

        appearance = QFormLayout()
        appearance.setSpacing(10)

        color_row = QWidget()
        color_layout = QHBoxLayout(color_row)
        color_layout.setContentsMargins(0, 0, 0, 0)
        color_layout.setSpacing(8)

        self.color_preview = QLabel()
        self.color_preview.setFixedSize(28, 22)
        self.color_btn = QPushButton("Elegir…")
        self.color_btn.clicked.connect(self._pick_color)
        self.reset_color_btn = QPushButton("Reset")
        self.reset_color_btn.setToolTip("Volver al azul oscuro por defecto")
        self.reset_color_btn.clicked.connect(self._reset_color)
        color_layout.addWidget(self.color_preview)
        color_layout.addWidget(self.color_btn)
        color_layout.addWidget(self.reset_color_btn)
        color_layout.addStretch()
        appearance.addRow("Color:", color_row)

        self.alpha_spin = QSpinBox()
        self.alpha_spin.setRange(40, 255)
        self.alpha_spin.setValue(settings.bg_alpha)
        self.alpha_spin.setToolTip("Transparencia del fondo (40 = más transparente)")
        self.alpha_spin.valueChanged.connect(self._refresh_preview)
        appearance.addRow("Opacidad:", self.alpha_spin)

        root.addLayout(appearance)
        self._refresh_preview()

        note = QLabel("Las preferencias se guardan al cerrar la app.")
        note.setStyleSheet("color: #888; font-size: 11px;")
        note.setWordWrap(True)
        root.addWidget(note)

        buttons = QDialogButtonBox(
            QDialogButtonBox.StandardButton.Ok | QDialogButtonBox.StandardButton.Cancel
        )
        buttons.accepted.connect(self.accept)
        buttons.rejected.connect(self.reject)
        root.addWidget(buttons)

    def _pick_color(self) -> None:
        chosen = QColorDialog.getColor(
            self._color, self, "Color de fondo", QColorDialog.ColorDialogOption.ShowAlphaChannel
        )
        if chosen.isValid():
            self._color = QColor(chosen.red(), chosen.green(), chosen.blue())
            if chosen.alpha() != 255:
                self.alpha_spin.setValue(chosen.alpha())
            self._refresh_preview()

    def _reset_color(self) -> None:
        self._color = QColor(DEFAULT_BG_COLOR)
        self.alpha_spin.setValue(DEFAULT_BG_ALPHA)
        self._refresh_preview()

    def _refresh_preview(self) -> None:
        c = QColor(self._color)
        c.setAlpha(self.alpha_spin.value())
        self.color_preview.setStyleSheet(
            f"background-color: rgba({c.red()}, {c.green()}, {c.blue()}, {c.alpha()});"
            "border: 1px solid #555; border-radius: 3px;"
        )

    def apply_to(self, settings: AppSettings) -> None:
        settings.system_interval_sec = self.system_spin.value()
        settings.external_interval_min = self.external_spin.value()
        settings.bg_color = self._color.name().upper()
        settings.bg_alpha = self.alpha_spin.value()
