# Appedit

Monta videosets de DJ con el estilo de edición descrito en [ESTILO.md](ESTILO.md) y genera timelines para importar en DaVinci Resolve.

Qué hace:

1. Sincroniza las cámaras con la grabación de la mesa comparando el audio.
2. Elige los momentos del set con más energía, o los que tú le digas.
3. Detecta el tempo y corta en el beat, alternando cámara principal, segunda cámara y un clip de recurso, sin repetir fuente.
4. Pone un zoom de 1.25–1.32× en los planos de cámara.
5. Guarda un `.fcpxml` por pieza y un `resumen.html` con los cortes dibujados.

## Instalación (Mac, una sola vez)

1. Abre la app **Terminal** (Cmd + Espacio, escribe "Terminal" y pulsa Enter).
2. Pega esta línea y pulsa Enter:

   ```bash
   curl -fsSL https://raw.githubusercontent.com/9legionlenovo-art/appedit/claude/zen-franklin-hoyem1/instalar.sh | bash
   ```

3. Si te pide la contraseña, es la del Mac (al escribirla no se ve nada; es normal).
4. Tarda unos minutos. Al acabar aparece **Appedit.command** en el Escritorio.

## Uso

1. Doble clic en **Appedit.command** del Escritorio.
2. Te va pidiendo con ventanas: la grabación de la mesa, los vídeos de la cámara principal, los de la segunda cámara y la carpeta de clips de recurso. La siguiente vez te pregunta si usar los mismos.
3. Le dices cuántas piezas y cuántos segundos, o en qué minutos del set empezar.
4. Al terminar se abre una carpeta en el Escritorio con:
   - `pieza_XX_previa.mp4`: el montaje en vídeo para verlo ya.
   - `pieza_XX.fcpxml`: la timeline para DaVinci (**File → Import → Timeline…**).
   - `resumen.html`: los cortes dibujados.

La primera vez tarda más porque analiza el audio de todo el set. Las siguientes reutiliza la sincronización.

### Desde la Terminal (avanzado)

```bash
~/Appedit/.venv/bin/python ~/Appedit/appedit.py \
  --mesa "/Volumes/orico 1t/fernanda likas/261108_0068.wav" \
  --cam1 "/Volumes/orico 1t/fernanda likas/C5651.MP4" \
  --cam2 "/Volumes/orico 1t/fernanda likas/C5802.MP4" "/Volumes/orico 1t/fernanda likas/C5803.MP4" \
  --recursos "/Volumes/orico 1t/fernanda likas/clips" \
  --piezas 6 --duracion 60 --previa --salida ~/Desktop/appedit_salida
```

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
| `--previa` | Renderiza también un mp4 de cada pieza para verlo sin DaVinci |
| `--semilla 7` | Repetir exactamente el mismo montaje. Sin ella, cada ejecución sale distinta |

## Limitaciones de esta primera versión

- No ve la imagen: no sabe si un plano está desenfocado o tapado. Hay que revisar en DaVinci.
- Si la consola avisa de que una sincronización es "dudosa", comprueba esa cámara a mano.
- La corrección de color no se aplica: se hace en DaVinci como siempre.
