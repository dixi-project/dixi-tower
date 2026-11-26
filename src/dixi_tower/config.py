"""Configuración de la torre de agentes.

Dos niveles:
- **Global** (`~/.agentes/config.json`): valores con los que nace cada agente.
- **Por agente** (clave `config` de `~/.agentes/estado/<agente>.json`): copia que
  se toma al lanzarlo y que se puede cambiar después sin afectar a los demás.

Uso como programa:
  config.py global                          imprime la configuración global
  config.py valor <clave>                   imprime un valor global (p. ej. tope_revision)
  config.py agente <agente>                 imprime la de un agente
  config.py nueva [--motor M] [--autonomia A]   global + lo indicado, validada
"""
import json
import os
import sys

HOME_AG = os.environ.get("DIXI_AGENTES_HOME", os.path.expanduser("~/.agentes"))
MOTORES = ("claude", "codex")
AUTONOMIAS = ("supervisada", "equilibrada", "autonoma")
PREDETERMINADA = {
    "motor": "claude",
    "autonomia": "equilibrada",
    # Subagentes que el agente puede tener abiertos a la vez.
    "subagentes": {"permitidos": True, "max": 3},
    # Porcentajes de uso de la cuenta a partir de los cuales el agente deja de
    # trabajar. 0 = sin límite. «sesion» es la ventana de 5 horas.
    "limites": {"semana": 80, "sesion": 0},
    # Solo global. Con la integración de tareas (tasks/TASKS.md): no lanzar en un
    # proyecto que tenga más de este número de tareas en revisión. 0 = sin tope.
    "tope_revision": 0,
}


def _entero(valor, minimo, maximo, respaldo):
    try:
        return max(minimo, min(maximo, int(valor)))
    except (TypeError, ValueError):
        return respaldo


def normalizar(datos, base=None):
    """Devuelve una configuración completa y válida: `datos` sobre `base`."""
    base = base or PREDETERMINADA
    datos = datos if isinstance(datos, dict) else {}
    sub = datos.get("subagentes") if isinstance(datos.get("subagentes"), dict) else {}
    lim = datos.get("limites") if isinstance(datos.get("limites"), dict) else {}
    return {
        "motor": datos.get("motor") if datos.get("motor") in MOTORES else base["motor"],
        "autonomia": datos.get("autonomia") if datos.get("autonomia") in AUTONOMIAS else base["autonomia"],
        "subagentes": {
            "permitidos": bool(sub["permitidos"]) if "permitidos" in sub else base["subagentes"]["permitidos"],
            "max": _entero(sub.get("max"), 1, 20, base["subagentes"]["max"]),
        },
        "limites": {
            "semana": _entero(lim.get("semana"), 0, 100, base["limites"]["semana"]),
            "sesion": _entero(lim.get("sesion"), 0, 100, base["limites"]["sesion"]),
        },
        "tope_revision": _entero(datos.get("tope_revision"), 0, 99, base.get("tope_revision", 0)),
    }


def _leer(ruta):
    try:
        with open(ruta, encoding="utf-8") as fh:
            return json.load(fh)
    except Exception:
        return {}


def _escribir(ruta, datos):
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    tmp = ruta + ".tmp"
    with open(tmp, "w", encoding="utf-8") as fh:
        json.dump(datos, fh, ensure_ascii=False, indent=1)
    os.replace(tmp, ruta)


def ruta_global():
    return os.path.join(HOME_AG, "config.json")


def ruta_estado(agente):
    return os.path.join(HOME_AG, "estado", f"{agente}.json")


def global_():
    return normalizar(_leer(ruta_global()))


def guardar_global(datos):
    nueva = normalizar(datos, global_())
    _escribir(ruta_global(), nueva)
    return nueva


def de_agente(agente):
    """La del agente; si nació antes de existir la configuración, la global."""
    return normalizar(_leer(ruta_estado(agente)).get("config"), global_())


def guardar_agente(agente, datos):
    estado = _leer(ruta_estado(agente))
    if not estado:
        raise KeyError(agente)
    estado["config"] = normalizar(datos, de_agente(agente))
    _escribir(ruta_estado(agente), estado)
    return estado["config"]


def ruta_reglas_propias():
    """Reglas que el usuario añade a las de todo agente (archivo opcional)."""
    return os.path.join(HOME_AG, "reglas.md")


def uso(agente):
    """Último uso de la cuenta que reportó la sesión del agente (puede no existir)."""
    return _leer(os.path.join(HOME_AG, "uso", f"{agente}.json"))


def limite_alcanzado(agente):
    """Texto del límite superado, o '' si el agente puede seguir."""
    lim, u = de_agente(agente)["limites"], uso(agente)
    for clave, nombre in (("semana", "semanal"), ("sesion", "de sesión")):
        tope, valor = lim[clave], u.get(clave)
        if tope and isinstance(valor, (int, float)) and valor >= tope:
            return f"uso {nombre} en {valor:.0f}% (límite {tope}%)"
    return ""


if __name__ == "__main__":
    args = sys.argv[1:]
    if args[:1] == ["valor"] and len(args) == 2:
        print(global_().get(args[1], ""))
        sys.exit(0)
    if args[:1] == ["agente"] and len(args) == 2:
        salida = de_agente(args[1])
    elif args[:1] == ["nueva"]:
        cambios = {}
        for clave in ("motor", "autonomia"):
            if f"--{clave}" in args:
                valor = args[args.index(f"--{clave}") + 1]
                permitidos = MOTORES if clave == "motor" else AUTONOMIAS
                if valor and valor not in permitidos:
                    sys.exit(f"Valor inválido para {clave}: {valor} (opciones: {', '.join(permitidos)})")
                if valor:
                    cambios[clave] = valor
        salida = normalizar({**global_(), **cambios}, global_())
    else:
        salida = global_()
    print(json.dumps(salida, ensure_ascii=False))
