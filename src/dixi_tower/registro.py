"""Da de alta en el registro de proyectos un repositorio de la carpeta de proyectos.

  registro.py <proyectos.json> <carpeta-de-proyectos> <nombre>

No hace nada si ya está registrado. Deduce la rama base (origin/HEAD, main,
master o la rama actual) y si el proyecto tiene el comando /build.
"""
import json
import os
import subprocess
import sys

registro, raiz, nombre = sys.argv[1:4]
try:
    datos = json.load(open(registro, encoding="utf-8"))
except FileNotFoundError:
    datos = {}      # primera vez: el registro nace vacío
if nombre in datos:
    sys.exit(0)

repo = os.path.join(raiz, nombre)
if os.sep in nombre or nombre.startswith(".") or not os.path.exists(os.path.join(repo, ".git")):
    sys.exit(f"No es un repositorio git dentro de {raiz}: {nombre}")


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
    sys.exit(f"No pude determinar la rama base de {nombre}")

datos[nombre] = {
    "repo": repo,
    "base": base,
    "comando": "/build" if os.path.exists(os.path.join(repo, ".claude", "commands", "build.md")) else "",
    "max_en_revision": 3,
}
os.makedirs(os.path.dirname(registro), exist_ok=True)
with open(registro, "w", encoding="utf-8") as fh:
    json.dump(datos, fh, ensure_ascii=False, indent=2)
    fh.write("\n")
print(f"Registrado {nombre} (rama base {base})", file=sys.stderr)
