#!/usr/bin/env bash
# Prueba del servicio siempre encendido en Linux (systemd de usuario).
#
# Instala el servicio de verdad (dixi-tower.service), así que solo corre en la
# integración continua o en una máquina desechable: hace falta CI=true o
# DIXI_TOWER_PROBAR_SERVICIO=1. Necesita systemd de usuario (systemctl --user).
#
#   CI=true tests/servicio.sh
set -uo pipefail
if [ "${CI:-}" != true ] && [ "${DIXI_TOWER_PROBAR_SERVICIO:-}" != 1 ]; then
  echo "Esta prueba instala el servicio de verdad: solo corre con CI=true o DIXI_TOWER_PROBAR_SERVICIO=1." >&2; exit 2
fi
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
DT="${DIXI_TOWER_BIN:-$AQUI/dixi-tower}"
T="$(mktemp -d "${TMPDIR:-/tmp}/dixi-tower-servicio.XXXXXX")"
P=$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1])")
export DIXI_TOWER_HOME="$T/datos" DIXI_TOWER_PROJECTS="$T/proyectos" DIXI_TOWER_PORT="$P" LANG=en_US.UTF-8
unset DIXI_AGENTES_HOME DIXI_PROYECTOS_DIR DIXI_TOWER_SESSION LC_ALL LC_MESSAGES
export PATH="$T/bin:$PATH"
fallos=0
ok()   { echo "  ok   $1"; }
mal()  { echo "  FAIL $1"; fallos=$((fallos + 1)); }
# Sin grep -q tras una tubería: con pipefail, cerrarla antes de tiempo cuenta como fallo.
debe() { echo "  ...  $1"; if eval "$2" >/dev/null 2>&1; then ok "$1"; else mal "$1"; fi; }
responde() { curl -s -o /dev/null -m 2 "http://127.0.0.1:$P/en/lista"; }
espera() { local i; for i in $(seq 1 40); do eval "$1" >/dev/null 2>&1 && return 0; sleep 0.5; done; return 1; }
limpiar() { "$DT" service uninstall >/dev/null 2>&1; tmux kill-server 2>/dev/null; rm -rf "$T"; }
trap limpiar EXIT

mkdir -p "$T/bin" "$T/proyectos/demo"
printf '#!/usr/bin/env bash\nsleep 300\n' > "$T/bin/claude"; chmod +x "$T/bin/claude"
(cd "$T/proyectos/demo" && echo hola > README.md && git init -q -b main . && git add -A && git -c user.name=t -c user.email=t@t commit -q -m init)
echo "Fix the README" > "$T/encargo.txt"
U="$HOME/.config/systemd/user/dixi-tower.service"

echo "Servicio en Linux (systemd de usuario)"
debe "hay systemd de usuario" "systemctl --user show-environment"
debe "se instala y el panel responde" "'$DT' service install && responde"
debe "la unidad usa KillMode=process y Restart=always" "grep -qx 'KillMode=process' '$U' && grep -qx 'Restart=always' '$U'"
debe "queda habilitado para arrancar solo" "systemctl --user is-enabled dixi-tower.service"
debe "estado lo ve instalado y respondiendo" "'$DT' service status | grep 'installed' && '$DT' service status | grep 'responding'"
debe "doctor ve el servicio" "'$DT' doctor | grep '✓ Service'"
debe "el panel del servicio usa las carpetas indicadas" "[ -f '$DIXI_TOWER_HOME/panel.token' ] && curl -s http://127.0.0.1:$P/en/carpetas | grep -q demo"
debe "se lanza un agente" "'$DT' launch demo free --instruction '$T/encargo.txt' && tmux list-windows -t '=dixi-tower' -F '#W' | grep -qx demo"
debe "reiniciar el servicio no mata a los agentes" "'$DT' service restart && responde && tmux list-windows -t '=dixi-tower' -F '#W' | grep -qx demo"
PID=$(systemctl --user show -p MainPID --value dixi-tower.service)
debe "si el panel se cae, systemd lo levanta" "[ \"\${PID:-0}\" -gt 0 ] && kill $PID && sleep 1 && espera responde && [ \"\$(systemctl --user show -p MainPID --value dixi-tower.service)\" != '$PID' ]"
debe "quitar lo detiene y borra la unidad" "'$DT' service uninstall && [ ! -f '$U' ] && ! responde"
debe "sin systemd explica qué hacer" "(env -i HOME='$HOME' PATH=/usr/bin:/bin LANG=es_MX.UTF-8 XDG_RUNTIME_DIR=/nonexistent DBUS_SESSION_BUS_ADDRESS=unix:path=/nonexistent '$DT' service install 2>&1; true) | grep -q 'systemd'"

echo
if [ "$fallos" -eq 0 ]; then echo "Todo pasó."; else echo "$fallos prueba(s) fallaron."; fi
exit "$fallos"
