#!/usr/bin/env bash
# Prueba de Dixi Tower en Linux (Debian 12) dentro de Docker.
#
# El repositorio entra en solo lectura y el contenedor se borra al terminar. Corre
# la prueba de humo desde el repositorio y contra una instalación con pip, y prueba
# el panel por HTTP, lanzar un agente con un motor falso y los avisos.
#
#   tests/linux.sh [imagen]        (por defecto debian:bookworm-slim)
set -euo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
exec docker run --rm -v "$AQUI:/src:ro" "${1:-debian:bookworm-slim}" bash /src/tests/linux/dentro.sh
