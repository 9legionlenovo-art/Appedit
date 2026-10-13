#!/bin/bash
# Instala Appedit en un Mac. Uso (pegar en la app Terminal):
#   curl -fsSL https://raw.githubusercontent.com/9legionlenovo-art/appedit/claude/zen-franklin-hoyem1/instalar.sh | bash
set -e
RAMA="claude/zen-franklin-hoyem1"
DIR="$HOME/Appedit"

echo "== Instalando Appedit en $DIR =="

if ! command -v brew >/dev/null 2>&1; then
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$b" ] && eval "$("$b" shellenv)"
  done
fi
if ! command -v brew >/dev/null 2>&1; then
  echo "Instalando Homebrew (te pedirá la contraseña del Mac)..."
  /bin/bash -c "$(curl -fsSL https://raw.githubusercontent.com/Homebrew/install/HEAD/install.sh)" </dev/tty
  for b in /opt/homebrew/bin/brew /usr/local/bin/brew; do
    [ -x "$b" ] && eval "$("$b" shellenv)"
  done
fi

echo "Instalando ffmpeg y Python..."
brew install ffmpeg python@3.12

mkdir -p "$DIR"
echo "Descargando Appedit..."
curl -fsSL "https://github.com/9legionlenovo-art/appedit/archive/refs/heads/$RAMA.tar.gz" \
  | tar -xz -C "$DIR" --strip-components=1

PY="$(brew --prefix python@3.12)/bin/python3.12"
"$PY" -m venv "$DIR/.venv"
"$DIR/.venv/bin/pip" install -q --upgrade pip numpy

LANZADOR="$HOME/Desktop/Appedit.command"
cat > "$LANZADOR" <<EOF
#!/bin/bash
exec bash "$DIR/lanzar.sh"
EOF
chmod +x "$LANZADOR" "$DIR/lanzar.sh"

echo
echo "== Listo =="
echo "En el Escritorio tienes 'Appedit.command': haz doble clic para usarlo."
