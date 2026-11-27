"""Aviso de fin de turno de un agente que corre con Codex.

Codex lo ejecuta (clave `notify`) al terminar cada turno, con un JSON como último
argumento: {"type": "agent-turn-complete", "thread-id": …, "last-assistant-message": …}.
Aquí se anota en el estado del agente y se avisa por macOS.

  codex-notify.py <agente> <carpeta-de-la-torre> <json>
"""
import glob
import json
import os
import shutil
import subprocess
import sys
import time


def main():
    agente, home = sys.argv[1], sys.argv[2]
    try:
        ev = json.loads(sys.argv[-1])
    except Exception:
        ev = {}
    if ev.get("type") not in (None, "agent-turn-complete"):
        return
    mensaje = ev.get("last-assistant-message") or ""
    try:
        interno = json.loads(mensaje)
    except ValueError:
        interno = None
    if isinstance(interno, dict) and "title" in interno:
        return                        # hilo interno de Codex que pone título a la conversación
    hilo = ev.get("thread-id") or ""
    codex_home = os.environ.get("CODEX_HOME") or os.path.expanduser("~/.codex")
    sesiones = os.path.join(codex_home, "sessions")
    # Solo es la conversación principal si Codex guardó su historial con ese id.
    hilo_valido = bool(hilo) and (not os.path.isdir(sesiones) or
                                  bool(glob.glob(os.path.join(sesiones, "**", f"rollout-*{hilo}.jsonl"), recursive=True)))
    ruta = os.path.join(home, "estado", f"{agente}.json")
    try:
        d = json.load(open(ruta, encoding="utf-8"))
    except Exception:
        return
    d.update(estado="en_pausa", actualizado=time.time(), motor_sesion="codex",
             detalle=(mensaje or "terminó su turno")[-300:])
    if hilo_valido:
        d["session_id"] = hilo
    with open(ruta + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    os.replace(ruta + ".tmp", ruta)

    if (os.environ.get("DIXI_TOWER_NOTIFY") or os.environ.get("DIXI_AGENTES_AVISOS") or "1") == "0":
        return
    sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))
    from avisos import avisar_escritorio
    avisar_escritorio(f"Agente {agente}", "terminó su turno", agente)


try:
    main()
except Exception:
    pass
