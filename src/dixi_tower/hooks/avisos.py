"""Avisos de escritorio de los agentes, compartidos por los hooks."""
import base64
import os
import subprocess
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

# Notificación nativa de Windows desde WSL. Los textos llegan por variables de
# entorno (WSLENV las pasa a Windows) para no tener que escaparlos en la orden.
# El clic abre el panel en el agente. Se muestra con el identificador de PowerShell,
# que Windows ya tiene registrado, para no instalar nada.
TOAST_WINDOWS = r"""
$ErrorActionPreference = 'Stop'
[void][Windows.UI.Notifications.ToastNotificationManager, Windows.UI.Notifications, ContentType = WindowsRuntime]
[void][Windows.Data.Xml.Dom.XmlDocument, Windows.Data.Xml.Dom.XmlDocument, ContentType = WindowsRuntime]
$e = [System.Security.SecurityElement]
$xml = '<toast activationType="protocol" launch="' + $e::Escape($env:DT_URL) + '"><visual><binding template="ToastGeneric">' +
       '<text>' + $e::Escape($env:DT_TITULO) + '</text><text>' + $e::Escape($env:DT_TEXTO) + '</text>' +
       '</binding></visual></toast>'
$doc = New-Object Windows.Data.Xml.Dom.XmlDocument
$doc.LoadXml($xml)
$app = '{1AC14E77-02E7-4E5D-B744-2EB1AE5198B7}\WindowsPowerShell\v1.0\powershell.exe'
[Windows.UI.Notifications.ToastNotificationManager]::CreateToastNotifier($app).Show([Windows.UI.Notifications.ToastNotification]::new($doc))
"""


def orden_windows(powershell, titulo, texto, url):
    """Orden y entorno para mostrar un aviso de Windows desde WSL."""
    codificado = base64.b64encode(TOAST_WINDOWS.encode("utf-16-le")).decode()
    entorno = dict(os.environ, DT_TITULO=titulo, DT_TEXTO=texto, DT_URL=url)
    previas = os.environ.get("WSLENV", "")
    entorno["WSLENV"] = ":".join(p for p in (previas, "DT_TITULO/u:DT_TEXTO/u:DT_URL/u") if p)
    orden = [powershell, "-NoProfile", "-NonInteractive", "-ExecutionPolicy", "Bypass", "-EncodedCommand", codificado]
    return orden, entorno


def avisar_escritorio(titulo, texto, agente):
    """Aviso de escritorio. macOS: terminal-notifier (el clic abre el panel en el
    agente) u osascript. Windows (WSL): notificación nativa con PowerShell.
    Linux: notify-send. Sin ninguno, no avisa."""
    import platform
    import shutil
    from sistema import es_wsl
    puerto = os.environ.get("DIXI_TOWER_PORT") or os.environ.get("DIXI_AGENTES_PUERTO") or "4310"
    url = f"http://localhost:{puerto}/#{agente}"
    notificador = shutil.which("terminal-notifier") or next(
        (r for r in ("/opt/homebrew/bin/terminal-notifier", "/usr/local/bin/terminal-notifier") if os.path.exists(r)), None)
    if notificador:
        orden = [notificador, "-title", titulo, "-message", texto.lstrip("-[") or "aviso",
                 "-group", f"agente-{agente}", "-open", url]
    elif es_wsl() and shutil.which("powershell.exe"):
        # PowerShell tarda en arrancar: se lanza sin esperar para no frenar al agente.
        orden, entorno = orden_windows(shutil.which("powershell.exe"), titulo, texto, url)
        subprocess.Popen(orden, env=entorno, stdin=subprocess.DEVNULL, stdout=subprocess.DEVNULL,
                         stderr=subprocess.DEVNULL, start_new_session=True)
        return
    elif shutil.which("notify-send"):
        orden = ["notify-send", "--app-name=Dixi Tower", titulo, texto]
    elif platform.system() == "Darwin":
        limpio = lambda v: v.replace("\\", " ").replace('"', "'")
        orden = ["osascript", "-e", f'display notification "{limpio(texto)}" with title "{limpio(titulo)}"']
    else:
        return
    subprocess.run(orden, capture_output=True, timeout=5)
