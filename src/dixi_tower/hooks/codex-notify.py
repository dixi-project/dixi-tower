"""Aviso de fin de turno de un agente que corre con Codex.

Codex lo ejecuta (clave `notify`) al terminar cada turno, con un JSON como último
argumento: {"type": "agent-turn-complete", "thread-id": …, "last-assistant-message": …}.
Aquí se anota en el estado del agente y se avisa por macOS.

  codex-notify.py <agente> <carpeta-de-la-torre> <json>
"""
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
    ruta = os.path.join(home, "estado", f"{agente}.json")
    try:
        d = json.load(open(ruta, encoding="utf-8"))
    except Exception:
        return
    d.update(estado="en_pausa", actualizado=time.time(), motor_sesion="codex",
             detalle=(ev.get("last-assistant-message") or "terminó su turno")[-300:])
    if ev.get("thread-id"):
        d["session_id"] = ev["thread-id"]
    with open(ruta + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    os.replace(ruta + ".tmp", ruta)

    if os.environ.get("DIXI_AGENTES_AVISOS", "1") == "0":
        return
    notificador = shutil.which("terminal-notifier") or next(
        (r for r in ("/opt/homebrew/bin/terminal-notifier", "/usr/local/bin/terminal-notifier") if os.path.exists(r)), None)
    if notificador:
        puerto = os.environ.get("DIXI_AGENTES_PUERTO", "4310")
        subprocess.run([notificador, "-title", f"Agente {agente}", "-message", "terminó su turno",
                        "-group", f"agente-{agente}", "-open", f"http://localhost:{puerto}/#{agente}"],
                       capture_output=True, timeout=5)


try:
    main()
except Exception:
    pass
