"""Mensajes del lanzador y sus programas auxiliares, en español e inglés.

El idioma sale de DIXI_TOWER_LANG o, si no está, del idioma del sistema
(LC_ALL, LC_MESSAGES, LANG): español si empieza por «es», inglés en otro caso.

Como programa, para los guiones de bash:
  mensajes.py <clave> [nombre=valor ...]
"""
import os
import sys

CATALOGO = {
    # Lanzador
    "opcion_desconocida": ("Opción desconocida: {op}", "Unknown option: {op}"),
    "proyecto_desconocido": ("Proyecto desconocido: {p} (registrados: {lista})", "Unknown project: {p} (registered: {lista})"),
    "sin_actualizar": ("Aviso: no pude actualizar {base} desde origin; uso la copia local.",
                       "Warning: could not update {base} from origin; using the local copy."),
    "revision_sin_tope": ("En revisión [r]: {n} (sin tope)", "In review [r]: {n} (no limit)"),
    "revision_tope": ("En revisión [r]: {n} (tope {tope})", "In review [r]: {n} (limit {tope})"),
    "tope_superado": ("{p} tiene {n} tareas en revisión y tu tope es {tope}. Para lanzarlo de todos modos, marca «Lanzar aunque el proyecto supere su tope» (o usa --forzar). El tope se cambia en Configuración; 0 lo desactiva.",
                      "{p} has {n} tasks in review and your limit is {tope}. To launch anyway, tick “Launch even if the project is over its in-review limit” (or use --force). Change the limit in Settings; 0 turns it off."),
    "falta_instruccion": ("Sin tarea del tablero hace falta una instrucción.", "Without a board task, an instruction is required."),
    "tarea_ocupada": ("Esa tarea ya tiene un agente vivo en {p}; elige otra tarea o detén ese agente.",
                      "That task already has a running agent in {p}; pick another task or stop that agent."),
    "lanzado": ("Agente lanzado: {ag} · {id} · {rama}", "Agent launched: {ag} · {id} · {rama}"),
    "worktree": ("Worktree: {wt}", "Worktree: {wt}"),
    "sin_ventana": ("No hay ventana viva para {ag}", "No running window for {ag}"),
    "detenido": ("Detenido: {ag} (el worktree y la rama se conservan)", "Stopped: {ag} (worktree and branch are kept)"),
    "desconocido": ("No conozco al agente {ag}.", "Unknown agent: {ag}."),
    "ya_encendido": ("El agente {ag} ya está encendido.", "Agent {ag} is already running."),
    "reanudado": ("Agente reanudado: {ag}", "Agent resumed: {ag}"),
    "encendido_no_eliminar": ("El agente {ag} está encendido: detenlo antes de eliminarlo.", "Agent {ag} is running: stop it before deleting it."),
    "worktree_fuera": ("El worktree no está dentro de {dir}; no lo borro: {wt}", "The worktree is not inside {dir}; not deleting it: {wt}"),
    "sin_commit": ("No lo elimino: tiene {n} archivos sin commit en {wt}. Haz commit o descártalos primero.",
                   "Not deleting it: {n} uncommitted files in {wt}. Commit or discard them first."),
    "git_no_quita": ("git no pudo quitar el worktree {wt}.", "git could not remove the worktree {wt}."),
    "eliminado": ("Eliminado: {ag}. La rama {rama} se conserva en el repositorio.", "Deleted: {ag}. Branch {rama} is kept in the repository."),
    "attach": ("tmux attach -t {s}    (Ctrl-b n: siguiente ventana · Ctrl-b d: salir sin detenerlos)",
               "tmux attach -t {s}    (Ctrl-b n: next window · Ctrl-b d: leave without stopping them)"),
    "panel_corriendo": ("El panel ya está corriendo.", "The panel is already running."),
    "panel_url": ("Panel: {url}", "Panel: {url}"),
    "servicio_solo_macos": ("El servicio automático solo existe en macOS. En este sistema usa: dixi-tower panel",
                            "The always-on service only exists on macOS. On this system use: dixi-tower panel"),
    "servicio_instalado": ("Servicio instalado. Panel: {url}", "Service installed. Panel: {url}"),
    "servicio_sin_respuesta": ("El servicio se instaló pero el panel no responde; revisa {log}",
                               "The service was installed but the panel does not respond; check {log}"),
    "servicio_quitado": ("Servicio quitado. Para levantar el panel a mano: dixi-tower panel",
                         "Service removed. To start the panel by hand: dixi-tower panel"),
    "panel_reiniciado": ("Panel reiniciado: {url}", "Panel restarted: {url}"),
    "panel_no_responde": ("El panel no responde; revisa {log}", "The panel does not respond; check {log}"),
    "servicio_si": ("Servicio: instalado ({plist})", "Service: installed ({plist})"),
    "servicio_no": ("Servicio: no instalado", "Service: not installed"),
    "panel_si": ("Panel: responde en {url}", "Panel: responding at {url}"),
    "panel_no": ("Panel: no responde", "Panel: not responding"),
    "uso_servicio": ("Uso: dixi-tower servicio instalar|quitar|reiniciar|estado",
                     "Usage: dixi-tower service install|uninstall|restart|status"),
    # Programas auxiliares
    "valor_invalido": ("Valor inválido para {clave}: {valor} (opciones: {ops})", "Invalid value for {clave}: {valor} (options: {ops})"),
    "worktree_no_existe": ("El worktree de este agente ya no existe: {wt}", "This agent's worktree no longer exists: {wt}"),
    "motor_no_definido": ("El motor «{motor}» ya no está definido en la configuración.", "The engine “{motor}” is no longer defined in the settings."),
    "continua": ("Continúa con el encargo anterior.", "Continue with the previous task."),
    "no_es_repo": ("No es un repositorio git dentro de {raiz}: {nombre}", "Not a git repository inside {raiz}: {nombre}"),
    "sin_rama_base": ("No pude determinar la rama base de {nombre}", "Could not determine the base branch of {nombre}"),
    "registrado": ("Registrado {nombre} (rama base {base})", "Registered {nombre} (base branch {base})"),
    "tarea_no_encontrada": ("No hay tarea con st:{id} en la rama base", "No task with st:{id} on the base branch"),
    "candidatas": ("({n} candidatas en backlog con id; se muestran hasta 15)", "({n} backlog candidates with an id; showing up to 15)"),
    # Tabla de estado
    "sin_agentes": ("Sin agentes lanzados todavía.", "No agents launched yet."),
    "e_lanzando": ("lanzando", "launching"),
    "e_trabajando": ("trabajando", "working"),
    "e_en_pausa": ("EN PAUSA (terminó turno)", "PAUSED (turn finished)"),
    "e_te_necesita": ("TE NECESITA", "NEEDS YOU"),
    "e_cerrado": ("cerrado", "closed"),
    "ventana_cerrada": ("la ventana ya no existe", "the window no longer exists"),
    "hace": ("hace {t}", "{t} ago"),
    "instruccion_libre": ("instrucción libre", "free-form instruction"),
    "fila_tarea": ("    tarea : {tarea}  {titulo}", "    task  : {tarea}  {titulo}"),
    "fila_rama": ("    rama  : {rama}  ·  {commits} commits  ·  {sucios} archivos sin commit",
                  "    branch: {rama}  ·  {commits} commits  ·  {sucios} uncommitted files"),
    "fila_ultimo": ("    último: {detalle}", "    latest: {detalle}"),
    # Respuestas del panel
    "p_proyecto_invalido": ("Proyecto inválido.", "Invalid project."),
    "p_tarea_invalida": ("Tarea inválida.", "Invalid task."),
    "p_instruccion_invalida": ("Instrucción inválida.", "Invalid instruction."),
    "p_lanzar_lento": ("El lanzamiento tardó demasiado; revisa el estado en la lista.", "Launching took too long; check the agent list."),
    "p_lanzar_fallo": ("No se pudo lanzar el agente.", "The agent could not be launched."),
    "p_agente_desconocido": ("Agente desconocido.", "Unknown agent."),
    "p_lento": ("La operación tardó demasiado.", "The operation took too long."),
    "p_fallo": ("No se pudo completar la operación.", "The operation could not be completed."),
    "p_config_invalida": ("Configuración inválida.", "Invalid settings."),
    "p_fuera_de_casa": ("Solo se pueden explorar carpetas dentro de tu carpeta personal.", "Only folders inside your home folder can be browsed."),
    "p_sin_lectura": ("No se puede leer esa carpeta.", "That folder cannot be read."),
    "p_sin_ventana": ("Agente desconocido o sin ventana.", "Unknown agent or no running window."),
    "p_tecla": ("Tecla no permitida.", "Key not allowed."),
    "p_peticion": ("Petición inválida.", "Invalid request."),
}


def idioma(forzado=None):
    if forzado in ("es", "en"):
        return forzado
    valor = (os.environ.get("DIXI_TOWER_LANG") or os.environ.get("LC_ALL")
             or os.environ.get("LC_MESSAGES") or os.environ.get("LANG") or "")
    return "es" if valor.lower().startswith("es") else "en"


def t(_clave, _idioma=None, /, **valores):
    """Mensaje `_clave` en el idioma del usuario (o en `_idioma`, si se indica)."""
    es, en = CATALOGO[_clave]
    texto = es if idioma(_idioma) == "es" else en
    try:
        return texto.format(**valores)
    except (KeyError, IndexError):
        return texto


if __name__ == "__main__":
    pares = dict(a.split("=", 1) for a in sys.argv[2:] if "=" in a)
    print(t(sys.argv[1], **pares))
