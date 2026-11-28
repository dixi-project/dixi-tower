#!/usr/bin/env bash
# Pruebas de la carpeta de proyectos por defecto y del aviso de primera vez.
#
# Todo ocurre en una carpeta temporal: HOME, datos y carpetas son propios. No usa
# tmux, ni sesiones de modelo, ni el panel HTTP: llama directamente a
# panel.pagina(), panel.info_carpeta() y panel.accion().
#
#   tests/aviso-carpeta.sh
set -uo pipefail
AQUI="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
SRC="${DIXI_TOWER_SRC:-$AQUI/src/dixi_tower}"
T="$(mktemp -d "${TMPDIR:-/tmp}/dixi-tower-aviso.XXXXXX")"
T="$(cd "$T" && pwd -P)"
export T SRC PYTHONPATH="$SRC"
export HOME="$T/casa" DIXI_TOWER_HOME="$T/datos"
unset DIXI_TOWER_PROJECTS DIXI_PROYECTOS_DIR DIXI_AGENTES_HOME DIXI_AGENTES_REGISTRO DIXI_TOWER_LANG LC_ALL LC_MESSAGES
export LANG=en_US.UTF-8
fallos=0 aciertos=0
ok()   { echo "  ok   $1"; aciertos=$((aciertos + 1)); }
mal()  { echo "  FAIL $1"; fallos=$((fallos + 1)); }
debe() {
  local salida
  if salida="$(eval "$2" 2>&1)"; then ok "$1"
  else mal "$1"; [ -n "$salida" ] && printf '%s\n' "$salida" | tail -n 4 | cut -c1-220 | sed 's/^/         | /'; fi
  return 0
}
trap 'rm -rf "$T"' EXIT
mkdir -p "$T/casa" "$T/datos" "$T/aux"
cfg()    { mkdir -p "$DIXI_TOWER_HOME"; printf '%s' "$1" > "$DIXI_TOWER_HOME/config.json"; }
sincfg() { rm -f "$DIXI_TOWER_HOME/config.json"; }

# Comprobador común: chequeo.py VISIBLE|HIDDEN ELEGIR(True|False) MODO
cat > "$T/aux/chequeo.py" <<'PY'
import re, sys, html
import panel
visible, elegir, modo = sys.argv[1:4]
cp = panel.info_carpeta()
claves = {"modo", "valor", "efectiva", "origen", "disponible", "base", "base_origen"}
assert claves <= set(cp), f"faltan claves en info_carpeta: {claves - set(cp)}"
assert str(cp.get("elegir")) == elegir, f"elegir={cp.get('elegir')!r}, esperado {elegir}"
assert cp["modo"] == modo, f"modo={cp['modo']!r}, esperado {modo}"
for i in ("es", "en"):
    h = panel.pagina(i)
    m = re.search(r'<div id="aviso-carpeta"([^>]*)>', h)
    assert m, f"[{i}] no existe #aviso-carpeta"
    assert 'role="status"' in m.group(1), f"[{i}] falta role=status"
    oculto = bool(re.search(r"\bhidden\b", m.group(1)))
    assert oculto == (visible == "HIDDEN"), f"[{i}] hidden={oculto}, esperado {visible}"
    assert 'id="aviso-carpeta-abrir"' in h, f"[{i}] falta el botón del aviso"
    if visible == "VISIBLE":
        assert html.escape(panel.CAT[i]["aviso_carpeta_titulo"]) in h, f"[{i}] falta el título"
        assert html.escape(cp["efectiva"]) in h, f"[{i}] falta la ruta"
PY
chequeo() { (cd "$SRC" && python3 -B "$T/aux/chequeo.py" "$@"); }

echo "Aviso de primera vez"
sincfg; rm -rf "$T/casa/projects"
debe "a. sin config y sin carpeta por defecto: aviso visible, elegir=True, modo predeterminada" 'chequeo VISIBLE True predeterminada'
mkdir -p "$T/casa/projects"
debe "b. con la carpeta por defecto creada: aviso oculto, elegir=False" 'chequeo HIDDEN False predeterminada'
rm -rf "$T/casa/projects"
debe "c. DIXI_TOWER_PROJECTS inexistente sin config: aviso visible" 'DIXI_TOWER_PROJECTS="$T/no-existe" chequeo VISIBLE True predeterminada'
mkdir -p "$T/existe"
debe "d. DIXI_TOWER_PROJECTS existente sin config: aviso oculto" 'DIXI_TOWER_PROJECTS="$T/existe" chequeo HIDDEN False predeterminada'
cfg "{\"carpeta_proyectos\":\"$T/no-existe\"}"
debe "e. ruta guardada inexistente: aviso oculto, modo carpeta" 'chequeo HIDDEN False carpeta'
cfg '{"carpeta_proyectos":""}'
debe "f. Ninguna guardada: aviso oculto, modo ninguna" 'chequeo HIDDEN False ninguna'
sincfg

echo "Interfaz"
cat > "$T/aux/ui.py" <<'PY'
import html, sys
import panel
for i in ("es", "en"):
    h = panel.pagina(i)
    for malo in ('value="predeterminada"', "aj-c-pred", "aj-origenes"):
        assert malo not in h, f"[{i}] sigue presente: {malo}"
    for bueno in ('name="aj-cmodo" value="carpeta"', 'value="ninguna"', 'id="aj-c-sugerida"'):
        assert bueno in h, f"[{i}] falta: {bueno}"
    texto = html.escape(panel.CAT[i]["carpeta_modo_carpeta"])
    assert texto == {"es": "Carpeta de proyectos por defecto:", "en": "Default projects folder:"}[i], f"[{i}] texto: {texto!r}"
    assert texto in h, f"[{i}] falta el texto del radio"
PY
debe "g. Proyectos: dos radios (carpeta, ninguna), campo y ayuda sugerida; sin predeterminada" '(cd "$SRC" && python3 -B "$T/aux/ui.py")'
cat > "$T/aux/hostil.py" <<'PY'
import panel
h = panel.pagina("es")
assert "&lt;x&quot;" in h, "no aparece la ruta escapada"
assert '<x"' not in h, "ruta sin escapar en la página"
PY
debe "h. ruta hostil en la variable de entorno: sale escapada" 'DIXI_TOWER_PROJECTS="$T/<x\"&'"'"'>" bash -c "cd \"\$SRC\" && python3 -B \"\$T/aux/hostil.py\""'

echo "Guardado y catálogos"
cat > "$T/aux/guardar.py" <<'PY'
import json, os
import panel
c, m = panel.accion({"guardar_config": True, "agente": None, "config": {"tope_revision": 2}, "_idioma": "es"})
assert c == 200, f"accion devolvió {c}: {m}"
datos = json.load(open(os.path.join(os.environ["DIXI_TOWER_HOME"], "config.json")))
assert "carpeta_proyectos" not in datos, f"se creó carpeta_proyectos: {datos}"
assert datos.get("tope_revision") == 2, f"no se guardó tope_revision: {datos}"
PY
sincfg
debe "i. guardar sin tocar Proyectos no crea carpeta_proyectos (200)" '(cd "$SRC" && python3 -B "$T/aux/guardar.py")'
cat > "$T/aux/cat.py" <<'PY'
import os, re
import panel
es, en = set(panel.CAT["es"]), set(panel.CAT["en"])
assert es == en, f"claves distintas: {sorted(es ^ en)}"
for k in ("aviso_carpeta_titulo", "aviso_carpeta_texto", "aviso_carpeta_boton", "carpeta_sugerida"):
    assert k in es, f"falta la clave {k}"
fuente = open(os.path.join(os.path.dirname(panel.__file__), "panel.py"), encoding="utf-8").read()
for malo in ("carpeta_modo_predeterminada", "carpeta_origen_"):
    assert malo not in fuente, f"{malo} sigue en panel.py"
    assert not any(malo in k for k in es | en), f"{malo} sigue en los catálogos"
PY
debe "j. catálogos es/en con las mismas claves, claves nuevas y sin las obsoletas" '(cd "$SRC" && python3 -B "$T/aux/cat.py")'
cat > "$T/aux/jscss.py" <<'PY'
import panel
assert "abrirAjustes(null,'proyectos')" in panel.JS, "JS sin abrirAjustes(null,'proyectos')"
assert "#aviso-carpeta[hidden]" in panel.CSS, "CSS sin #aviso-carpeta[hidden]"
PY
debe "k. JS abre Proyectos desde el aviso y CSS respeta hidden" '(cd "$SRC" && python3 -B "$T/aux/jscss.py")'

echo
echo "$aciertos ok, $fallos con fallos"
[ "$fallos" -eq 0 ]
