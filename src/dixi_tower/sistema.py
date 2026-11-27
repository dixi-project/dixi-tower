"""Detalles del sistema que cambian cómo se comporta Dixi Tower.

Windows se soporta a través de WSL2: Dixi Tower corre dentro de Linux, el panel se
abre desde el navegador de Windows y los avisos se muestran con PowerShell.
"""
import os


def es_wsl(version="/proc/version"):
    """True si corremos dentro de WSL (Linux de Windows)."""
    if os.environ.get("WSL_DISTRO_NAME"):
        return True
    try:
        with open(version, encoding="utf-8", errors="ignore") as fh:
            return "microsoft" in fh.read().lower()
    except OSError:
        return False


def en_disco_de_windows(ruta):
    """True si la ruta está en un disco de Windows montado en WSL (/mnt/c/…).

    Ahí git y los agentes van muy lentos y los permisos no son los de Linux."""
    partes = os.path.realpath(ruta).split(os.sep)
    return len(partes) > 2 and partes[1] == "mnt" and len(partes[2]) == 1
