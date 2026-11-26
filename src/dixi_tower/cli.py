"""Punto de entrada del comando `dixi-tower`.

El lanzador es un script de bash que vive junto a este archivo; aquí solo se
localiza y se ejecuta con los mismos argumentos.
"""
import os
import shutil
import sys

from . import __version__


def main():
    if sys.argv[1:2] in (["--version"], ["-V"]):
        print(f"dixi-tower {__version__}")
        return 0
    bash = shutil.which("bash")
    if not bash:
        print("dixi-tower necesita bash.", file=sys.stderr)
        return 1
    guion = os.path.join(os.path.dirname(os.path.abspath(__file__)), "agentes.sh")
    os.execv(bash, [bash, guion, *sys.argv[1:]])


if __name__ == "__main__":
    sys.exit(main())
