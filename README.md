# Info Widget

Widget flotante de escritorio para Windows, construido con **PyQt6**. Muestra métricas del sistema y servicios externos en una ventana siempre visible, sin bordes y arrastrable.

## Características

### Sistema
- Uso de CPU y RAM
- Velocidad de red (↓ download / ↑ upload)
- WiFi (SSID), Ethernet e IP local
- Uptime
- Temperatura (si hay sensores disponibles)

### Servicios externos
- Clima ([wttr.in](https://wttr.in))
- Santoral, Dólar, Euro, UF y UTM ([Boostr.cl](https://api.boostr.cl))

Cada servicio se puede activar o desactivar desde el menú contextual. Si un servicio no responde, su línea se oculta automáticamente.

### Interfaz
- Ventana frameless, always-on-top y semi-transparente
- Arrastrable con clic izquierdo
- Menú contextual (clic derecho): servicios, configuración y cierre
- Color de fondo y opacidad configurables
- Preferencias persistentes (`config.json`)

## Requisitos

- Python 3.10+
- Windows (recomendado; WiFi vía `netsh`)

## Instalación

```powershell
cd python-info-widget
python -m pip install -r requirements.txt
```

## Ejecutar

```powershell
python main.py
```

## Compilar a ejecutable

```powershell
.\build.ps1
```

El binario queda en `dist\InfoWidget.exe`.

## Estructura

```
python-info-widget/
├── main.py                 # Punto de entrada
├── requirements.txt
├── build.ps1 / build.bat   # Compilación con PyInstaller
├── doc/
│   └── services.txt        # Endpoints Boostr documentados
├── services/
│   ├── system_metrics.py   # CPU, RAM, red, WiFi, IP, uptime
│   ├── weather.py          # Clima (wttr.in)
│   ├── boostr.py           # Santoral e indicadores Chile
│   └── settings.py         # Preferencias persistentes
└── ui/
    ├── widget.py           # Overlay flotante
    └── config_dialog.py    # Diálogo de configuración
```

## Configuración

Clic derecho → **Configuración…**

| Opción | Descripción |
|--------|-------------|
| Sistema | Intervalo de métricas locales (1–60 s) |
| Servicios | Intervalo de APIs externas (1–180 min) |
| Color / Opacidad | Fondo semi-transparente del widget |

Al cerrar la aplicación se guardan: servicios activos, intervalos, color, opacidad y posición de la ventana.

## Licencia

Uso personal / educativo.
