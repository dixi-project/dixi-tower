#!/usr/bin/env bash
# Se ejecuta DENTRO del contenedor que abre tests/linux.sh. El repositorio llega en
# solo lectura en /src; todo lo que se escribe queda en el contenedor, que se borra al salir.
set -uo pipefail
export DEBIAN_FRONTEND=noninteractive LANG=C.UTF-8
echo "══ Preparando Debian"
apt-get update -qq >/dev/null && apt-get install -y -qq --no-install-recommends tmux git python3 python3-venv curl ca-certificates procps >/dev/null 2>&1 \
  && echo "   $(. /etc/os-release; echo "$PRETTY_NAME") · $(python3 --version) · tmux $(tmux -V | cut -d' ' -f2) · $(git --version)"
git config --global user.name prueba; git config --global user.email prueba@example.com; git config --global init.defaultBranch main
cp -R /src /tmp/dixi-tower && rm -rf /tmp/dixi-tower/.git /tmp/dixi-tower/build /tmp/dixi-tower/src/*.egg-info
find /tmp/dixi-tower -name __pycache__ -prune -exec rm -rf {} +
echo; echo "══ 1. Prueba de humo desde el repositorio"
/tmp/dixi-tower/tests/smoke.sh 2>&1 | grep -v "^  ok"
echo; echo "══ 2. Instalación con pip en un entorno virtual"
python3 -m venv /tmp/v && /tmp/v/bin/pip install -q /tmp/dixi-tower 2>&1 | tail -2
PKG="$(ls -d /tmp/v/lib/python*/site-packages/dixi_tower)"
/tmp/v/bin/dixi-tower --version
DIXI_TOWER_BIN=/tmp/v/bin/dixi-tower DIXI_TOWER_SRC="$PKG" /tmp/dixi-tower/tests/smoke.sh 2>&1 | grep -v "^  ok"
echo; echo "══ 3. Lo propio de Linux"
D=/tmp/v/bin/dixi-tower
echo "-- doctor:"; $D doctor | sed 's/^/   /'
echo "-- servicio (solo macOS):"; $D service install 2>&1 | sed 's/^/   /'
echo "-- panel real por HTTP:"
mkdir -p /tmp/proyectos/demo && (cd /tmp/proyectos/demo && echo hola > README.md && git init -q . && git add . && git commit -q -m init)
export DIXI_TOWER_PROJECTS=/tmp/proyectos
$D panel 2>&1 | sed 's/^/   /'; sleep 2
for r in / /es/ /en/ /en/lista /en/carpetas; do printf '   %-12s %s\n' "$r" "$(curl -s -o /dev/null -w '%{http_code}' -H 'Accept-Language: en' "http://127.0.0.1:4310$r")"; done
curl -s http://127.0.0.1:4310/en/carpetas | grep -q demo && echo "   el panel ve el proyecto «demo»"
echo "-- lanzar un agente con un motor falso y verlo en el panel:"
mkdir -p /tmp/bin && printf '#!/usr/bin/env bash\nsleep 300\n' > /tmp/bin/claude && chmod +x /tmp/bin/claude
echo "Fix the README" > /tmp/i.txt
PATH="/tmp/bin:$PATH" $D launch demo free --instruction /tmp/i.txt 2>&1 | grep -v "^Preparing\|^HEAD" | sed 's/^/   /'
sleep 2; curl -s http://127.0.0.1:4310/en/lista | grep -o 'class="n">[^<]*' | sed 's/class="n">/   en la lista: /'
echo "-- aviso al terminar un turno (en Linux no hay terminal-notifier ni osascript):"
printf '{"hook_event_name":"Stop","last_assistant_message":"listo"}' | DIXI_AGENTE_PROYECTO=demo DIXI_AGENTE_ID=demo DIXI_AGENTES_HOME="$HOME/.dixi-tower" python3 "$PKG/hooks/estado-hook.py"; echo "   salida del hook: $? · estado: $(python3 -c "import json,os; print(json.load(open(os.path.expanduser('~/.dixi-tower/estado/demo.json')))['estado'])")"
