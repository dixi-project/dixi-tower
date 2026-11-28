#!/usr/bin/env bash
# Prueba de humo de Dixi Tower.
#
# Simula una instalación nueva en una carpeta temporal, con motores falsos (no
# abre ninguna sesión de modelo) y una sesión tmux propia, sin tocar la carpeta
# de datos ni los agentes reales de quien la ejecuta.
#
#   tests/smoke.sh
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Con DIXI_TOWER_BIN y DIXI_TOWER_SRC se prueba una instalación en vez del repositorio.
DT="${DIXI_TOWER_BIN:-$AQUI/dixi-tower}"
SRC="${DIXI_TOWER_SRC:-$AQUI/src/dixi_tower}"
T="$(mktemp -d "${TMPDIR:-/tmp}/dixi-tower-smoke.XXXXXX")"
export DIXI_TOWER_HOME="$T/datos" DIXI_TOWER_PROJECTS="$T/proyectos" DIXI_TOWER_SESSION="dixi-tower-smoke-$$"
unset DIXI_AGENTES_HOME DIXI_PROYECTOS_DIR DIXI_AGENTES_REGISTRO DIXI_TOWER_LANG LC_ALL LC_MESSAGES   # el idioma lo decide LANG (los runners de macOS fijan LC_ALL)
export PATH="$T/bin:$PATH" LANG=en_US.UTF-8
fallos=0
ok()   { echo "  ok   $1"; }
mal()  { echo "  FAIL $1"; fallos=$((fallos + 1)); }
debe() { if eval "$2" >/dev/null 2>&1; then ok "$1"; else mal "$1"; fi; }
limpiar() { tmux kill-session -t "=$DIXI_TOWER_SESSION" 2>/dev/null; rm -rf "$T"; }
trap limpiar EXIT

mkdir -p "$T/bin" "$T/proyectos/con_tareas/tasks" "$T/proyectos/simple"
for motor in claude codex miagente; do printf '#!/usr/bin/env bash\necho "$0 $*" > "%s/ultimo-%s.txt"\nsleep 300\n' "$T" "$motor" > "$T/bin/$motor"; chmod +x "$T/bin/$motor"; done
repo() { (cd "$1" && git init -q -b main . && git add -A && git -c user.name=t -c user.email=t@t commit -q -m init); }
printf -- '- [r] **Revisada** <!-- st:aaaaaa000001 -->\n- [r] **Otra** <!-- st:aaaaaa000002 -->\n- [ ] **Pendiente** _(P1)_ <!-- st:aaaaaa000003 -->\n' > "$T/proyectos/con_tareas/tasks/TASKS.md"
echo hola > "$T/proyectos/simple/README.md"
repo "$T/proyectos/con_tareas"; repo "$T/proyectos/simple"
echo "Fix the README" > "$T/encargo.txt"
E="$DIXI_TOWER_HOME/estado"; R="$DIXI_TOWER_HOME/run"
vivas() { tmux list-windows -t "=$DIXI_TOWER_SESSION" -F '#W' 2>/dev/null; }

echo "Instalación nueva"
debe "la ayuda sale en inglés" "'$DT' | grep -q 'local control tower'"
debe "doctor encuentra lo imprescindible" "'$DT' doctor"
debe "la carpeta de datos es la indicada, no ~/.agentes" "'$DT' status | grep -q 'No agents' && [ -d '$DIXI_TOWER_HOME' ]"
debe "los mensajes salen en el idioma del sistema" "('$DT' stop nope 2>&1; true) | grep -q 'Unknown agent' && (LANG=es_MX.UTF-8 '$DT' stop nope 2>&1; true) | grep -q 'No conozco al agente'"
debe "DIXI_TOWER_LANG manda sobre el idioma del sistema" "(DIXI_TOWER_LANG=es '$DT' stop nope 2>&1; true) | grep -q 'No conozco'"
debe "doctor también respeta DIXI_TOWER_LANG" "(DIXI_TOWER_LANG=es '$DT' doctor 2>&1; true) | grep -q 'Requisitos'"

echo "Lanzar"
debe "sin tasks/TASKS.md, con instrucción libre (comandos en inglés)" "'$DT' launch simple free --instruction '$T/encargo.txt'"
debe "la rama no usa el prefijo de tareas" "git -C '$T/proyectos/simple' branch --list 'agente/*' | grep -q agente/"
debe "con tarea del tablero, y de fábrica no hay tope" "'$DT' launch con_tareas aaaaaa000003"
debe "segundo agente en el mismo proyecto, con Codex" "'$DT' launch simple free --instruction '$T/encargo.txt' --engine codex --autonomy supervised"
debe "el segundo se llama simple@2" "vivas | grep -qx 'simple@2'"
debe "Codex supervisado arranca en solo lectura" "grep -q -- '--sandbox read-only' '$R/simple@2.sh'"
debe "la misma tarea no se lanza dos veces" "! '$DT' launch con_tareas aaaaaa000003"
debe "un motor desconocido se rechaza" "! '$DT' launch simple free --instruction '$T/encargo.txt' --engine nope"
debe "con el sistema en inglés, el encargo y las reglas van en inglés" "grep -q 'Its entry in tasks/TASKS.md' '$R/con_tareas.prompt.txt' && grep -q 'You are already on branch' '$R/simple.prompt.txt' && grep -q 'You are a Dixi Tower' '$R/simple.reglas.md'"
MERGE='{"tool_input":{"command":"gh pr merge 3"}}'
debe "la barrera bloquea y explica en inglés" "(echo '$MERGE' | DIXI_AGENTE=1 DIXI_TOWER_LANG=en python3 -B '$SRC/hooks/guardia.py' 2>&1; true) | grep -q 'local agent guard'"
debe "la barrera bloquea y explica en español" "(echo '$MERGE' | DIXI_AGENTE=1 DIXI_TOWER_LANG=es python3 -B '$SRC/hooks/guardia.py' 2>&1; true) | grep -q 'barrera de agentes'"
debe "la barrera sale con código 2 al bloquear" "echo '$MERGE' | DIXI_AGENTE=1 python3 -B '$SRC/hooks/guardia.py' 2>/dev/null; [ \$? -eq 2 ]"
debe "el guion del agente le pasa su idioma a los hooks" "grep -q 'DIXI_TOWER_LANG=en' '$R/simple.sh'"
debe "con DIXI_TOWER_LANG=es, el encargo va en español" "DIXI_TOWER_LANG=es '$DT' launch simple free --instruction '$T/encargo.txt' && grep -q 'Ya estás en la rama' '$R/simple@3.prompt.txt' && grep -q 'Eres un agente local' '$R/simple@3.reglas.md'"
debe "las reglas del agente no traen nada de una instalación ajena" "! grep -qi 'sys_task\|TASKS.md' '$R/simple.reglas.md'"

echo "Motor propio"
mkdir -p "$DIXI_TOWER_HOME"
python3 - "$DIXI_TOWER_HOME/config.json" <<'PY'
import json, sys
json.dump({"motores": {"miagente": {"comando": "miagente --task {instruccion}", "reanudar": "miagente --continue"}}}, open(sys.argv[1], "w"))
PY
debe "se puede lanzar un motor definido por el usuario" "'$DT' launch simple free --instruction '$T/encargo.txt' --engine miagente"
sleep 1
debe "recibe el encargo en su propio comando" "grep -q -- '--task Fix the README' '$T/ultimo-miagente.txt'"
debe "guardar la configuración no borra los motores propios" "python3 -c \"
import sys; sys.path.insert(0, '$SRC'); import config
config.guardar_global({'tope_revision': 1}); assert 'miagente' in config.motores_disponibles()\""

echo "Tope de tareas en revisión"
debe "con tope 1 y dos en revisión se niega" "'$DT' stop con_tareas && '$DT' delete con_tareas && ! '$DT' launch con_tareas aaaaaa000003"
debe "forzándolo, pasa" "'$DT' launch con_tareas aaaaaa000003 --force"

echo "Ciclo de vida"
WT="$(python3 -c "import json; print(json.load(open('$E/simple.json'))['worktree'])")"   # hay varios agentes en «simple»
debe "decir le escribe al agente" "'$DT' say simple 'mensaje-de-prueba' && sleep 0.5 && tmux capture-pane -p -t '=$DIXI_TOWER_SESSION:simple' | grep -q mensaje-de-prueba"
debe "detener cierra la ventana" "'$DT' stop simple && ! vivas | grep -qx simple"
debe "eliminar se niega si hay archivos sin commit" "echo x > '$WT/nuevo.txt'; ! '$DT' delete simple"
debe "reanudar lo vuelve a encender" "'$DT' resume simple && vivas | grep -qx simple"
debe "reanudar retoma la conversación" "grep -q -- '--continue\|--resume' '$R/simple.reanudar.sh'"
debe "eliminar un agente encendido se niega" "! '$DT' delete simple"
debe "ya limpio y detenido, se elimina y conserva la rama" "rm '$WT/nuevo.txt'; '$DT' stop simple && '$DT' delete simple && [ ! -f '$E/simple.json' ] && git -C '$T/proyectos/simple' branch --list 'agente/*' | grep -q agente/"

echo "Panel"
debe "renderiza la página y la lista en los dos idiomas" "cd '$SRC' && python3 -B -c \"
import panel
for i in ('es', 'en'):
    assert 'Dixi Tower' in panel.pagina(i) and 'con_tareas' in panel.lista(i)
assert panel.sesion() == '$DIXI_TOWER_SESSION'\""
debe "rechaza acciones inválidas" "cd '$SRC' && python3 -B -c \"
import panel
assert panel.accion({'lanzar': True, 'proyecto': '../x'})[0] == 400
assert panel.accion({'eliminar': True, 'proyecto': 'nope'})[0] == 404\""
debe "ofrece el motor propio y los comandos del motor" "cd '$SRC' && python3 -B -c \"
import panel
assert 'miagente' in panel.pagina('en')
assert any(c['c'] == '/model' for c in panel.comandos('en', 'con_tareas'))\""

debe "lee el estado de Codex en su pantalla" "cd '$SRC' && python3 -B -c \"
import panel
pie = 'GPT · Ready · 5h 90% left · weekly 70% left'
assert panel.estado_codex('con_tareas', 'x\\n' + pie)[0] == 'en_pausa'
assert panel.estado_codex('con_tareas', 'x\\n• Working (3s • esc to interrupt)')[0] == 'trabajando'
assert panel.estado_codex('con_tareas', 'Would you like to run the following command?\\nPress enter to confirm or esc to cancel')[0] == 'te_necesita'
u = panel.config.uso('con_tareas'); assert u['semana'] == 30 and u['sesion'] == 10\""
debe "un título largo se corta en un espacio, con puntos suspensivos" "cd '$SRC' && echo 'Add a search box above the product list that filters products by name as you type. Plain JavaScript' | python3 -B tareas.py slug | cut -f1 | grep -q 'Plain…\$'"
debe "ve que Claude espera al arrancar (confiar en la carpeta)" "cd '$SRC' && python3 -B -c \"
import panel
assert panel.espera_al_arrancar('x', 'Quick safety check\\n> No, exit\\n  Yes, I trust this folder\\nEnter to confirm')
assert not panel.espera_al_arrancar('x', 'Welcome to Claude Code')\""
debe "guarda un adjunto sin salirse de su carpeta" "cd '$SRC' && python3 -B -c \"
import os, panel
r = panel.guardar_adjunto('con_tareas', '../../fuera/mi foto.png', b'x')
assert os.path.dirname(r) == os.path.join(panel.HOME_AG, 'adjuntos', 'con_tareas') and os.path.isfile(r) and ' ' not in os.path.basename(r)\""
debe "el explorador no sale de la carpeta personal ni muestra ocultos" "cd '$SRC' && python3 -B -c \"
import json, os, panel
assert panel.explorar('/etc')[0] == 403
d = json.loads(panel.explorar(os.path.expanduser('~'))[1])
assert d['padre'] is None and not any(n.startswith('.') for n in d['carpetas'] + d['archivos'])\""
P=$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1])")
debe "el panel en tmux usa la carpeta de datos indicada y sirve su ícono" "'$DT' panel $P >/dev/null && for i in \$(seq 1 20); do curl -s -m 1 http://127.0.0.1:$P/es/lista | grep -q con_tareas && break; sleep 0.5; done && curl -s http://127.0.0.1:$P/es/lista | grep -q con_tareas && curl -s -D - -o /dev/null http://127.0.0.1:$P/favicon.svg | grep -qi 'image/svg+xml'"
debe "eliminar un agente borra también sus adjuntos" "'$DT' stop con_tareas && '$DT' delete con_tareas && [ ! -d '$DIXI_TOWER_HOME/adjuntos/con_tareas' ]"

echo "Windows (WSL)"
printf 'Linux version 5.15.167.4-microsoft-standard-WSL2\n' > "$T/version-wsl"
printf 'Linux version 6.1.0-28-amd64 (debian)\n' > "$T/version-linux"
debe "reconoce WSL y no lo confunde con Linux" "cd '$SRC' && env -u WSL_DISTRO_NAME python3 -B -c \"
import sistema
assert sistema.es_wsl('$T/version-wsl') and not sistema.es_wsl('$T/version-linux')\""
debe "distingue el disco de Windows (/mnt/c) de una carpeta de Linux" "cd '$SRC' && python3 -B -c \"
import sistema
assert sistema.en_disco_de_windows('/mnt/c/Users/ana/projects')
assert not sistema.en_disco_de_windows('/home/ana/projects') and not sistema.en_disco_de_windows('/mnt/datos/x')\""
debe "el aviso de Windows pasa los textos por WSLENV, no en la orden" "cd '$SRC/hooks' && python3 -B -c \"
import base64, avisos
orden, env = avisos.orden_windows('powershell.exe', 'Agent \\\"x\\\"', 'needs <you> & me', 'http://localhost:4310/#x')
guion = base64.b64decode(orden[-1]).decode('utf-16-le')
assert 'ToastGeneric' in guion and 'needs' not in ' '.join(orden)
assert env['DT_TEXTO'] == 'needs <you> & me' and 'DT_URL/u' in env['WSLENV']\""

echo
if [ "$fallos" -eq 0 ]; then echo "Todo pasó."; else echo "$fallos prueba(s) fallaron."; fi
exit "$fallos"
