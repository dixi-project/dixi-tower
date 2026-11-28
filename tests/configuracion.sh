#!/usr/bin/env bash
# Pruebas de la configuración: carpeta de proyectos, tablero editable y lanzar
# por ruta.
#
# Como tests/smoke.sh: todo ocurre en una carpeta temporal, con motores falsos
# (no abre ninguna sesión de modelo), una sesión tmux propia y un panel propio en
# un puerto libre. No toca la carpeta de datos ni los agentes de quien la ejecuta.
#
#   tests/configuracion.sh
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
# Con DIXI_TOWER_BIN y DIXI_TOWER_SRC se prueba una instalación en vez del repositorio.
DT="${DIXI_TOWER_BIN:-$AQUI/dixi-tower}"
SRC="${DIXI_TOWER_SRC:-$AQUI/src/dixi_tower}"
T="$(mktemp -d "${TMPDIR:-/tmp}/dixi-tower-config.XXXXXX")"
T="$(cd "$T" && pwd -P)"     # ruta física: así las comparaciones no dependen de /var → /private/var
export T SRC AQUI
export DIXI_TOWER_HOME="$T/datos" DIXI_TOWER_PROJECTS="$T/proyectos" DIXI_TOWER_SESSION="dixi-tower-config-$$"
unset DIXI_AGENTES_HOME DIXI_PROYECTOS_DIR DIXI_AGENTES_REGISTRO DIXI_TOWER_LANG LC_ALL LC_MESSAGES
export PATH="$T/bin:$PATH" LANG=en_US.UTF-8
fallos=0 aciertos=0 PANEL_PID=""
ok()   { echo "  ok   $1"; aciertos=$((aciertos + 1)); }
mal()  { echo "  FAIL $1"; fallos=$((fallos + 1)); }
# Como en smoke.sh, pero al fallar enseña las últimas líneas de salida.
debe() {
  local salida
  if salida="$(eval "$2" 2>&1)"; then ok "$1"
  else mal "$1"; [ -n "$salida" ] && printf '%s\n' "$salida" | tail -n 4 | cut -c1-220 | sed 's/^/         | /'; fi
  return 0
}
limpiar() {
  [ -n "$PANEL_PID" ] && kill "$PANEL_PID" 2>/dev/null
  tmux kill-session -t "=$DIXI_TOWER_SESSION" 2>/dev/null
  rm -rf "$T"
}
trap limpiar EXIT

E="$DIXI_TOWER_HOME/estado"; R="$DIXI_TOWER_HOME/run"
export E R
HOSTIL="$T/fuera/mi repo's \"q\" \$(touch PWNED) \`touch PWNED\`"
export HOSTIL

mkdir -p "$T/bin" "$T/casa/projects" "$T/proyectos/con_tareas/tasks" "$T/proyectos/simple" \
         "$T/otros/otro" "$T/otros/simple" "$T/fuera/web/sub" "$T/fuera/no-git" "$T/fuera/cli-repo" \
         "$T/fuera/tareas-repo/tasks" "$T/fuera/con
salto" "$HOSTIL" "$DIXI_TOWER_HOME/dentro"
for motor in claude codex; do printf '#!/usr/bin/env bash\n[ "${1:-}" = --version ] && { echo "%s fake"; exit 0; }\necho "$0 $*" > "%s/ultimo-%s.txt"\nsleep 300\n' "$motor" "$T" "$motor" > "$T/bin/$motor"; chmod +x "$T/bin/$motor"; done
repo() { (cd "$1" && git init -q -b main . && git add -A && git -c user.name=t -c user.email=t@t commit -q -m init); }
printf -- '- [r] **Revisada** <!-- st:aaaaaa000001 -->\n- [ ] **Pendiente** _(P1)_ <!-- st:aaaaaa000003 -->\n' > "$T/proyectos/con_tareas/tasks/TASKS.md"
printf -- '- [ ] **Tarea externa** _(P1)_ <!-- st:bbbbbb000001 -->\n' > "$T/fuera/tareas-repo/tasks/TASKS.md"
echo hola | tee "$T/proyectos/simple/README.md" "$T/otros/otro/README.md" "$T/otros/simple/README.md" \
                "$T/fuera/web/README.md" "$T/fuera/web/sub/x.txt" "$T/fuera/no-git/README.md" "$T/fuera/cli-repo/README.md" \
                "$T/fuera/con
salto/README.md" "$HOSTIL/README.md" "$DIXI_TOWER_HOME/dentro/README.md" >/dev/null
for r in "$T/proyectos/con_tareas" "$T/proyectos/simple" "$T/otros/otro" "$T/otros/simple" "$T/fuera/web" "$T/fuera/cli-repo" \
         "$T/fuera/tareas-repo" "$T/fuera/con
salto" "$HOSTIL" "$DIXI_TOWER_HOME/dentro"; do repo "$r"; done
echo "Fix the README" > "$T/encargo.txt"

cfg()    { mkdir -p "$DIXI_TOWER_HOME"; printf '%s' "$1" > "$DIXI_TOWER_HOME/config.json"; }
sincfg() { rm -f "$DIXI_TOWER_HOME/config.json"; }
# Ejecuta Python (script por stdin) dentro de src/. PYPREFIX permite anteponer «env …».
py()     { (cd "$SRC" && ${PYPREFIX:-} python3 -B -); }
vivas()  { tmux list-windows -t "=$DIXI_TOWER_SESSION" -F '#W' 2>/dev/null; }
LANZA="'lanzar': True, 'tarea': 'libre', 'instruccion': 'Fix the README', '_idioma': 'en'"
export LANZA

# Cliente HTTP con tiempo límite: web METODO PUERTO RUTA [cabeceras-json] [cuerpo]
mkdir -p "$T/aux"
cat > "$T/aux/cliente_web.py" <<'PY'
import http.client, json, sys
metodo, puerto, ruta = sys.argv[1:4]
cab = json.loads(sys.argv[4]) if len(sys.argv) > 4 else {}
cuerpo = sys.argv[5].encode() if len(sys.argv) > 5 else None
c = http.client.HTTPConnection("127.0.0.1", int(puerto), timeout=8)
c.request(metodo, ruta, cuerpo, cab)
r = c.getresponse()
print(r.status)
print(r.read().decode())
PY
web() { python3 "$T/aux/cliente_web.py" "$@"; }
token() { cat "$DIXI_TOWER_HOME/panel.token" 2>/dev/null; }
# post_cfg '<json de config>' [idioma] [agente-json]: guarda la configuración con token y Origin buenos
post_cfg() {
  local tk cab cuerpo
  tk="$(token)"
  cab="{\"X-Panel-Token\":\"$tk\",\"Origin\":\"http://127.0.0.1:$P\",\"X-Idioma\":\"${2:-en}\",\"Content-Type\":\"application/json\"}"
  cuerpo="{\"guardar_config\":true,\"agente\":${3:-null},\"config\":$1}"
  web POST "$P" /api/accion "$cab" "$cuerpo"
}
# codigo '<cabeceras json>' '<cuerpo>': código HTTP de un POST a /api/accion
codigo() { web POST "$P" /api/accion "$1" "$2" | head -1; }

echo "Configuración"
t_sin_clave() {
  sincfg
  py <<'PY' && [ "$(python3 -B "$SRC/config.py" proyectos)" = "$T/proyectos" ]
import config, os
assert config.carpeta_proyectos() == os.environ["T"] + "/proyectos", config.carpeta_proyectos()
assert config.origen_carpeta() == "DIXI_TOWER_PROJECTS", config.origen_carpeta()
PY
}
debe "sin clave, la carpeta es la de DIXI_TOWER_PROJECTS y se dice su origen" t_sin_clave
t_predeterminada() {
  sincfg
  [ "$(env -u DIXI_TOWER_PROJECTS -u DIXI_PROYECTOS_DIR HOME="$T/casa" python3 -B "$SRC/config.py" proyectos)" = "$T/casa/projects" ] &&
  PYPREFIX="env -u DIXI_TOWER_PROJECTS -u DIXI_PROYECTOS_DIR HOME=$T/casa" py <<'PY'
import config, os
assert config.carpeta_proyectos() == os.environ["T"] + "/casa/projects", config.carpeta_proyectos()
assert config.origen_carpeta() == "predeterminada", config.origen_carpeta()
PY
}
debe "sin clave ni variables, ~/projects" t_predeterminada
t_antigua() {
  sincfg
  PYPREFIX="env -u DIXI_TOWER_PROJECTS DIXI_PROYECTOS_DIR=$T/otros" py <<'PY'
import config, os
assert config.carpeta_proyectos() == os.environ["T"] + "/otros", config.carpeta_proyectos()
assert config.origen_carpeta() == "DIXI_PROYECTOS_DIR", config.origen_carpeta()
PY
}
debe "DIXI_PROYECTOS_DIR se sigue aceptando" t_antigua
t_manda_config() {
  cfg "{\"carpeta_proyectos\": \"$T/otros\"}"
  py <<'PY'
import config, os
assert config.carpeta_proyectos() == os.environ["T"] + "/otros", config.carpeta_proyectos()
assert config.origen_carpeta() == "config", config.origen_carpeta()
PY
}
debe "la carpeta configurada manda sobre la variable" t_manda_config
t_vacia() {
  cfg '{"carpeta_proyectos": ""}'
  py <<'PY' && [ "$(python3 -B "$SRC/config.py" proyectos; echo x)" = $'\nx' ]
import config
assert config.carpeta_proyectos() == "", repr(config.carpeta_proyectos())
assert config.origen_carpeta() == "config", config.origen_carpeta()
PY
}
debe "carpeta vacía = sin carpeta por defecto (config.py proyectos imprime una línea vacía)" t_vacia
t_null() {
  cfg "{\"carpeta_proyectos\": \"$T/otros\", \"zeta\": 1}"
  py <<'PY'
import config, json, os
config.guardar_global({"carpeta_proyectos": None})
d = json.load(open(config.ruta_global()))
assert "carpeta_proyectos" not in d, d
assert d.get("zeta") == 1, d
assert config.carpeta_proyectos() == os.environ["T"] + "/proyectos" and config.origen_carpeta() == "DIXI_TOWER_PROJECTS"
PY
}
debe "null quita la clave y se vuelve a la variable" t_null
t_rechaza_carpeta() {
  cfg "{\"carpeta_proyectos\": \"$T/otros\", \"tope_revision\": 2}"
  py <<'PY'
import config, os
T = os.environ["T"]
malas = ["relativa/x", "~nadie-existe/x", T + "/no-existe", T + "/proyectos/simple/README.md",
         T + "/otros\n", T + "/otros\x01", "x" * 1100, T + "/otros" + "/a" * 600]
antes = open(config.ruta_global(), "rb").read()
for m in malas:
    try:
        config.guardar_global({"carpeta_proyectos": m, "tope_revision": 9})
    except ValueError as e:
        assert e.args and e.args[0] == "p_carpeta_invalida", (m[:30], e.args)
    else:
        raise AssertionError("aceptó " + repr(m[:40]))
    assert open(config.ruta_global(), "rb").read() == antes, "tocó el archivo con " + repr(m[:40])
PY
}
debe "rechaza carpeta relativa, inexistente, archivo, con control o demasiado larga, y no toca el archivo" t_rechaza_carpeta
t_normaliza_carpeta() {
  cfg '{}'
  PYPREFIX="env HOME=$T/casa" py <<'PY'
import config, json, os
T = os.environ["T"]
config.guardar_global({"carpeta_proyectos": "~/projects"})
assert json.load(open(config.ruta_global()))["carpeta_proyectos"] == T + "/casa/projects"
config.guardar_global({"carpeta_proyectos": T + "/otros/"})
assert json.load(open(config.ruta_global()))["carpeta_proyectos"] == T + "/otros"
config.guardar_global({"carpeta_proyectos": "   "})
assert json.load(open(config.ruta_global()))["carpeta_proyectos"] == ""
PY
}
debe "guarda la carpeta con ~ expandido, sin barra final; solo espacios = vacía" t_normaliza_carpeta
t_conserva() {
  cfg "{\"motores\": {\"miagente\": {\"comando\": \"miagente --task {instruccion}\"}}, \"tablero\": \"https://tablero.example/b\", \"carpeta_proyectos\": \"$T/otros\", \"zeta\": {\"a\": 1}}"
  py <<'PY'
import config, json, os
config.guardar_global({"tope_revision": 2, "autonomia": "autonoma"})
d = json.load(open(config.ruta_global()))
assert d["tope_revision"] == 2 and d["autonomia"] == "autonoma", d
assert "miagente" in d["motores"], d
assert d["tablero"] == "https://tablero.example/b", d
assert d["carpeta_proyectos"] == os.environ["T"] + "/otros", d
assert d["zeta"] == {"a": 1}, d
PY
}
debe "guardar conserva motores, tablero, carpeta y claves desconocidas" t_conserva
t_no_crea() {
  sincfg
  py <<'PY'
import config, json
config.guardar_global({"tope_revision": 1})
d = json.load(open(config.ruta_global()))
assert d["tope_revision"] == 1 and "carpeta_proyectos" not in d and "tablero" not in d, d
PY
}
debe "guardar sin carpeta_proyectos no crea la clave" t_no_crea
t_tablero() {
  cfg '{"zeta": 1}'
  py <<'PY'
import config, json
buenas = ["https://tablero.example/b", "http://localhost:3000/", "HTTPS://Tablero.example"]
for b in buenas:
    config.guardar_global({"tablero": b})
    assert config.tablero() == b, (b, config.tablero())
malas = ["javascript:alert(1)", "ftp://x.example/a", "https://a b.example", "https://", "http:///x", "tablero.example",
         "https://x.example/\n", "https://" + "a" * 2050 + ".example", 5]
config.guardar_global({"tablero": "https://tablero.example/b"})
antes = open(config.ruta_global(), "rb").read()
for m in malas:
    try:
        config.guardar_global({"tablero": m, "tope_revision": 9})
    except ValueError as e:
        assert e.args and e.args[0] == "p_tablero_invalido", (str(m)[:30], e.args)
    else:
        raise AssertionError("aceptó " + repr(m)[:40])
    assert open(config.ruta_global(), "rb").read() == antes, "tocó el archivo con " + repr(m)[:40]
for vacio in ("", None):
    config.guardar_global({"tablero": "https://tablero.example/b"})
    config.guardar_global({"tablero": vacio})
    assert "tablero" not in json.load(open(config.ruta_global())) and config.tablero() is None, vacio
    assert json.load(open(config.ruta_global())).get("zeta") == 1
PY
}
debe "tablero: acepta http/https; rechaza javascript:, ftp:, espacios y >2048; vacío o null lo borra" t_tablero
t_agente_no_toca() {
  cfg "{\"carpeta_proyectos\": \"$T/otros\", \"tablero\": \"https://tablero.example/b\", \"tope_revision\": 1}"
  mkdir -p "$E"
  echo '{"agente": "falso", "proyecto": "falso", "config": {"motor": "claude"}}' > "$E/falso.json"
  cp "$DIXI_TOWER_HOME/config.json" "$T/config.antes"
  py <<'PY' && cmp -s "$DIXI_TOWER_HOME/config.json" "$T/config.antes"
import config, json, os, panel
c, m = panel.accion({"guardar_config": True, "agente": "falso", "_idioma": "en",
                     "config": {"motor": "codex", "tope_revision": 7, "carpeta_proyectos": "/no/existe", "tablero": "javascript:x"}})
assert c == 200, (c, m)
guardada = json.load(open(os.path.join(os.environ["E"], "falso.json")))["config"]
assert guardada["motor"] == "codex", guardada
assert "carpeta_proyectos" not in guardada and "tablero" not in guardada, guardada
PY
}
debe "guardar ajustes de un agente no toca config.json (byte a byte) ni copia claves globales" t_agente_no_toca

echo "Panel"
t_carpetas_sigue() {
  sincfg
  py <<'PY'
import config, os, panel
T = os.environ["T"]
assert panel.carpetas() == ["con_tareas", "simple"], panel.carpetas()
config.guardar_global({"carpeta_proyectos": T + "/otros"})
assert panel.carpeta() == T + "/otros", panel.carpeta()
assert panel.carpetas() == ["otro", "simple"], panel.carpetas()
assert 'value="otro"' in panel.opciones_proyecto("en") and "con_tareas" not in panel.opciones_proyecto("en")
config.guardar_global({"carpeta_proyectos": None})
assert panel.carpetas() == ["con_tareas", "simple"], panel.carpetas()
PY
}
debe "carpetas() sigue el cambio de configuración sin reiniciar" t_carpetas_sigue

# Panel real en un puerto libre, con la misma carpeta de datos temporal.
P=$(python3 -c "import socket; s=socket.socket(); s.bind(('127.0.0.1', 0)); print(s.getsockname()[1])")
python3 -B "$SRC/panel.py" "$P" >"$T/panel.log" 2>&1 &
PANEL_PID=$!
for _ in $(seq 1 40); do curl -s -m 1 "http://127.0.0.1:$P/es/lista" >/dev/null 2>&1 && break; sleep 0.25; done
curl -s -m 2 "http://127.0.0.1:$P/es/lista" >/dev/null 2>&1 || echo "  (el panel de prueba no arrancó: $(tail -n 2 "$T/panel.log" | tr '\n' ' '))"

t_api_config() {
  sincfg
  web GET "$P" /api/config | tail -n +2 | python3 -c '
import json, os, sys
d = json.load(sys.stdin)
cp = d["carpeta_proyectos"]
assert "motor" in d["config"], d
assert cp["modo"] == "predeterminada" and cp["valor"] == "", cp
assert cp["efectiva"] == os.environ["T"] + "/proyectos" and cp["origen"] == "DIXI_TOWER_PROJECTS" and cp["disponible"] is True, cp
assert d["tablero"] == "", d
' &&
  cfg "{\"carpeta_proyectos\": \"$T/otros\", \"tablero\": \"https://tablero.example/b\"}" &&
  web GET "$P" /api/config | tail -n +2 | python3 -c '
import json, os, sys
d = json.load(sys.stdin)
cp = d["carpeta_proyectos"]
T = os.environ["T"]
assert cp["modo"] == "carpeta" and cp["valor"] == T + "/otros" and cp["efectiva"] == T + "/otros", cp
assert cp["origen"] == "config" and cp["disponible"] is True, cp
assert d["tablero"] == "https://tablero.example/b", d
'
}
debe "/api/config global trae modo, valor, efectiva, origen, disponible y tablero" t_api_config
t_sin_carpeta() {
  cfg '{"carpeta_proyectos": ""}'
  py <<'PY' &&
import panel
assert panel.carpetas() == [], panel.carpetas()
PY
  web GET "$P" /api/config | tail -n +2 | python3 -c '
import json, sys
cp = json.load(sys.stdin)["carpeta_proyectos"]
assert cp["modo"] == "ninguna" and cp["disponible"] is False and not cp["efectiva"], cp
' &&
  web GET "$P" /es/carpetas | tail -n +2 | python3 -c '
import sys
assert "con_tareas" not in sys.stdin.read()
' &&
  cfg "{\"carpeta_proyectos\": \"$T/no-existe\"}" &&
  py <<'PY' &&
import panel
assert panel.carpetas() == [], panel.carpetas()
PY
  web GET "$P" /api/config | tail -n +2 | python3 -c '
import json, sys
cp = json.load(sys.stdin)["carpeta_proyectos"]
assert cp["disponible"] is False, cp
'
}
debe "sin carpeta (vacía o inexistente), carpetas() es vacío y disponible=false" t_sin_carpeta
t_explorar() {
  mkdir -p "$T/casa/trabajo/x"
  cfg "{\"carpeta_proyectos\": \"$T/casa/trabajo\"}"
  PYPREFIX="env HOME=$T/casa" py <<'PY' &&
import json, os, panel
c, m = panel.explorar(None)
d = json.loads(m)
assert c == 200 and d["ruta"] == os.environ["T"] + "/casa/trabajo" and "x" in d["carpetas"], (c, m)
PY
  cfg '{"carpeta_proyectos": ""}' &&
  PYPREFIX="env HOME=$T/casa" py <<'PY'
import json, os, panel
c, m = panel.explorar(None)
assert c == 200 and json.loads(m)["ruta"] == os.environ["T"] + "/casa", (c, m)
PY
}
debe "explorar arranca en la carpeta configurada (o en la personal si no hay)" t_explorar
t_ruta_invalida() {
  sincfg
  py <<'PY'
import json, os, panel
T, H = os.environ["T"], os.environ["DIXI_TOWER_HOME"]
def foto():
    ls = lambda d: sorted(os.listdir(d)) if os.path.isdir(d) else []
    reg = os.path.join(H, "proyectos.json")
    return (ls(H + "/estado"), ls(H + "/worktrees"), open(reg).read() if os.path.exists(reg) else "")
malas = ["otros/otro", T + "/nope", T + "/fuera/no-git", T + "/fuera/web/sub", T + "/fuera/web/../no-git",
         H + "/dentro", T + "/fuera/con\nsalto", T + "/fuera/web\n", "-rf", "--ruta", "", 123, ["x"]]
antes = foto()
for i in ("en", "es"):
    for m in malas:
        c, msg = panel.accion({"lanzar": True, "ruta": m, "tarea": "libre", "instruccion": "Fix the README", "_idioma": i})
        assert c == 400, (i, repr(m), c, msg)
        assert msg and msg != panel.tr("p_proyecto_invalido", i), (repr(m), msg)   # un error propio de la ruta
        assert foto() == antes, "creó algo con " + repr(m)
PY
}
debe "lanzar con ruta inválida da 400 y no crea nada (relativa, inexistente, no-git, subcarpeta, datos, \\n, -x)" t_ruta_invalida
t_lanza_ruta() {
  sincfg
  py <<'PY'
import json, os, subprocess, panel
T, H, E = os.environ["T"], os.environ["DIXI_TOWER_HOME"], os.environ["E"]
c, n = panel.accion({"lanzar": True, "ruta": T + "/fuera/web", **eval("{" + os.environ["LANZA"] + "}")})
assert c == 200 and n == "web", (c, n)
est = json.load(open(E + "/web.json"))
assert est["worktree"].startswith(H + "/worktrees/web/") and os.path.isdir(est["worktree"]), est
reg = json.load(open(H + "/proyectos.json"))
assert os.path.realpath(reg["web"]["repo"]) == os.path.realpath(T + "/fuera/web"), reg
vivas = subprocess.run(["tmux", "list-windows", "-t", "=" + os.environ["DIXI_TOWER_SESSION"], "-F", "#W"], capture_output=True, text=True).stdout.split()
assert "web" in vivas, vivas
PY
}
debe "lanzar con ruta externa crea agente, worktree en la carpeta de datos y entrada de registro" t_lanza_ruta
t_misma_ruta() {
  py <<'PY'
import json, os, panel
T, H, E = os.environ["T"], os.environ["DIXI_TOWER_HOME"], os.environ["E"]
c, n = panel.accion({"lanzar": True, "ruta": T + "/fuera/web", **eval("{" + os.environ["LANZA"] + "}")})
assert c == 200 and n == "web@2", (c, n)
reg = json.load(open(H + "/proyectos.json"))
claves = [k for k, v in reg.items() if os.path.realpath(v["repo"]) == os.path.realpath(T + "/fuera/web")]
assert claves == ["web"], claves
assert json.load(open(E + "/web@2.json"))["worktree"].startswith(H + "/worktrees/web/")
PY
}
debe "la misma ruta otra vez reutiliza la clave: web@2" t_misma_ruta
t_nombre_repetido() {
  sincfg
  "$DT" launch simple free --instruction "$T/encargo.txt" >/dev/null 2>&1 &&
  py <<'PY'
import json, os, panel
T, H = os.environ["T"], os.environ["DIXI_TOWER_HOME"]
c, n = panel.accion({"lanzar": True, "ruta": T + "/otros/simple", **eval("{" + os.environ["LANZA"] + "}")})
assert c == 200 and n == "simple-2", (c, n)
reg = json.load(open(H + "/proyectos.json"))
assert os.path.realpath(reg["simple"]["repo"]) == os.path.realpath(T + "/proyectos/simple"), reg
assert os.path.realpath(reg["simple-2"]["repo"]) == os.path.realpath(T + "/otros/simple"), reg
PY
}
debe "un nombre ya registrado con otro repo recibe la clave simple-2" t_nombre_repetido
t_hostil() {
  sincfg
  py <<'PY' && [ -z "$(find "$T" "$SRC" "$AQUI" -name PWNED 2>/dev/null)" ]
import json, os, re, panel
H = os.environ["DIXI_TOWER_HOME"]
c, n = panel.accion({"lanzar": True, "ruta": os.environ["HOSTIL"], **eval("{" + os.environ["LANZA"] + "}")})
assert c == 200, (c, n)
assert re.fullmatch(r"[\w-]+(@\d+)?", n) and n.startswith("mi-repo"), n
reg = json.load(open(H + "/proyectos.json"))
clave = n.split("@")[0]
assert re.fullmatch(r"[\w-]+", clave) and os.path.realpath(reg[clave]["repo"]) == os.path.realpath(os.environ["HOSTIL"]), reg.get(clave)
PY
}
debe "ruta con espacios, comillas y \$( ) no ejecuta nada y la clave sale saneada" t_hostil
t_cambio_carpeta() {
  cfg "{\"carpeta_proyectos\": \"$T/otros\"}"
  py <<'PY'
import json, os, subprocess, panel
T, E = os.environ["T"], os.environ["E"]
assert "simple" in panel.carpetas()
c, n = panel.accion({"lanzar": True, "proyecto": "simple", **eval("{" + os.environ["LANZA"] + "}")})
assert c == 200, (c, n)
wt = json.load(open(E + "/" + n + ".json"))["worktree"]
comun = subprocess.run(["git", "-C", wt, "rev-parse", "--path-format=absolute", "--git-common-dir"], capture_output=True, text=True).stdout.strip()
assert os.path.realpath(comun) == os.path.realpath(T + "/otros/simple/.git"), (n, wt, comun)
PY
}
debe "tras cambiar la carpeta por defecto, lanzar «simple» desde el panel abre el repo nuevo" t_cambio_carpeta
t_tareas_ruta() {
  sincfg
  py <<'PY'
import os, panel
T = os.environ["T"]
c, b = panel.accion({"tareas": True, "ruta": T + "/fuera/tareas-repo", "_idioma": "en"})
assert c == 200 and 'value="libre"' in b and "bbbbbb000001" in b and "Tarea externa" in b, (c, b)
c, b = panel.accion({"tareas": True, "ruta": T + "/proyectos/con_tareas", "_idioma": "en"})
assert c == 200 and "aaaaaa000003" in b and "bbbbbb000001" not in b, (c, b)
for mala in ("fuera/tareas-repo", T + "/fuera/no-git", T + "/fuera/web/sub", T + "/nope"):
    c, b = panel.accion({"tareas": True, "ruta": mala, "_idioma": "en"})
    assert c == 400, (mala, c, b)
PY
}
debe "tareas por ruta devuelve las tareas pendientes de ese repo y rechaza rutas inválidas" t_tareas_ruta
t_pestanas() {
  sincfg
  py <<'PY'
import config, html, panel
for i in ("es", "en"):
    pag = panel.pagina(i)
    assert 'role="tablist"' in pag and pag.count('role="tab"') == 3 and 'role="tabpanel"' in pag, i
    assert "aria-selected" in pag
    for k in ("config_tab_agentes", "config_tab_proyectos", "config_tab_tareas"):
        assert k in panel.CAT[i] and html.escape(panel.CAT[i][k]) in pag, (i, k)
    assert "tablero.example" not in pag
config.guardar_global({"tablero": "https://tablero.example/b"})
assert all("https://tablero.example/b" in panel.pagina(i) for i in ("es", "en"))
config.guardar_global({"tablero": ""})
assert all("tablero.example" not in panel.pagina(i) for i in ("es", "en"))
PY
}
debe "la configuración tiene 3 pestañas en es y en; el tablero aparece y desaparece en el pie" t_pestanas
t_catalogos() {
  py <<'PY'
import json
es = json.load(open("locales/es.json", encoding="utf-8"))
en = json.load(open("locales/en.json", encoding="utf-8"))
assert set(es) == set(en), sorted(set(es) ^ set(en))
PY
}
debe "es.json y en.json tienen las mismas claves" t_catalogos

echo "CLI"
t_cli_ruta() {
  sincfg
  "$DT" launch "$T/fuera/cli-repo" free --instruction "$T/encargo.txt" &&
  vivas | grep -qx 'cli-repo' &&
  python3 -c "
import json, os
reg = json.load(open('$DIXI_TOWER_HOME/proyectos.json'))
assert os.path.realpath(reg['cli-repo']['repo']) == os.path.realpath('$T/fuera/cli-repo'), reg
"
}
debe "launch /ruta/absoluta free funciona" t_cli_ruta
t_cli_config() {
  cfg "{\"carpeta_proyectos\": \"$T/otros\"}"
  "$DT" launch otro free --instruction "$T/encargo.txt" && vivas | grep -qx 'otro' &&
  "$DT" next otro 2>&1 | grep -q 'In review' &&
  ! "$DT" launch con_tareas free --instruction "$T/encargo.txt" &&
  ! "$DT" next con_tareas
}
debe "con carpeta configurada, launch/next <nombre> usan esa carpeta y no la variable" t_cli_config
t_cli_sin_carpeta() {
  cfg '{"carpeta_proyectos": ""}'
  local en es
  en="$("$DT" launch fantasma free --instruction "$T/encargo.txt" 2>&1)" && return 1
  es="$(LANG=es_MX.UTF-8 "$DT" launch fantasma free --instruction "$T/encargo.txt" 2>&1)" && return 1
  echo "$en" | grep -qi 'absolute path' && echo "$es" | grep -qi 'ruta absoluta' &&
  [ ! -f "$E/fantasma.json" ] &&
  "$DT" launch simple free --instruction "$T/encargo.txt"      # un proyecto ya registrado sigue funcionando
}
debe "sin carpeta, launch <nombre> no registrado explica que hay que dar la ruta absoluta (en y es)" t_cli_sin_carpeta
t_doctor() {
  local fuera
  sincfg
  fuera="$("$DT" doctor 2>&1)"; echo "$fuera" | grep 'Projects folder' | grep -q "$T/proyectos" &&
  echo "$fuera" | grep 'Projects folder' | grep -q 'DIXI_TOWER_PROJECTS' || return 1
  cfg "{\"carpeta_proyectos\": \"$T/otros\"}"
  fuera="$("$DT" doctor 2>&1)"; echo "$fuera" | grep 'Projects folder' | grep -q "$T/otros" &&
  echo "$fuera" | grep 'Projects folder' | grep -qiE 'settings|config' &&
  ! echo "$fuera" | grep 'Projects folder' | grep -q "$T/proyectos" || return 1
  cfg '{"carpeta_proyectos": ""}'
  fuera="$("$DT" doctor 2>&1)"; echo "$fuera" | grep 'Projects folder' | grep -qiE 'no default|none' &&
  ! echo "$fuera" | grep -q 'missing'
}
debe "doctor muestra la carpeta y su origen; sin carpeta lo dice" t_doctor

echo "HTTP"
t_403() {
  sincfg
  local cuerpo="{\"guardar_config\":true,\"agente\":null,\"config\":{\"carpeta_proyectos\":\"$T/otros\",\"tablero\":\"https://tablero.example/b\"}}"
  local tareas="{\"tareas\":true,\"ruta\":\"$T/fuera/web\"}" lanzar="{\"lanzar\":true,\"ruta\":\"$T/fuera/web\",\"tarea\":\"libre\",\"instruccion\":\"x\"}"
  local cuerpo_ in_ tk ok_origin="http://127.0.0.1:$P" cab
  tk="$(token)"; [ -n "$tk" ] || return 1
  local h_sin='{"Content-Type":"application/json"}' h_malo h_host h_origin
  h_malo="{\"X-Panel-Token\":\"mal\",\"Origin\":\"$ok_origin\"}"
  h_host="{\"X-Panel-Token\":\"$tk\",\"Host\":\"evil.example:$P\",\"Origin\":\"$ok_origin\"}"
  h_origin="{\"X-Panel-Token\":\"$tk\",\"Origin\":\"http://evil.example\"}"
  for cuerpo_ in "$cuerpo" "$tareas" "$lanzar"; do
    [ "$(codigo "$h_sin" "$cuerpo_")" = 403 ] || { echo "sin token no dio 403"; return 1; }
    [ "$(codigo "$h_malo" "$cuerpo_")" = 403 ] || { echo "token malo no dio 403"; return 1; }
    [ "$(codigo "$h_host" "$cuerpo_")" = 403 ] || { echo "Host ajeno no dio 403"; return 1; }
    [ "$(codigo "$h_origin" "$cuerpo_")" = 403 ] || { echo "Origin ajeno no dio 403"; return 1; }
  done
  [ ! -e "$DIXI_TOWER_HOME/config.json" ] || ! grep -q 'otros\|tablero' "$DIXI_TOWER_HOME/config.json"
}
debe "guardar config, tareas y lanzar con ruta: sin token, token malo, Host ajeno u Origin ajeno dan 403 y no cambian nada" t_403
t_guardar_http() {
  local c_en c_es t_en t_es
  sincfg
  [ "$(post_cfg "{\"carpeta_proyectos\":\"$T/otros\"}" en | head -1)" = 200 ] &&
  web GET "$P" /es/carpetas | tail -n +2 | python3 -c '
import sys
h = sys.stdin.read()
assert "value=\"otro\"" in h and "con_tareas" not in h, h
' &&
  [ "$(post_cfg '{"carpeta_proyectos":null}' en | head -1)" = 200 ] &&
  web GET "$P" /es/carpetas | tail -n +2 | grep -q con_tareas &&
  [ "$(web GET "$P" /es/carpetas | head -1)" = 200 ] || return 1
  # errores: 400 en el idioma de la página y archivo intacto
  cp "$DIXI_TOWER_HOME/config.json" "$T/config.antes" || return 1
  c_en="$(post_cfg '{"carpeta_proyectos":"relativa"}' en)"; c_es="$(post_cfg '{"carpeta_proyectos":"relativa"}' es)"
  [ "$(echo "$c_en" | head -1)" = 400 ] && [ "$(echo "$c_es" | head -1)" = 400 ] &&
  [ "$(echo "$c_en" | tail -n +2)" != "$(echo "$c_es" | tail -n +2)" ] || return 1
  t_en="$(post_cfg '{"tablero":"javascript:alert(1)"}' en)"; t_es="$(post_cfg '{"tablero":"javascript:alert(1)"}' es)"
  [ "$(echo "$t_en" | head -1)" = 400 ] && [ "$(echo "$t_es" | head -1)" = 400 ] &&
  [ "$(echo "$t_en" | tail -n +2)" != "$(echo "$t_es" | tail -n +2)" ] || return 1
  cmp -s "$DIXI_TOWER_HOME/config.json" "$T/config.antes" &&
  # tablero válido y vacío por la API
  [ "$(post_cfg '{"tablero":"https://tablero.example/b"}' en | head -1)" = 200 ] &&
  web GET "$P" /es/ | grep -q 'https://tablero.example/b' &&
  web GET "$P" /en/ | grep -q 'https://tablero.example/b' &&
  [ "$(post_cfg '{"tablero":""}' en | head -1)" = 200 ] &&
  ! web GET "$P" /en/ | grep -q 'tablero.example'
}
debe "guardar config con token cambia la carpeta (GET /es/carpetas lo refleja), valida en el idioma de la página y edita el tablero" t_guardar_http

echo
if [ "$fallos" -eq 0 ]; then echo "Todo pasó ($aciertos ok)."; else echo "$fallos prueba(s) fallaron, $aciertos ok."; fi
[ "$fallos" -eq 0 ]
