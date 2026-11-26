"""Barra de estado de un agente local.

Claude Code entrega a la barra de estado el uso de la cuenta (semana y ventana
de 5 horas) y el contexto restante. Aquí se guardan en ~/.agentes/uso/<agente>.json
para que el panel los muestre y `control.py` aplique los límites, y después se
ejecuta la barra de estado propia del usuario para que la siga viendo igual.
"""
import json
import os
import subprocess
import sys
import time

crudo = sys.stdin.read()
try:
    datos = json.loads(crudo)
except Exception:
    datos = {}

agente = os.environ.get("DIXI_AGENTE_ID") or os.environ.get("DIXI_AGENTE_PROYECTO")
if agente:
    try:
        limites = datos.get("rate_limits") or {}
        semana, sesion = limites.get("seven_day") or {}, limites.get("five_hour") or {}
        registro = {
            "semana": semana.get("used_percentage"),
            "semana_vence": semana.get("resets_at"),
            "sesion": sesion.get("used_percentage"),
            "sesion_vence": sesion.get("resets_at"),
            "contexto_libre": (datos.get("context_window") or {}).get("remaining_percentage"),
            "modelo": (datos.get("model") or {}).get("display_name"),
            "actualizado": time.time(),
        }
        home = os.environ.get("DIXI_AGENTES_HOME", os.path.expanduser("~/.agentes"))
        ruta = os.path.join(home, "uso", f"{agente}.json")
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta + ".tmp", "w", encoding="utf-8") as fh:
            json.dump(registro, fh)
        os.replace(ruta + ".tmp", ruta)
    except Exception:
        pass

# La barra del usuario, tal como la tiene configurada.
try:
    propia = json.load(open(os.path.expanduser("~/.claude/settings.json"), encoding="utf-8"))
    comando = (propia.get("statusLine") or {}).get("command")
    if comando and "barra.py" not in comando:
        r = subprocess.run(comando, shell=True, input=crudo, capture_output=True, text=True, timeout=5)
        sys.stdout.write(r.stdout)
except Exception:
    pass
