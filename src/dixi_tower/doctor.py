"""Revisa que la máquina tiene lo que Dixi Tower necesita.

  doctor.py <puerto> <ruta-del-servicio>

Sale con 1 si falta algo imprescindible.
"""
import os
import platform
import shutil
import subprocess
import sys
import urllib.request

import config

ES = (os.environ.get("LC_ALL") or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "").startswith("es")
T = lambda es, en: es if ES else en
puerto, servicio = sys.argv[1], sys.argv[2]
faltan = 0


def linea(ok, texto, detalle="", opcional=False):
    global faltan
    marca = "✓" if ok else ("·" if opcional else "✗")
    if not ok and not opcional:
        faltan += 1
    print(f"  {marca} {texto}" + (f" — {detalle}" if detalle else ""))


def version(*orden):
    try:
        r = subprocess.run(orden, capture_output=True, text=True, timeout=10)
        return (r.stdout or r.stderr).strip().splitlines()[0][:60]
    except Exception:
        return ""


print(T("Requisitos", "Requirements"))
linea(sys.version_info >= (3, 9), f"Python {platform.python_version()}", "" if sys.version_info >= (3, 9) else T("hace falta 3.9 o posterior", "3.9 or later is required"))
for programa in ("bash", "git", "tmux"):
    ruta = shutil.which(programa)
    linea(bool(ruta), programa, ruta or T("no está instalado", "not installed"))

print(T("\nMotores (hace falta al menos uno)", "\nEngines (at least one is required)"))
encontrados = 0
for motor, programa in (("Claude Code", "claude"), ("Codex", "codex")):
    ruta = shutil.which(programa)
    encontrados += bool(ruta)
    linea(bool(ruta), motor, version(programa, "--version") if ruta else T("no está instalado", "not installed"), opcional=True)
for nombre, d in config.motores_propios().items():
    programa = d["comando"].split()[0]
    ruta = shutil.which(programa)
    encontrados += bool(ruta)
    linea(bool(ruta), f"{nombre} ({T('propio', 'custom')})", ruta or T(f"no encuentro «{programa}»", f"cannot find “{programa}”"), opcional=True)
if not encontrados:
    faltan += 1
    print("  ✗ " + T("ningún motor disponible", "no engine available"))

print(T("\nOpcionales", "\nOptional"))
linea(bool(shutil.which("gh")), "gh", T("para que los agentes abran pull requests", "so agents can open pull requests"), opcional=True)
if platform.system() == "Darwin":
    linea(bool(shutil.which("terminal-notifier")), "terminal-notifier", T("avisos que abren el panel al hacer clic", "notifications that open the panel on click"), opcional=True)

print(T("\nInstalación", "\nInstallation"))
linea(True, T("Carpeta de datos", "Data folder"), config.HOME_AG + ("" if os.path.isdir(config.HOME_AG) else T(" (se crea al primer uso)", " (created on first use)")))
proyectos = config.entorno("DIXI_TOWER_PROJECTS", "DIXI_PROYECTOS_DIR", os.path.expanduser("~/projects"))
linea(os.path.isdir(proyectos), T("Carpeta de proyectos", "Projects folder"), proyectos + ("" if os.path.isdir(proyectos) else T(" — no existe; cámbiala con DIXI_TOWER_PROJECTS", " — missing; change it with DIXI_TOWER_PROJECTS")), opcional=True)
try:
    urllib.request.urlopen(f"http://127.0.0.1:{puerto}/es/lista", timeout=2)
    responde = True
except Exception:
    responde = False
linea(responde, T("Panel", "Panel"), f"http://localhost:{puerto}/" if responde else T("no está corriendo: dixi-tower panel", "not running: dixi-tower panel"), opcional=True)
if platform.system() == "Darwin":
    linea(os.path.isfile(servicio), T("Servicio (siempre encendido)", "Service (always on)"), "" if os.path.isfile(servicio) else T("dixi-tower servicio instalar", "dixi-tower service install"), opcional=True)

print()
print(T("Todo lo imprescindible está." if not faltan else f"Faltan {faltan} requisitos imprescindibles (✗).",
        "Everything required is in place." if not faltan else f"{faltan} required item(s) missing (✗)."))
sys.exit(1 if faltan else 0)
