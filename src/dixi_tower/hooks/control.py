"""Control de uso y de subagentes de un agente local.

Se ejecuta antes de cada herramienta (PreToolUse) y al terminar un subagente
(SubagentStop). Lee la configuración del agente en cada llamada, así que un
cambio hecho desde el panel aplica de inmediato.

- **Límites de uso**: si la cuenta superó el porcentaje semanal o de sesión
  fijado para este agente, bloquea la herramienta y le pide detenerse.
- **Subagentes**: bloquea abrirlos si no están permitidos o si ya hay el máximo
  abiertos a la vez. Los flujos multiagente (Workflow) no se pueden acotar, así
  que solo se permiten cuando no hay tope efectivo (máximo de 20).

Bloquea con código de salida 2; ante cualquier error propio, deja pasar.
"""
import json
import os
import sys
import time

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

ABRE_SUBAGENTE = {"Agent", "Task"}
CADUCA = 45 * 60   # un subagente que no avisó de su fin deja de contar a los 45 min


def main():
    agente = os.environ.get("DIXI_AGENTE_ID") or os.environ.get("DIXI_AGENTE_PROYECTO")
    if not agente:
        return 0
    import config
    from mensajes import t

    try:
        evento = json.load(sys.stdin)
    except Exception:
        evento = {}
    nombre = evento.get("hook_event_name", "")
    ruta = os.path.join(config.HOME_AG, "uso", f"{agente}.subagentes.json")

    def abiertos():
        try:
            marcas = json.load(open(ruta, encoding="utf-8"))
        except Exception:
            marcas = []
        return [m for m in marcas if isinstance(m, (int, float)) and time.time() - m < CADUCA]

    def guardar(marcas):
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as fh:
            json.dump(marcas, fh)

    if nombre == "SubagentStop":
        marcas = abiertos()
        guardar(marcas[1:])          # sale el más antiguo
        return 0
    if nombre == "SessionStart":
        guardar([])
        return 0
    if nombre != "PreToolUse":
        return 0

    motivo = config.limite_alcanzado(agente)
    if motivo:
        print(t("h_limite", motivo=motivo), file=sys.stderr)
        return 2

    herramienta = evento.get("tool_name", "")
    if herramienta in ABRE_SUBAGENTE or herramienta == "Workflow":
        sub = config.de_agente(agente)["subagentes"]
        if not sub["permitidos"]:
            print(t("h_sin_subagentes"), file=sys.stderr)
            return 2
        if herramienta == "Workflow":
            if sub["max"] < 20:
                print(t("h_workflow", max=sub["max"]), file=sys.stderr)
                return 2
            return 0
        marcas = abiertos()
        if len(marcas) >= sub["max"]:
            print(t("h_tope_subagentes", n=len(marcas), max=sub["max"]), file=sys.stderr)
            return 2
        guardar(marcas + [time.time()])
    return 0


try:
    codigo = main()
except Exception:
    codigo = 0
sys.exit(codigo)
