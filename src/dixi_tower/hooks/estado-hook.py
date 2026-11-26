"""Hook de estado de un agente local.

Escribe ~/.agentes/estado/<proyecto>.json en cada evento de la sesión para que
la torre sepa qué hace el agente sin depender de lo que el modelo diga.
Nunca bloquea: ante cualquier error sale con 0.
"""
import json
import os
import subprocess
import sys
import time


def main():
    proyecto = os.environ.get("DIXI_AGENTE_PROYECTO")
    if not proyecto:
        return
    # Nombre del agente: igual al proyecto, o <proyecto>@N si hay varios a la vez.
    agente = os.environ.get("DIXI_AGENTE_ID") or proyecto
    try:
        ev = json.load(sys.stdin)
    except Exception:
        ev = {}
    nombre = ev.get("hook_event_name", "")
    home = os.environ.get("DIXI_AGENTES_HOME", os.path.expanduser("~/.agentes"))
    ruta = os.path.join(home, "estado", f"{agente}.json")
    try:
        d = json.load(open(ruta))
    except Exception:
        d = {}

    avisar = None
    if nombre in ("SessionStart", "UserPromptSubmit"):
        d["estado"] = "trabajando"
    elif nombre == "PostToolUse":
        d["estado"] = "trabajando"
        entrada = ev.get("tool_input") or {}
        pista = entrada.get("command") or entrada.get("file_path") or entrada.get("description") or ""
        d["detalle"] = f"{ev.get('tool_name', '')}: {str(pista)[:200]}"
    elif nombre == "Stop":
        d["estado"] = "en_pausa"
        d["detalle"] = (ev.get("last_assistant_message") or "terminó su turno")[-300:]
        avisar = "terminó su turno"
    elif nombre == "Notification":
        msg = ev.get("message", "")
        if "waiting for your input" not in msg:
            d["estado"] = "te_necesita"
            d["detalle"] = msg[:300]
            avisar = msg[:120] or "te necesita"
    elif nombre == "SessionEnd":
        d["estado"] = "cerrado"
    else:
        return

    d.update(
        agente=agente,
        proyecto=proyecto,
        tarea=os.environ.get("DIXI_AGENTE_TAREA", d.get("tarea")),
        titulo=os.environ.get("DIXI_AGENTE_TITULO", d.get("titulo")),
        rama=os.environ.get("DIXI_AGENTE_RAMA", d.get("rama")),
        worktree=ev.get("cwd") or d.get("worktree"),
        session_id=ev.get("session_id"),
        actualizado=time.time(),
    )
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w") as fh:
        json.dump(d, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)

    if avisar:
        if os.environ.get("DIXI_AGENTES_AVISOS", "1") == "0":
            return
        # terminal-notifier: al hacer clic abre el panel en ese agente. Con
        # osascript el aviso sale a nombre de «Script Editor» y el clic abre esa app.
        import shutil
        notificador = shutil.which("terminal-notifier") or next(
            (r for r in ("/opt/homebrew/bin/terminal-notifier", "/usr/local/bin/terminal-notifier") if os.path.exists(r)), None)
        if notificador:
            puerto = os.environ.get("DIXI_AGENTES_PUERTO", "4310")
            subprocess.run(
                [notificador, "-title", f"Agente {agente}", "-message", avisar.lstrip("-[") or "aviso",
                 "-group", f"agente-{agente}", "-open", f"http://localhost:{puerto}/#{agente}"],
                capture_output=True, timeout=5,
            )
            return
        texto = avisar.replace("\\", " ").replace('"', "'")
        subprocess.run(
            ["osascript", "-e", f'display notification "{texto}" with title "Agente {agente}"'],
            capture_output=True, timeout=5,
        )


try:
    main()
except Exception:
    pass
sys.exit(0)
