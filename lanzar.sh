#!/bin/bash
# Asistente de Appedit para Mac: pide los archivos con ventanas y lanza el montaje.
DIR="$(cd "$(dirname "$0")" && pwd)"
CONF="$DIR/ultima_vez.conf"
for b in /opt/homebrew/bin /usr/local/bin; do PATH="$b:$PATH"; done

elegir_archivos() {  # $1 = texto, $2 = "multiple" para permitir varios
  local multi=""
  [ "$2" = "multiple" ] && multi="with multiple selections allowed"
  osascript <<EOF
set l to choose file with prompt "$1" $multi
if class of l is not list then set l to {l}
set out to ""
repeat with f in l
  set out to out & POSIX path of f & linefeed
end repeat
return out
EOF
}
preguntar() {  # $1 = texto, $2 = valor por defecto
  osascript -e "text returned of (display dialog \"$1\" default answer \"$2\")"
}

USAR_ANTERIOR="No"
if [ -f "$CONF" ]; then
  USAR_ANTERIOR=$(osascript -e 'button returned of (display dialog "¿Usar los mismos archivos que la última vez?" buttons {"No", "Sí"} default button "Sí")')
fi

if [ "$USAR_ANTERIOR" = "Sí" ]; then
  source "$CONF"
else
  MESA=$(elegir_archivos "1/4 · Elige la grabación de la MESA (wav)") || exit 1
  CAM1=$(elegir_archivos "2/4 · Elige el vídeo o vídeos de la CÁMARA PRINCIPAL" multiple) || exit 1
  CAM2=$(elegir_archivos "3/4 · Elige el vídeo o vídeos de la SEGUNDA CÁMARA" multiple) || exit 1
  RECURSOS=$(osascript -e 'POSIX path of (choose folder with prompt "4/4 · Elige la CARPETA de clips de recurso")') || exit 1
  {
    printf 'MESA=%q\n' "$MESA"; printf 'CAM1=%q\n' "$CAM1"
    printf 'CAM2=%q\n' "$CAM2"; printf 'RECURSOS=%q\n' "$RECURSOS"
  } > "$CONF"
fi

PIEZAS=$(preguntar "¿Cuántas piezas quieres?" "6") || exit 1
DURACION=$(preguntar "¿Cuántos segundos dura cada pieza?" "60") || exit 1
MOMENTOS=$(preguntar "Minutos del set donde empezar cada pieza, separados por espacios (ej: 46:30 1:22:10). Déjalo vacío para que los elija solo." "") || exit 1

SALIDA="$HOME/Desktop/Appedit_$(date +%Y-%m-%d_%H-%M)"
ARGS=(--mesa "$(echo "$MESA" | head -1)" --recursos "$RECURSOS" --duracion "$DURACION"
      --salida "$SALIDA" --cache "$DIR/sincronizacion.json" --previa)
ARGS+=(--cam1); while IFS= read -r l; do [ -n "$l" ] && ARGS+=("$l"); done <<< "$CAM1"
ARGS+=(--cam2); while IFS= read -r l; do [ -n "$l" ] && ARGS+=("$l"); done <<< "$CAM2"
if [ -n "$MOMENTOS" ]; then
  ARGS+=(--momentos); for m in $MOMENTOS; do ARGS+=("$m"); done
else
  ARGS+=(--piezas "$PIEZAS")
fi

"$DIR/.venv/bin/python" "$DIR/appedit.py" "${ARGS[@]}" || {
  echo; echo "Algo ha fallado. Haz una captura de esta ventana y mándasela a Claude."; read -r -p "Pulsa Enter para cerrar"; exit 1; }

open "$SALIDA"
open "$SALIDA/resumen.html"
echo; echo "Listo. Los vídeos de vista previa y los .fcpxml están en: $SALIDA"
