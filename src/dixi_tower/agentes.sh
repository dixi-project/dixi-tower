#!/usr/bin/env bash
# Dixi Tower — torre de control local para agentes de código.
# Lanzador: crea el worktree y la rama de cada agente y lo abre en una ventana de tmux.
# La ayuda de los comandos está al final, en español e inglés (dixi-tower sin argumentos).
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

m() { python3 "$DIR/mensajes.py" "$@"; }   # mensaje en el idioma del usuario

esperar_panel() {   # hasta 15 s: al arrancar con la máquina ocupada puede tardar
  local i; for i in $(seq 1 30); do panel_responde && return 0; sleep 0.5; done; return 1
}

panel_responde() { curl -s -o /dev/null -m 2 "http://127.0.0.1:${1:-$PUERTO}/es/lista"; }

mkdir -p "$HOME_AG/estado" "$HOME_AG/run" "$HOME_AG/worktrees"

campo() { # campo <proyecto> <clave>
  python3 - "$REG" "$1" "$2" "$DIR" <<'PY'
import json, sys
d = json.load(open(sys.argv[1]))
p = d.get(sys.argv[2])
if p is None:
    sys.path.insert(0, sys.argv[4]); from mensajes import t
    sys.exit(t("proyecto_desconocido", p=sys.argv[2], lista=", ".join(d)))
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
    git -C "$1" fetch --quiet origin "$2" || m sin_actualizar "base=$2" >&2
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
  if [ "$tope" = "0" ]; then m revision_sin_tope "n=$(tareas "$repo" "$base" revision)"
  else m revision_tope "n=$(tareas "$repo" "$base" revision)" "tope=$tope"; fi
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
      *) m opcion_desconocida "op=$1" >&2; exit 1 ;;
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
      m falta_instruccion >&2; exit 1
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
    m tarea_ocupada "p=$p" >&2; exit 1
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
      printf '%s\n\n' "$(m encargo_tarea "id=$id" "titulo=$titulo")"
      printf '%s\n%s\n\n' "$(m encargo_registro)" "$linea"
      if [ -n "$instr" ] && [ -s "$instr" ]; then
        printf '%s\n' "$(m encargo_indicaciones)"; cat "$instr"; printf '\n\n'
      fi
    fi
    printf '%s' "$(m encargo_rama "rama=$rama" "ref=$ref")"
    [ "$id" = "libre" ] && printf '\n' || printf ' %s\n' "$(m encargo_ficha)"
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
  m lanzado "ag=$ag" "id=$id" "rama=$rama"
  m worktree "wt=$wt"
}

cmd_estado() { python3 "$DIR/estado.py" "$HOME_AG" "$REG" "$SESION"; }

cmd_ver() {
  ventana_viva "$1" || { m sin_ventana "ag=$1" >&2; exit 1; }
  tmux capture-pane -p -t "$SESION:$1" -S "-${2:-40}"
}

cmd_decir() {
  ventana_viva "$1" || { m sin_ventana "ag=$1" >&2; exit 1; }
  # Como el panel: pegado entre corchetes y una pausa antes de Enter. Codex trata el
  # texto que llega muy rápido como un pegado y se tragaría un Enter inmediato.
  printf '%s' "$2" | tmux load-buffer -b dixi-tower-decir -
  tmux paste-buffer -p -d -b dixi-tower-decir -t "$SESION:$1"
  sleep 0.3
  tmux send-keys -t "$SESION:$1" Enter
}

cmd_detener() {
  if [ ! -f "$HOME_AG/estado/$1.json" ] && ! ventana_viva "$1"; then m desconocido "ag=$1" >&2; exit 1; fi
  ventana_viva "$1" && tmux kill-window -t "$SESION:$1"
  python3 - "$HOME_AG/estado/$1.json" <<'PY'
import json, sys, time, os
f = sys.argv[1]
if os.path.exists(f):
    d = json.load(open(f))
    d.update(estado="cerrado", detalle="detenido por la torre", actualizado=time.time())
    json.dump(d, open(f, "w"), ensure_ascii=False, indent=1)
PY
  m detenido "ag=$1"
}

cmd_reanudar() {
  local ag="$1"
  [ -f "$HOME_AG/estado/$ag.json" ] || { m desconocido "ag=$ag" >&2; exit 1; }
  if ventana_viva "$ag"; then m ya_encendido "ag=$ag" >&2; exit 1; fi
  # Mismo worktree y reglas; retoma la conversación con el motor y la autonomía
  # que tenga configurados ahora.
  local nuevo
  nuevo="$(python3 "$DIR/arranque.py" "$ag" reanudar)" || exit 1
  if tmux has-session -t "$SESION" 2>/dev/null; then
    tmux new-window -d -t "$SESION" -n "$ag" "$nuevo"
  else
    tmux new-session -d -s "$SESION" -n "$ag" "$nuevo"
  fi
  m reanudado "ag=$ag"
}

cmd_eliminar() {
  local ag="$1" est="$HOME_AG/estado/$1.json"
  [ -f "$est" ] || { m desconocido "ag=$ag" >&2; exit 1; }
  if ventana_viva "$ag"; then m encendido_no_eliminar "ag=$ag" >&2; exit 1; fi
  local wt rama
  wt="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("worktree") or "")' "$est")"
  rama="$(python3 -c 'import json,sys; print(json.load(open(sys.argv[1])).get("rama") or "")' "$est")"
  # Solo se borra un worktree que esté dentro de la carpeta de la torre.
  if [ -n "$wt" ] && [ -d "$wt" ]; then
    case "$wt" in
      "$HOME_AG/worktrees/"*) ;;
      *) m worktree_fuera "dir=$HOME_AG/worktrees" "wt=$wt" >&2; exit 1 ;;
    esac
    local sucios
    sucios="$(git -C "$wt" status --porcelain | wc -l | tr -d ' ')"
    if [ "$sucios" != "0" ]; then
      m sin_commit "n=$sucios" "wt=$wt" >&2; exit 1
    fi
    # Sin --force: git se niega si queda algo sin guardar. La rama no se borra,
    # así que los commits del agente siguen en el repositorio.
    git -C "$wt" worktree remove "$wt" || { m git_no_quita "wt=$wt" >&2; exit 1; }
  fi
  rm -f "$est" "$HOME_AG/run/$ag.sh" "$HOME_AG/run/$ag.prompt.txt" "$HOME_AG/run/$ag.reanudar.sh"
  rm -f "$HOME_AG/run/$ag.reglas.md" "$HOME_AG/uso/$ag.json" "$HOME_AG/uso/$ag.subagentes.json"
  rm -rf "$HOME_AG/adjuntos/$ag"
  m eliminado "ag=$ag" "rama=${rama:--}"
}

# ── Servicio siempre encendido ───────────────────────────────────────────────
# macOS: LaunchAgent de launchd. Linux y Windows con WSL2: servicio de usuario de
# systemd; en WSL, además, un lanzador en la carpeta de Inicio de Windows mantiene
# viva la distribución (WSL la apaga cuando no queda ninguna ventana abierta).
UNIDAD="$HOME/.config/systemd/user/dixi-tower.service"
case "$(uname)" in Darwin) SERVICIO="$PLIST" ;; *) SERVICIO="$UNIDAD" ;; esac
es_wsl() { [ -n "${WSL_DISTRO_NAME:-}" ] || grep -qi microsoft /proc/version 2>/dev/null; }

servicio_macos() {
  local dominio="gui/$(id -u)"
  case "$1" in
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
      if esperar_panel; then m servicio_instalado "url=http://localhost:$PUERTO/"
      else m servicio_sin_respuesta "log=$HOME_AG/panel.log" >&2; exit 1; fi
      ;;
    quitar|uninstall)
      launchctl bootout "$dominio/$ETIQUETA" 2>/dev/null || true
      rm -f "$PLIST"
      m servicio_quitado
      ;;
    reiniciar|restart)
      launchctl kickstart -k "$dominio/$ETIQUETA"
      if esperar_panel; then m panel_reiniciado "url=http://localhost:$PUERTO/"; else m panel_no_responde "log=$HOME_AG/panel.log" >&2; exit 1; fi
      ;;
    estado|status)
      if [ -f "$PLIST" ]; then m servicio_si "plist=$PLIST"; else m servicio_no; fi
      if panel_responde; then m panel_si "url=http://localhost:$PUERTO/"; else m panel_no; fi
      ;;
    *) m uso_servicio >&2; exit 1 ;;
  esac
}

# Carpeta de Inicio de Windows y lanzador que despierta WSL al iniciar sesión.
inicio_windows() {
  local w; w="$(powershell.exe -NoProfile -Command '[Environment]::GetFolderPath("Startup")' 2>/dev/null | tr -d '\r')"
  [ -n "$w" ] && wslpath -u "$w"
}
LANZADOR_WSL="Dixi Tower.vbs"
mantener_wsl() {   # mantener_wsl instalar|quitar
  local carpeta; carpeta="$(inicio_windows)" || true
  if [ -z "$carpeta" ] || [ ! -d "$carpeta" ]; then m servicio_wsl_sin_inicio >&2; return 1; fi
  local vbs="$carpeta/$LANZADOR_WSL"
  if [ "$1" = quitar ]; then
    rm -f "$vbs"; pkill -f '^dixi-tower-wsl' 2>/dev/null || true; return 0
  fi
  # Un proceso que no termina (sleep con otro nombre, para poder quitarlo) mantiene
  # viva la distribución; la ventana se abre oculta (el 0 de Run). El .vbs va en
  # ASCII porque wscript no lo lee como UTF-8.
  printf '%s\r\n' \
    "' Dixi Tower: keeps the WSL distribution $WSL_DISTRO_NAME running so the panel stays at http://localhost:$PUERTO/" \
    "CreateObject(\"WScript.Shell\").Run \"wsl.exe -d \"\"$WSL_DISTRO_NAME\"\" --exec bash -c \"\"exec -a dixi-tower-wsl sleep infinity\"\"\", 0, False" > "$vbs"
  pgrep -f '^dixi-tower-wsl' >/dev/null || (cd /mnt/c 2>/dev/null; wscript.exe "$(wslpath -w "$vbs")") >/dev/null 2>&1 || true
}

servicio_linux() {
  local accion="$1"
  case "$accion" in instalar|install|quitar|uninstall|reiniciar|restart|estado|status) ;; *) m uso_servicio >&2; exit 1 ;; esac
  if ! command -v systemctl >/dev/null || [ ! -d /run/systemd/system ] || ! systemctl --user show-environment >/dev/null 2>&1; then
    case "$accion" in
      estado|status) m servicio_no; if panel_responde; then m panel_si "url=http://localhost:$PUERTO/"; else m panel_no; fi; return 0 ;;
    esac
    if es_wsl; then m servicio_sin_systemd_wsl >&2; else m servicio_sin_systemd >&2; fi
    exit 1
  fi
  case "$accion" in
    instalar|install)
      if ventana_viva panel; then tmux kill-window -t "$SESION:panel"; fi
      mkdir -p "$(dirname "$UNIDAD")"
      python3 - "$UNIDAD" "$(command -v python3)" "$DIR" "$PUERTO" "$HOME_AG" "$PATH" "$PROYECTOS_DIR" <<'PYS'
import sys
ruta, python, carpeta, puerto, home_ag, path, proyectos = sys.argv[1:]
q = lambda v: '"' + v.replace("\\", "\\\\").replace('"', '\\"').replace("%", "%%") + '"'
with open(ruta, "w") as fh:
    fh.write(f"""[Unit]
Description=Dixi Tower panel (http://localhost:{puerto}/)

[Service]
# WorkingDirectory no admite comillas (toma la línea entera, espacios incluidos).
ExecStart={q(python)} {q(carpeta + "/panel.py")} {puerto}
WorkingDirectory={carpeta}
# systemd arranca con un PATH mínimo: se fija el de esta sesión para que el panel
# y los agentes que lance encuentren tmux, git, gh y el motor.
Environment={q("PATH=" + path)} {q("DIXI_AGENTES_HOME=" + home_ag)} {q("DIXI_AGENTES_PUERTO=" + puerto)} {q("DIXI_PROYECTOS_DIR=" + proyectos)}
Restart=always
RestartSec=5
# Los agentes viven en tmux, que el panel arranca: al reiniciar o detener el panel
# solo se detiene el panel, no los agentes.
KillMode=process
StandardOutput=append:{home_ag}/panel.log
StandardError=append:{home_ag}/panel.log

[Install]
WantedBy=default.target
""")
PYS
      systemctl --user daemon-reload
      systemctl --user enable dixi-tower.service >/dev/null 2>&1
      systemctl --user restart dixi-tower.service
      if es_wsl; then
        # Sin «linger», el servicio de usuario no arranca hasta abrir una terminal.
        loginctl enable-linger "$(id -un)" 2>/dev/null || sudo -n loginctl enable-linger "$(id -un)" 2>/dev/null \
          || m servicio_linger "u=$(id -un)" >&2
        mantener_wsl instalar && m servicio_wsl_inicio
      fi
      if esperar_panel; then m servicio_instalado "url=http://localhost:$PUERTO/"
      else m servicio_sin_respuesta "log=$HOME_AG/panel.log" >&2; exit 1; fi
      ;;
    quitar|uninstall)
      systemctl --user disable --now dixi-tower.service >/dev/null 2>&1 || true
      rm -f "$UNIDAD"; systemctl --user daemon-reload
      if es_wsl; then mantener_wsl quitar || true; fi
      m servicio_quitado
      ;;
    reiniciar|restart)
      systemctl --user restart dixi-tower.service
      if esperar_panel; then m panel_reiniciado "url=http://localhost:$PUERTO/"; else m panel_no_responde "log=$HOME_AG/panel.log" >&2; exit 1; fi
      ;;
    estado|status)
      if [ -f "$UNIDAD" ]; then m servicio_si "plist=$UNIDAD"; else m servicio_no; fi
      if panel_responde; then m panel_si "url=http://localhost:$PUERTO/"; else m panel_no; fi
      ;;
  esac
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
  doctor)    python3 "$DIR/doctor.py" "$PUERTO" "$SERVICIO" ;;
  abrir|attach) m attach "s=$SESION" ;;
  panel)
    puerto="${2:-$PUERTO}"
    # Una ventana nueva de tmux hereda el entorno del servidor tmux, no el de esta
    # terminal: el panel recibe la carpeta de datos, la de proyectos y la sesión a mano.
    cmd_panel="env DIXI_TOWER_HOME=$(printf %q "$HOME_AG") DIXI_TOWER_PROJECTS=$(printf %q "$PROYECTOS_DIR") DIXI_TOWER_SESSION=$(printf %q "$SESION")"
    [ -n "${DIXI_TOWER_NOTIFY:-}" ] && cmd_panel+=" DIXI_TOWER_NOTIFY=$(printf %q "$DIXI_TOWER_NOTIFY")"
    [ -n "${DIXI_TOWER_LANG:-}" ] && cmd_panel+=" DIXI_TOWER_LANG=$(printf %q "$DIXI_TOWER_LANG")"
    cmd_panel+=" python3 $(printf %q "$DIR/panel.py") $puerto"
    if panel_responde "$puerto"; then
      m panel_corriendo
    elif tmux has-session -t "$SESION" 2>/dev/null; then
      tmux new-window -d -t "$SESION" -n panel "$cmd_panel"
    else
      tmux new-session -d -s "$SESION" -n panel "$cmd_panel"
    fi
    m panel_url "url=http://localhost:$puerto/"
    ;;
  servicio|service)
    case "$(uname)" in
      Darwin) servicio_macos "${2:-estado}" ;;
      Linux) servicio_linux "${2:-estado}" ;;
      *) m servicio_sin_soporte >&2; exit 1 ;;
    esac
    ;;
  *)
    case "${DIXI_TOWER_LANG:-${LC_ALL:-${LC_MESSAGES:-${LANG:-}}}}" in
      es*) cat <<'AYUDA'
Dixi Tower — torre de control local para agentes de código.
Lanza sesiones interactivas de tu agente de código dentro de tmux, cada una en su
propio worktree y rama de git. Un proyecto puede tener varios agentes a la vez: el
primero se llama como el proyecto y los siguientes <proyecto>@2, <proyecto>@3…

  dixi-tower panel [puerto]                    panel web (http://localhost:4310/)
  dixi-tower servicio instalar|quitar|reiniciar|estado   panel siempre encendido (macOS, Linux, WSL)
  dixi-tower doctor                            revisa requisitos e instalación
  dixi-tower lanzar <proyecto> libre --instruccion <archivo> [--motor M] [--autonomia A]
  dixi-tower lanzar <proyecto> <id-de-tarea> [--forzar] [--instruccion <archivo>]
  dixi-tower siguiente <proyecto>              tareas pendientes de un proyecto, por prioridad
  dixi-tower estado                            tabla de todos los agentes
  dixi-tower ver <agente> [líneas]             pantalla actual de un agente
  dixi-tower decir <agente> "<mensaje>"        escribirle un mensaje a un agente
  dixi-tower detener <agente>                  cierra su sesión (conserva worktree y rama)
  dixi-tower reanudar <agente>                 vuelve a encender un agente detenido
  dixi-tower eliminar <agente>                 quita un agente detenido y su worktree
  dixi-tower abrir                             cómo ver las consolas en vivo

Motores: claude, codex o uno propio (ver la guía de uso). Autonomía: supervisada,
equilibrada, autonoma. Los nombres en inglés (launch, status, stop…) también sirven.
AYUDA
      ;;
      *) cat <<'AYUDA'
Dixi Tower — local control tower for coding agents.
Launches interactive sessions of your coding agent inside tmux, each in its own
git worktree and branch. A project can have several agents at once: the first is
named after the project, the next ones <project>@2, <project>@3…

  dixi-tower panel [port]                      web panel (http://localhost:4310/)
  dixi-tower service install|uninstall|restart|status   keep the panel always on (macOS, Linux, WSL)
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
