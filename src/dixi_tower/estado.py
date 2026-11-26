"""Tabla de estado de los agentes locales. Uso: estado.py <home> <registro> <sesion-tmux>"""
import glob
import json
import os
import subprocess
import sys
import time

home, registro, sesion = sys.argv[1:4]
try:
    proyectos = json.load(open(registro))
except FileNotFoundError:
    proyectos = {}


def sh(*args):
    r = subprocess.run(args, capture_output=True, text=True)
    return r.stdout.strip() if r.returncode == 0 else ""


def hace(ts):
    s = int(time.time() - ts)
    if s < 90:
        return f"{s}s"
    if s < 5400:
        return f"{s // 60}min"
    return f"{s // 3600}h"


vivas = set(sh("tmux", "list-windows", "-t", sesion, "-F", "#W").splitlines())
ETIQUETA = {
    "lanzando": "lanzando",
    "trabajando": "trabajando",
    "en_pausa": "EN PAUSA (terminó turno)",
    "te_necesita": "TE NECESITA",
    "cerrado": "cerrado",
}

archivos = sorted(glob.glob(os.path.join(home, "estado", "*.json")))
if not archivos:
    print("Sin agentes lanzados todavía.")
for f in archivos:
    d = json.load(open(f))
    p = d["proyecto"]
    ag = d.get("agente") or p
    estado = d.get("estado", "?")
    if ag not in vivas and estado != "cerrado":
        estado = "cerrado"
        d["detalle"] = d.get("detalle") or "la ventana ya no existe"
    base = proyectos.get(p, {}).get("base", "main")
    wt = d.get("worktree", "")
    commits = ""
    if os.path.isdir(wt):
        commits = (sh("git", "-C", wt, "rev-list", "--count", f"origin/{base}..HEAD")
                   or sh("git", "-C", wt, "rev-list", "--count", f"{base}..HEAD"))
    sucio = len(sh("git", "-C", wt, "status", "--porcelain").splitlines()) if os.path.isdir(wt) else 0
    print(f"■ {ag}  —  {ETIQUETA.get(estado, estado)}  (hace {hace(d.get('actualizado', 0))})")
    tarea = "instrucción libre" if d.get("tarea") == "libre" else f"st:{d.get('tarea')}"
    print(f"    tarea : {tarea}  {d.get('titulo', '')[:90]}")
    print(f"    rama  : {d.get('rama')}  ·  {commits or 0} commits  ·  {sucio} archivos sin commit")
    if d.get("detalle"):
        print(f"    último: {d['detalle'][:300]}")
    print()
