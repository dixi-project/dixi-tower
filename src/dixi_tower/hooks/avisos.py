"""Avisos de escritorio de los agentes, compartidos por los hooks."""
import os
import subprocess


def avisar_escritorio(titulo, texto, agente):
    """Aviso de escritorio. macOS: terminal-notifier (el clic abre el panel en el
    agente) u osascript. Linux: notify-send. Sin ninguno, no avisa."""
    import platform
    import shutil
    puerto = os.environ.get("DIXI_TOWER_PORT") or os.environ.get("DIXI_AGENTES_PUERTO") or "4310"
    notificador = shutil.which("terminal-notifier") or next(
        (r for r in ("/opt/homebrew/bin/terminal-notifier", "/usr/local/bin/terminal-notifier") if os.path.exists(r)), None)
    if notificador:
        orden = [notificador, "-title", titulo, "-message", texto.lstrip("-[") or "aviso",
                 "-group", f"agente-{agente}", "-open", f"http://localhost:{puerto}/#{agente}"]
    elif shutil.which("notify-send"):
        orden = ["notify-send", "--app-name=Dixi Tower", titulo, texto]
    elif platform.system() == "Darwin":
        limpio = lambda v: v.replace("\\", " ").replace('"', "'")
        orden = ["osascript", "-e", f'display notification "{limpio(texto)}" with title "{limpio(titulo)}"']
    else:
        return
    subprocess.run(orden, capture_output=True, timeout=5)
