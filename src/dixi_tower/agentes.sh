#!/usr/bin/env bash
# Dixi Tower — torre de control local para agentes de código.
# Lanza sesiones interactivas de tu agente de código dentro de tmux, cada una en su
# propio worktree y rama. Un proyecto puede tener varios
# agentes a la vez: el primero se llama como el proyecto y los siguientes
# <proyecto>@2, <proyecto>@3… Ese nombre es el <agente> de ver, decir y detener.
#
#   dixi-tower siguiente <proyecto>            candidatas del backlog por prioridad
#   dixi-tower lanzar <proyecto> <st-id> [--forzar] [--instruccion <archivo>] [--motor claude|codex] [--autonomia supervisada|equilibrada|autonoma]
#   dixi-tower lanzar <proyecto> libre --instruccion <archivo>   sin tarea del tablero
#   dixi-tower estado                          tabla de todos los agentes
#   dixi-tower ver <agente> [líneas]           pantalla actual del agente
#   dixi-tower decir <agente> "<mensaje>"      escribirle al agente
#   dixi-tower detener <agente>                cierra su ventana (conserva el worktree)
#   dixi-tower reanudar <agente>               vuelve a encender un agente cerrado y retoma su conversación
#   dixi-tower eliminar <agente>               quita un agente cerrado y su worktree (la rama se conserva)
#   dixi-tower abrir                           cómo entrar a verlos en vivo
#   dixi-tower panel [puerto]                  panel web local (http://localhost:4310/)
#   dixi-tower servicio instalar|quitar|reiniciar|estado   panel siempre encendido (launchd)
#   dixi-tower doctor                          revisa requisitos e instalación
set -euo pipefail

DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
# Carpeta de datos: ~/.dixi-tower. Las instalaciones anteriores al nombre Dixi Tower
# usaban ~/.agentes: si solo existe esa, se sigue usando.
if [ -n "${DIXI_TOWER_HOME:-}" ]; then HOME_AG="$DIXI_TOWER_HOME"
elif [ -n "${DIXI_AGENTES_HOME:-}" ]; then HOME_AG="$DIXI_AGENTES_HOME"
elif [ -d "$HOME/.agentes" ] && [ ! -d "$HOME/.dixi-tower" ]; then HOME_AG="$HOME/.agentes"
else HOME_AG="$HOME/.dixi-tower"; fi
export DIXI_AGENTES_HOME="$HOME_AG"      # para que los programas auxiliares usen la misma
REG="${DIXI_AGENTES_REGISTRO:-$HOME_AG/proyectos.json}"
PROYECTOS_DIR="${DIXI_TOWER_PROJECTS:-${DIXI_PROYECTOS_DIR:-$HOME/projects}}"
export DIXI_PROYECTOS_DIR="$PROYECTOS_DIR"
# Sesión tmux: «dixi-tower». Si aún vive una sesión «agentes» de antes del cambio de
# nombre, se sigue usando para no perder de vista a los agentes ya encendidos.
if [ -n "${DIXI_TOWER_SESSION:-}" ]; then SESION="$DIXI_TOWER_SESSION"
elif tmux has-session -t '=agentes' 2>/dev/null && ! tmux has-session -t '=dixi-tower' 2>/dev/null; then SESION="agentes"
else SESION="dixi-tower"; fi
PUERTO="${DIXI_TOWER_PORT:-${DIXI_AGENTES_PUERTO:-4310}}"
ETIQUETA="com.dixi-project.dixi-tower"
ETIQUETA_ANTERIOR="com.dixi.torre-agentes"
PLIST="$HOME/Library/LaunchAgents/$ETIQUETA.plist"

panel_responde() { curl -s -o /dev/null -m 2 "http://127.0.0.1:${1:-$PUERTO}/es/lista"; }

mkdir -p "$HOME_AG/estado" "$HOME_AG/run" "$HOME_AG/worktrees"

campo() { # campo <proyecto> <clave>
  python3 - "$REG" "$1" "$2" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
p = d.get(sys.argv[2])
if p is None:
    sys.exit(f"Proyecto desconocido: {sys.argv[2]} (registrados: {', '.join(d)})")
print(p.get(sys.argv[3], ""))
PY
}

# Da de alta el proyecto si es un repo de PROYECTOS_DIR aún no registrado.
registrar() { python3 "$DIR/registro.py" "$REG" "$PROYECTOS_DIR" "$1"; }

# origin/<base> si existe; si no, la rama local (repos sin remoto).
ref_base() {
  if git -C "$1" show-ref --verify --quiet "refs/remotes/origin/$2"; then echo "origin/$2"; else echo "$2"; fi
}

traer() { # git fetch de la base, solo si hay remoto; sin red no aborta
  if git -C "$1" remote get-url origin >/dev/null 2>&1; then
    git -C "$1" fetch --quiet origin "$2" || echo "Aviso: no pude actualizar $2 desde origin; uso la copia local." >&2
  fi
}

ventana_viva() { tmux list-windows -t "$SESION" -F '#W' 2>/dev/null | grep -qxF -- "$1"; }

# Lee el TASKS.md de la rama base remota (la fuente de verdad) y lo analiza.
#   tareas <repo> <base> lista            → candidatas [ ] ordenadas por prioridad
#   tareas <repo> <base> revision         → cuántas hay en [r]
#   tareas <repo> <base> una <st-id>      → "título<TAB>slug<TAB>línea"
tareas() {
  local repo="$1" base="$2"; shift 2
  { git -C "$repo" show "$(ref_base "$repo" "$base"):tasks/TASKS.md" 2>/dev/null || true; } | python3 "$DIR/tareas.py" "$@"
}

cmd_siguiente() {
  local p="$1" repo base
  registrar "$p"
  repo="$(campo "$p" repo)"; base="$(campo "$p" base)"
  traer "$repo" "$base"
  local tope; tope="$(python3 "$DIR/config.py" valor tope_revision)"
  if [ "$tope" = "0" ]; then echo "En revisión [r]: $(tareas "$repo" "$base" revision) (sin tope)"
  else echo "En revisión [r]: $(tareas "$repo" "$base" revision) (tope $tope)"; fi
  tareas "$repo" "$base" lista
}

cmd_lanzar() {
  local p="$1" id="$2"; shift 2
  local forzar="" instr="" motor="" autonomia=""
  while [ $# -gt 0 ]; do
    case "$1" in
      --forzar|--force) forzar=1 ;;
      --motor|--engine) motor="${2:?falta el motor}"; shift ;;
      --autonomia|--autonomy) autonomia="${2:?falta el nivel (supervisada|equilibrada|autonoma)}"; shift ;;
      --instruccion|--instruction) instr="${2:?falta el archivo de la instrucción}"; shift ;;
      "") ;;
      *) echo "Opción desconocida: $1" >&2; exit 1 ;;
    esac
    shift
  done

  registrar "$p"
  local repo base comando max
  repo="$(campo "$p" repo)"; base="$(campo "$p" base)"
  comando="$(campo "$p" comando)"; max="$(python3 "$DIR/config.py" valor tope_revision)"

  # Nombre del agente: el del proyecto, o <proyecto>@N si ya hay otros vivos.
  local ag="$p" n=2
  while ventana_viva "$ag"; do ag="$p@$n"; n=$((n+1)); done

  traer "$repo" "$base"
  local ref; ref="$(ref_base "$repo" "$base")"

  local en_rev; en_rev="$(tareas "$repo" "$base" revision)"
  if [ "$max" != "0" ] && [ "$en_rev" -gt "$max" ] && [ -z "$forzar" ]; then
    echo "$p tiene $en_rev tareas en revisión y tu tope es $max. Para lanzarlo de todos modos, marca «Lanzar aunque el proyecto supere su tope» (o usa --forzar). El tope se cambia en Configuración; 0 lo desactiva." >&2
    exit 1
  fi

  local fila titulo slug linea="" rama clave marca
  marca="$(date +%m%d%H%M)"
  # Dos encargos libres en el mismo minuto no deben compartir carpeta ni rama.
  local n_libre=2 marca_base="$marca"
  while [ -d "$HOME_AG/worktrees/$p/libre-$marca" ]; do marca="$marca_base-$n_libre"; n_libre=$((n_libre+1)); done
  [ "$id" = "free" ] && id="libre"
  if [ "$id" = "libre" ]; then
    if [ -z "$instr" ] || [ ! -s "$instr" ]; then
      echo "Sin tarea del tablero hace falta una instrucción." >&2; exit 1
    fi
    fila="$(python3 "$DIR/tareas.py" slug < "$instr")"
    titulo="$(printf '%s' "$fila" | cut -f1)"
    slug="$(printf '%s' "$fila" | cut -f2)"
    clave="libre-$marca"
    rama="agente/$slug-$marca"   # no es st/: no mueve ninguna tarjeta del tablero
  else
    fila="$(tareas "$repo" "$base" una "$id")"
    titulo="$(printf '%s' "$fila" | cut -f1)"
    slug="$(printf '%s' "$fila" | cut -f2)"
    linea="$(printf '%s' "$fila" | cut -f3-)"
    clave="$id"
    rama="st/$id-$slug"
  fi

  local wt="$HOME_AG/worktrees/$p/$clave"
  # Dos agentes nunca comparten worktree: la misma tarea no se lanza dos veces a la vez.
  if tmux list-windows -t "$SESION" -F '#W' 2>/dev/null | python3 "$DIR/ocupado.py" "$HOME_AG/estado" "$wt"; then
    echo "Esa tarea ya tiene un agente vivo en $p; elige otra tarea o detén ese agente." >&2; exit 1
  fi
  if [ ! -d "$wt" ]; then
    mkdir -p "$(dirname "$wt")"
    if git -C "$repo" show-ref --verify --quiet "refs/heads/$rama"; then
      git -C "$repo" worktree add "$wt" "$rama"
    else
      git -C "$repo" worktree add -b "$rama" "$wt" "$ref"
    fi
  fi

  local prompt="$HOME_AG/run/$ag.prompt.txt"
  {
    [ -n "$comando" ] && printf '%s ' "$comando"
    if [ "$id" = "libre" ]; then
      cat "$instr"; printf '\n\n'
    else
      printf 'Tarea st:%s — %s\n\n' "$id" "$titulo"
      printf 'Su registro en tasks/TASKS.md:\n%s\n\n' "$linea"
      if [ -n "$instr" ] && [ -s "$instr" ]; then
        printf 'Indicaciones adicionales:\n'; cat "$instr"; printf '\n\n'
      fi
    fi
    printf 'Ya estás en la rama %s (worktree propio, base %s). ' "$rama" "$ref"
    printf 'Si el registro apunta a una ficha, léela antes de empezar.\n'
  } > "$prompt"

  # Configuración con la que nace: la global más lo que se pidió en este lanzamiento.
  local conf
  conf="$(python3 "$DIR/config.py" nueva --motor "$motor" --autonomia "$autonomia")" || exit 1
  python3 - "$HOME_AG/estado/$ag.json" "$p" "$id" "$titulo" "$rama" "$wt" "$ag" "$base" "$conf" <<'PY2'
import json, sys, time
f, p, i, t, r, w, a, b, c = sys.argv[1:]
json.dump({"agente": a, "proyecto": p, "tarea": i, "titulo": t, "rama": r, "worktree": w, "base": b,
           "config": json.loads(c), "estado": "lanzando", "detalle": "", "actualizado": time.time()},
          open(f, "w"), ensure_ascii=False, indent=1)
PY2
  local run
  run="$(python3 "$DIR/arranque.py" "$ag" inicial "$prompt")" || exit 1

  if tmux has-session -t "$SESION" 2>/dev/null; then
    tmux new-window -d -t "$SESION" -n "$ag" "$run"
  else
    tmux new-session -d -s "$SESION" -n "$ag" "$run"
  fi
  echo "AGENTE=$ag"
  echo "Agente lanzado: $ag · $id · $rama"
  echo "Worktree: $wt"
}

cmd_estado() { python3 "$DIR/estado.py" "$HOME_AG" "$REG" "$SESION"; }

cmd_ver() {
  ventana_viva "$1" || { echo "No hay ventana viva para $1" >&2; exit 1; }
  tmux capture-pane -p -t "$SESION:$1" -S "-${2:-40}"
}

cmd_decir() {
  ventana_viva "$1" || { echo "No hay ventana viva para $1" >&2; exit 1; }
  tmux send-keys -t "$SESION:$1" -l "$2"
  tmux send-keys -t "$SESION:$1" Enter
}

cmd_detener() {
  ventana_viva "$1" && tmux kill-window -t "$SESION:$1"
  python3 - "$HOME_AG/estado/$1.json" <<'PY'
import json, sys, time, os
f = sys.argv[1]
if os.path.exists(f):
    d = json.load(open(f))
    d.update(estado="cerrado", detalle="detenido por la torre", actualizado=time.time())
    json.dump(d, open(f, "w"), ensure_ascii=False, indent=1)
PY
  echo "Detenido: $1 (el worktree y la rama se conservan)"
}

cmd_reanudar() {
  local ag="$1"
  [ -f "$HOME_AG/estado/$ag.json" ] || { echo "No conozco al agente $ag." >&2; exit 1; }
  if ventana_viva "$ag"; then echo "El agente $ag ya está encendido." >&2; exit 1; fi
  # Mismo worktree y reglas; retoma la conversación con el motor y la autonomía
  # que tenga configurados ahora.
  local nuevo
  nuevo="$(python3 "$DIR/arranque.py" "$ag" reanudar)" || exit 1
  if tmux has-session -t "$SESION" 2>/dev/null; then
    tmux new-window -d -t "$SESION" -n "$ag" "$nuevo"
  else
    tmux new-session -d -s "$SESION" -n "$ag" "$nuevo"
  fi
  echo "Agente reanudado: $ag"
}

cmd_eliminar() {
  local ag="$1" est="$HOME_AG/estado/$1.json"
  [ -f "$est" ] || { echo "No conozco al agente $ag." >&2; exit 1; }
  if ventana_viva "$ag"; then echo "El agente $ag está encendido: detenlo antes de eliminarlo." >&2; exit 1; fi
  local wt rama
  wt="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("worktree") or "")' "$est")"
  rama="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("rama") or "")' "$est")"
  # Solo se borra un worktree que esté dentro de la carpeta de la torre.
  if [ -n "$wt" ] && [ -d "$wt" ]; then
    case "$wt" in
      "$HOME_AG/worktrees/"*) ;;
      *) echo "El worktree no está dentro de $HOME_AG/worktrees; no lo borro: $wt" >&2; exit 1 ;;
    esac
    local sucios
    sucios="$(git -C "$wt" status --porcelain | wc -l | tr -d ' ')"
    if [ "$sucios" != "0" ]; then
      echo "No lo elimino: tiene $sucios archivos sin commit en $wt. Haz commit o descártalos primero." >&2; exit 1
    fi
    # Sin --force: git se niega si queda algo sin guardar. La rama no se borra,
    # así que los commits del agente siguen en el repositorio.
    git -C "$wt" worktree remove "$wt" || { echo "git no pudo quitar el worktree $wt." >&2; exit 1; }
  fi
  rm -f "$est" "$HOME_AG/run/$ag.sh" "$HOME_AG/run/$ag.prompt.txt" "$HOME_AG/run/$ag.reanudar.sh"
  echo "Eliminado: $ag. La rama ${rama:-del agente} se conserva en el repositorio."
}

case "${1:-}" in
  siguiente|next) cmd_siguiente "${2:?proyecto}" ;;
  lanzar|launch) cmd_lanzar "${2:?proyecto}" "${3:?st-id o libre}" "${@:4}" ;;
  estado|status) cmd_estado ;;
  ver|show) cmd_ver "${2:?agente}" "${3:-}" ;;
  decir|say) cmd_decir "${2:?agente}" "${3:?mensaje}" ;;
  detener|stop) cmd_detener "${2:?agente}" ;;
  reanudar|resume) cmd_reanudar "${2:?agente}" ;;
  eliminar|delete) cmd_eliminar "${2:?agente}" ;;
  doctor)    python3 "$DIR/doctor.py" "$PUERTO" "$PLIST" ;;
  abrir|attach) echo "tmux attach -t $SESION    (Ctrl-b n: siguiente ventana · Ctrl-b d: salir sin detenerlos)" ;;
  panel)
    puerto="${2:-$PUERTO}"
    if panel_responde "$puerto"; then
      echo "El panel ya está corriendo."
    elif tmux has-session -t "$SESION" 2>/dev/null; then
      tmux new-window -d -t "$SESION" -n panel "python3 '$DIR/panel.py' $puerto"
    else
      tmux new-session -d -s "$SESION" -n panel "python3 '$DIR/panel.py' $puerto"
    fi
    echo "Panel: http://localhost:$puerto/"
    ;;
  servicio|service)
    if [ "$(uname)" != "Darwin" ]; then
      echo "El servicio automático solo existe en macOS. En este sistema usa: dixi-tower panel" >&2; exit 1
    fi
    dominio="gui/$(id -u)"
    case "${2:-estado}" in
      instalar|install)
        # El servicio sustituye a la ventana tmux del panel: arranca al iniciar sesión
        # y launchd lo relanza si se cae.
        if ventana_viva panel; then tmux kill-window -t "$SESION:panel"; fi
        mkdir -p "$(dirname "$PLIST")"
        python3 - "$PLIST" "$ETIQUETA" "$(command -v python3)" "$DIR" "$PUERTO" "$HOME_AG" "$PATH" <<'PYS'
import plistlib, sys
ruta, etiqueta, python, carpeta, puerto, home_ag, path = sys.argv[1:]
with open(ruta, "wb") as fh:
    plistlib.dump({
        "Label": etiqueta,
        "ProgramArguments": [python, f"{carpeta}/panel.py", puerto],
        "WorkingDirectory": carpeta,
        "RunAtLoad": True,
        "KeepAlive": True,
        "ThrottleInterval": 5,
        # launchd arranca con un PATH mínimo: se fija el de esta sesión para que
        # el panel y los agentes que lance encuentren tmux, git, gh y claude.
        "EnvironmentVariables": {"PATH": path, "DIXI_AGENTES_HOME": home_ag, "DIXI_AGENTES_PUERTO": puerto},
        "StandardOutPath": f"{home_ag}/panel.log",
        "StandardErrorPath": f"{home_ag}/panel.log",
    }, fh)
PYS
        launchctl bootout "$dominio/$ETIQUETA" 2>/dev/null || true
        # Instalaciones hechas antes de que el proyecto se llamara Dixi Tower.
        launchctl bootout "$dominio/$ETIQUETA_ANTERIOR" 2>/dev/null || true
        rm -f "$HOME/Library/LaunchAgents/$ETIQUETA_ANTERIOR.plist"
        launchctl bootstrap "$dominio" "$PLIST"
        sleep 2
        if panel_responde; then echo "Servicio instalado. Panel: http://localhost:$PUERTO/"
        else echo "El servicio se instaló pero el panel no responde; revisa $HOME_AG/panel.log" >&2; exit 1; fi
        ;;
      quitar|uninstall)
        launchctl bootout "$dominio/$ETIQUETA" 2>/dev/null || true
        rm -f "$PLIST"
        echo "Servicio quitado. Para levantar el panel a mano: dixi-tower panel"
        ;;
      reiniciar|restart)
        launchctl kickstart -k "$dominio/$ETIQUETA" && sleep 2
        if panel_responde; then echo "Panel reiniciado: http://localhost:$PUERTO/"; else echo "El panel no responde; revisa $HOME_AG/panel.log" >&2; exit 1; fi
        ;;
      estado|status)
        if [ -f "$PLIST" ]; then echo "Servicio: instalado ($PLIST)"; else echo "Servicio: no instalado"; fi
        if panel_responde; then echo "Panel: responde en http://localhost:$PUERTO/"; else echo "Panel: no responde"; fi
        ;;
      *) echo "Uso: dixi-tower servicio instalar|quitar|reiniciar|estado" >&2; exit 1 ;;
    esac
    ;;
  *)
    case "${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}" in
      es*) sed -n '2,20p' "$0" | sed 's/^# \{0,1\}//' ;;
      *) cat <<'AYUDA'
Dixi Tower — local control tower for coding agents.
Launches interactive sessions of your coding agent inside tmux, each in its own
git worktree and branch. A project can have several agents at once: the first is
named after the project, the next ones <project>@2, <project>@3…

  dixi-tower panel [port]                      web panel (http://localhost:4310/)
  dixi-tower service install|uninstall|restart|status   keep the panel always on (macOS)
  dixi-tower doctor                            check requirements and installation
  dixi-tower launch <project> free --instruction <file> [--engine E] [--autonomy A]
  dixi-tower launch <project> <task-id> [--force] [--instruction <file>]
  dixi-tower next <project>                    pending tasks of a project, by priority
  dixi-tower status                            table of every agent
  dixi-tower show <agent> [lines]              current screen of an agent
  dixi-tower say <agent> "<message>"           type a message to an agent
  dixi-tower stop <agent>                      close its session (keeps worktree and branch)
  dixi-tower resume <agent>                    turn a stopped agent back on
  dixi-tower delete <agent>                    remove a stopped agent and its worktree
  dixi-tower attach                            how to watch the consoles live

Engines: claude, codex, or your own (see the usage guide). Autonomy: supervised,
balanced, autonomous. The Spanish command names (lanzar, estado, detener…) work too.
AYUDA
      ;;
    esac
    ;;
esac
