"""Tabla de estado de los agentes locales. Uso: estado.py <home> <registro> <sesion-tmux>"""
import glob
import json
import os
import subprocess
import sys
import time

from mensajes import t

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
ETIQUETA = {e: t("e_" + e) for e in ("lanzando", "trabajando", "en_pausa", "te_necesita", "cerrado")}

archivos = sorted(glob.glob(os.path.join(home, "estado", "*.json")))
if not archivos:
    print(t("sin_agentes"))
for f in archivos:
    d = json.load(open(f))
    p = d["proyecto"]
    ag = d.get("agente") or p
    estado = d.get("estado", "?")
    if ag not in vivas and estado != "cerrado":
        estado = "cerrado"
        d["detalle"] = d.get("detalle") or t("ventana_cerrada")
    base = proyectos.get(p, {}).get("base", "main")
    wt = d.get("worktree", "")
    commits = ""
    if os.path.isdir(wt):
        commits = (sh("git", "-C", wt, "rev-list", "--count", f"origin/{base}..HEAD")
                   or sh("git", "-C", wt, "rev-list", "--count", f"{base}..HEAD"))
    sucio = len(sh("git", "-C", wt, "status", "--porcelain").splitlines()) if os.path.isdir(wt) else 0
    print(f"■ {ag}  —  {ETIQUETA.get(estado, estado)}  ({t('hace', t=hace(d.get('actualizado', 0)))})")
    tarea = t("instruccion_libre") if d.get("tarea") == "libre" else f"st:{d.get('tarea')}"
    print(t("fila_tarea", tarea=tarea, titulo=d.get("titulo", "")[:90]))
    print(t("fila_rama", rama=d.get("rama"), commits=commits or 0, sucios=sucio))
    if d.get("detalle"):
        print(t("fila_ultimo", detalle=d["detalle"][:300]))
    print()
