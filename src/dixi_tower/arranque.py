"""Escribe el script que abre (o retoma) la sesión de un agente, según su motor
y su nivel de autonomía, y deja listo su estado.

  arranque.py <agente> inicial <archivo-prompt>
  arranque.py <agente> reanudar

Imprime la ruta del script generado. El motor y la autonomía salen de la
configuración del agente (`config.py`), así que un cambio hecho desde el panel
aplica la próxima vez que se enciende.
"""
import json
import os
import re
import shlex
import sys
import time

import config
from mensajes import idioma, t

DIR = os.path.dirname(os.path.abspath(__file__))
HOME_AG = config.HOME_AG
REGISTRO = os.environ.get("DIXI_AGENTES_REGISTRO", os.path.join(HOME_AG, "proyectos.json"))

# Nivel de autonomía → cómo se le pide a cada motor.
#   supervisada: pregunta antes de editar y de ejecutar lo que no esté permitido.
#   equilibrada: edita sin preguntar; pregunta por comandos fuera de la lista.
#   autonoma:    decide solo dentro de sus barreras; pregunta lo mínimo.
CLAUDE_PERMISOS = {"supervisada": "manual", "equilibrada": "acceptEdits", "autonoma": "auto"}
CODEX_OPCIONES = {
    "supervisada": ["--sandbox", "read-only", "--ask-for-approval", "on-request"],
    "equilibrada": ["--sandbox", "workspace-write", "--ask-for-approval", "on-request"],
    # El sandbox de Codex protege .git: un commit siempre necesita aprobación.
    # Con «never» fallaría; --approve-for-me (workspace-write + on-request) manda
    # esas aprobaciones a un revisor automático en vez de a la persona.
    "autonoma": ["--approve-for-me"],
}


def opciones_codex(agente, autonomia, subagentes, reglas):
    """Flags de Codex para un agente. Todo va por línea de comandos (`-c`): no se
    toca ~/.codex/config.toml ni el repositorio del proyecto."""
    toml = lambda v: json.dumps(v, ensure_ascii=False)   # una cadena o lista JSON es TOML válido
    ops = list(CODEX_OPCIONES[autonomia]) + [
        "--no-alt-screen",                                # conserva el historial para el panel
        # Un aviso de «actualización disponible» bloquearía la sesión hasta que alguien responda.
        "-c", "check_for_update_on_startup=false",
        # En workspace-write no hay red salvo que se pida; sin ella no publica su rama ni abre el PR.
        "-c", "sandbox_workspace_write.network_access=true",
        "-c", "notify=" + toml(["python3", os.path.join(DIR, "hooks", "codex-notify.py"), agente, HOME_AG]),
        "-c", "developer_instructions=" + toml(open(reglas, encoding="utf-8").read()),
        "-c", 'tui.status_line=["model","run-state","five-hour-limit","weekly-limit","context-remaining"]',
    ]
    if subagentes["permitidos"]:
        ops += ["-c", f"agents.max_concurrent_threads_per_session={subagentes['max']}"]
    else:
        ops += ["--disable", "multi_agent"]
    return " ".join(q(o) for o in ops)


q = shlex.quote


def main():
    agente, modo = sys.argv[1], sys.argv[2]
    ruta_estado = config.ruta_estado(agente)
    try:
        estado = json.load(open(ruta_estado, encoding="utf-8"))
    except Exception:
        sys.exit(t("desconocido", ag=agente))
    wt = estado.get("worktree") or ""
    if not os.path.isdir(wt):
        sys.exit(t("worktree_no_existe", wt=wt))
    conf = config.de_agente(agente)
    motor, autonomia = conf["motor"], conf["autonomia"]
    proyecto = estado.get("proyecto") or agente
    base = estado.get("base")
    if not base:
        try:
            base = json.load(open(REGISTRO, encoding="utf-8")).get(proyecto, {}).get("base")
        except Exception:
            base = None
    # Reglas del agente: las de Dixi Tower más las que el usuario haya añadido.
    nombre = "worker-prompt.md" if idioma() == "es" else "worker-prompt.en.md"
    texto = open(os.path.join(DIR, nombre), encoding="utf-8").read()
    try:
        propias = open(config.ruta_reglas_propias(), encoding="utf-8").read().strip()
    except OSError:
        propias = ""
    if propias:
        texto = texto.rstrip() + "\n\n" + propias + "\n"
    reglas = os.path.join(HOME_AG, "run", f"{agente}.reglas.md")
    os.makedirs(os.path.dirname(reglas), exist_ok=True)
    with open(reglas, "w", encoding="utf-8") as fh:
        fh.write(texto)

    entorno = {
        "DIXI_AGENTE": "1",
        "DIXI_AGENTE_ID": agente,
        "DIXI_AGENTE_PROYECTO": proyecto,
        "DIXI_AGENTE_MOTOR": motor,
        "DIXI_AGENTE_TAREA": estado.get("tarea") or "",
        "DIXI_AGENTE_TITULO": estado.get("titulo") or "",
        "DIXI_AGENTE_RAMA": estado.get("rama") or "",
        "DIXI_AGENTE_BASE": base or "main",
        "DIXI_AGENTES_DIR": DIR,
        "DIXI_AGENTES_HOME": HOME_AG,
        # Los hooks hablan al agente y avisan en el idioma con el que se lanzó.
        "DIXI_TOWER_LANG": idioma(),
    }
    lineas = [
        "#!/usr/bin/env bash",
        f"cd {q(wt)} || exit 1",
        # Garantiza el login de la suscripción: sin llaves de API ni proveedores en la nube.
        "unset ANTHROPIC_API_KEY ANTHROPIC_AUTH_TOKEN CLAUDE_CODE_USE_BEDROCK CLAUDE_CODE_USE_VERTEX OPENAI_API_KEY"
        if motor in config.MOTORES else ": # motor propio: su entorno no se toca",
        "export " + " ".join(f"{k}={q(v)}" for k, v in entorno.items()),
    ]

    sesion = estado.get("session_id") or ""
    sesion_ok = bool(re.fullmatch(r"[0-9a-fA-F-]{8,64}", sesion)) and estado.get("motor_sesion", "claude") == motor

    if motor == "claude":
        orden = (f"exec claude --name {q('agente-' + agente)} --settings {q(os.path.join(DIR, 'worker-settings.json'))} "
                 f"--permission-mode {CLAUDE_PERMISOS[autonomia]} --append-system-prompt \"$(cat {q(reglas)})\"")
        if modo == "inicial":
            orden += f" \"$(cat {q(sys.argv[3])})\""
        else:
            orden += f" --resume {sesion}" if sesion_ok else " --continue"
    elif motor not in config.MOTORES:
        # Motor definido por el usuario: su propio comando, tal cual lo escribió.
        propio = config.motores_propios().get(motor)
        if not propio:
            sys.exit(t("motor_no_definido", motor=motor))
        if modo == "inicial":
            plantilla, encargo = propio["comando"], f'"$(cat {q(sys.argv[3])})"'
        else:
            plantilla, encargo = propio.get("reanudar") or propio["comando"], q(t("continua"))
        orden = "exec " + plantilla.replace("{instruccion}", encargo).replace("{reglas}", f'"$(cat {q(reglas)})"')
    else:
        opciones = opciones_codex(agente, autonomia, conf["subagentes"], reglas)
        if modo == "inicial":
            orden = f"exec codex {opciones} \"$(cat {q(sys.argv[3])})\""
        else:
            orden = f"exec codex resume {opciones} " + (sesion if sesion_ok else "--last")
    lineas.append(orden)

    sufijo = "" if modo == "inicial" else ".reanudar"
    ruta = os.path.join(HOME_AG, "run", f"{agente}{sufijo}.sh")
    os.makedirs(os.path.dirname(ruta), exist_ok=True)
    with open(ruta, "w", encoding="utf-8") as fh:
        fh.write("\n".join(lineas) + "\n")
    os.chmod(ruta, 0o755)

    estado.update(estado="lanzando", detalle="", actualizado=time.time(), config=conf, motor_sesion=motor)
    with open(ruta_estado + ".tmp", "w", encoding="utf-8") as fh:
        json.dump(estado, fh, ensure_ascii=False, indent=1)
    os.replace(ruta_estado + ".tmp", ruta_estado)
    print(ruta)


main()
