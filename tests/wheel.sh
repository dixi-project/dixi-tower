#!/usr/bin/env bash
# Prueba de humo contra el wheel ya construido, instalado con uv en una carpeta
# temporal (no toca las herramientas de uv de quien la ejecuta).
#
#   uv build && tests/wheel.sh [ruta-del-wheel]   (por defecto, el único dist/*.whl)
set -euo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WHL="${1:-}"
if [ -z "$WHL" ]; then
  set -- "$AQUI"/dist/*.whl
  if [ "$#" -ne 1 ] || [ ! -f "$1" ]; then echo "Hace falta un solo wheel en dist/ (uv build) o su ruta como argumento." >&2; exit 1; fi
  WHL="$1"
fi
T="$(mktemp -d "${TMPDIR:-/tmp}/dixi-tower-wheel.XXXXXX")"
trap 'rm -rf "$T"' EXIT
export UV_TOOL_DIR="$T/herramientas" UV_TOOL_BIN_DIR="$T/bin"
echo "Instalando $(basename "$WHL")"
uv tool install --quiet "$WHL"
PKG="$(ls -d "$UV_TOOL_DIR"/dixi-tower/lib/python*/site-packages/dixi_tower)"
"$T/bin/dixi-tower" --version
DIXI_TOWER_BIN="$T/bin/dixi-tower" DIXI_TOWER_SRC="$PKG" "$AQUI/tests/smoke.sh"
