"""Da de alta en el registro de proyectos un repositorio de la carpeta de proyectos.

  registro.py <proyectos.json> <carpeta-de-proyectos> <nombre>
  registro.py <proyectos.json> --ruta <ruta-del-repo> <carpeta-de-datos>

No hace nada si ya está registrado. Con --ruta registra un repositorio de cualquier
sitio (su raíz, con .git) y escribe en stdout la clave con la que quedó. Deduce la rama base (origin/HEAD, main,
master o la rama actual) y si el proyecto tiene el comando /build.
"""
import json
import os
import re
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
from mensajes import t  # noqa: E402

registro = sys.argv[1]
try:
    datos = json.load(open(registro, encoding="utf-8"))
except FileNotFoundError:
    datos = {}      # primera vez: el registro nace vacío


def clave_para(ruta, home_ag):
    """Clave del repo en `ruta`: la que ya tiene, o una nueva saneada y sin chocar."""
    real = os.path.realpath(ruta)
    datos_real = os.path.realpath(home_ag)
    if not os.path.isdir(real) or not os.path.exists(os.path.join(real, ".git")):
        sys.exit(t("ruta_no_repo", ruta=ruta))
    if real == datos_real or real.startswith(datos_real + os.sep):
        sys.exit(t("ruta_en_datos", ruta=ruta))
    for clave, d in datos.items():
        if os.path.realpath(d.get("repo", "")) == real:
            return clave, real, True
    base = re.sub(r"[^\w-]", "-", os.path.basename(real)).strip("-") or "repo"
    clave, n = base, 2
    while clave in datos:
        clave, n = f"{base}-{n}", n + 1
    return clave, real, False


if sys.argv[2] == "--ruta":
    nombre, repo, existente = clave_para(sys.argv[3], sys.argv[4])
    if existente:
        print(nombre)
        sys.exit(0)
else:
    raiz, nombre = sys.argv[2:4]
    if nombre in datos:
        sys.exit(0)
    if not raiz:
        sys.exit(t("sin_carpeta_proyectos", nombre=nombre))
    repo = os.path.join(raiz, nombre)
    if os.sep in nombre or nombre.startswith(".") or not os.path.exists(os.path.join(repo, ".git")):
        sys.exit(t("no_es_repo", raiz=raiz, nombre=nombre))


def git(*args):
    r = subprocess.run(["git", "-C", repo, *args], capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


base = git("symbolic-ref", "--short", "refs/remotes/origin/HEAD").replace("origin/", "", 1)
if not base:
    for candidata in ("main", "master"):
        if git("rev-parse", "--verify", "--quiet", f"refs/remotes/origin/{candidata}") or \
           git("rev-parse", "--verify", "--quiet", f"refs/heads/{candidata}"):
            base = candidata
            break
if not base:
    base = git("branch", "--show-current")
if not base:
    sys.exit(t("sin_rama_base", nombre=nombre))

datos[nombre] = {
    "repo": repo,
    "base": base,
    "comando": "/build" if os.path.exists(os.path.join(repo, ".claude", "commands", "build.md")) else "",
}
os.makedirs(os.path.dirname(registro), exist_ok=True)
with open(registro, "w", encoding="utf-8") as fh:
    json.dump(datos, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
print(t("registrado", nombre=nombre, base=base), file=sys.stderr)
if sys.argv[2] == "--ruta":
    print(nombre)
