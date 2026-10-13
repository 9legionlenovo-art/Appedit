# Appedit

Monta videosets de DJ con el estilo de edición descrito en [ESTILO.md](ESTILO.md) y genera timelines para importar en DaVinci Resolve.

Qué hace:

1. Sincroniza las cámaras con la grabación de la mesa comparando el audio.
2. Elige los momentos del set con más energía, o los que tú le digas.
3. Detecta el tempo y corta en el beat, alternando cámara principal, segunda cámara y un clip de recurso, sin repetir fuente.
4. Pone un zoom de 1.25–1.32× en los planos de cámara.
5. Guarda un `.fcpxml` por pieza y un `resumen.html` con los cortes dibujados.

## Instalación (Mac, una sola vez)

Abre la app **Terminal** y pega:

```bash
# Homebrew (si no lo tienes): https://brew.sh
brew install ffmpeg python
pip3 install numpy
```

Descarga este repositorio (botón verde **Code → Download ZIP** en GitHub) y descomprímelo, por ejemplo en `~/Appedit`.

## Uso

```bash
cd ~/Appedit
python3 appedit.py \
  --mesa "/Volumes/orico 1t/fernanda likas/261108_0068.wav" \
  --cam1 "/Volumes/orico 1t/fernanda likas/C5651.MP4" \
  --cam2 "/Volumes/orico 1t/fernanda likas/C5802.MP4" "/Volumes/orico 1t/fernanda likas/C5803.MP4" \
  --recursos "/Volumes/orico 1t/fernanda likas/clips" \
  --piezas 6 --duracion 60 \
  --salida ~/Desktop/appedit_salida
```

Consejo: en la Terminal puedes arrastrar un archivo o una carpeta desde Finder y se escribe su ruta sola.

Después, en DaVinci: **File → Import → Timeline…** y elige cada `.fcpxml` de la carpeta de salida. Si DaVinci pregunta por los medios, deja que los busque en el disco.

La primera vez tarda más porque analiza el audio de todo el set. La sincronización se guarda en `sincronizacion.json` dentro de la carpeta de salida y se reutiliza en las siguientes ejecuciones.

## Opciones

| Opción | Para qué |
|---|---|
| `--momentos 46:30 1:22:10` | Inicio de cada pieza en el audio de la mesa, en lugar de elegirlos automáticamente |
| `--piezas 6` | Cuántas piezas generar en modo automático |
| `--duracion 60` | Segundos por pieza |
| `--bpm 120-135` | Rango de tempo donde buscar el beat (por defecto 110-150) |
| `--sin-beat` | Cortar sin ajustarse al beat |
| `--zoom-animado` | Parte de los planos de cámara con zoom animado de 1.0× a 1.25× |
| `--fps 25` | fps de la timeline (por defecto 23.976, como en su proyecto) |
| `--resolucion 1280x720` | Resolución de la timeline (por defecto 1920x1080) |
| `--semilla 7` | Repetir exactamente el mismo montaje. Sin ella, cada ejecución sale distinta |

## Limitaciones de esta primera versión

- No ve la imagen: no sabe si un plano está desenfocado o tapado. Hay que revisar en DaVinci.
- Si la consola avisa de que una sincronización es "dudosa", comprueba esa cámara a mano.
- La corrección de color no se aplica: se hace en DaVinci como siempre.
