"""
Info Widget — overlay flotante always-on-top (PyQt6).

Muestra CPU, RAM, temperatura y servicios externos (Boostr.cl + clima).
Preferencias y posición se guardan al cerrar.
"""

from __future__ import annotations

import sys

from PyQt6.QtWidgets import QApplication

from ui.widget import InfoWidget


def main() -> int:
    app = QApplication(sys.argv)
    app.setQuitOnLastWindowClosed(True)

    widget = InfoWidget()
    widget.show()

    # Si no hay posición guardada, ubicar arriba a la derecha.
    if widget._settings.pos_x is None or widget._settings.pos_y is None:
        screen = app.primaryScreen()
        if screen is not None:
            geo = screen.availableGeometry()
            widget.move(geo.right() - widget.width() - 24, geo.top() + 24)

    return app.exec()


if __name__ == "__main__":
    raise SystemExit(main())
