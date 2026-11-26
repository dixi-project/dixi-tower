# Guía de uso de Dixi Tower

## Propósito

Cómo se usa Dixi Tower día a día: comandos, configuración, piezas internas y reglas.

## Uso rápido

```bash
dixi-tower servicio instalar    # panel siempre encendido en http://localhost:4310/
dixi-tower servicio reiniciar   # tras cambiar panel.py o los catálogos
dixi-tower servicio estado      # ¿instalado? ¿responde?
dixi-tower servicio quitar
dixi-tower panel                # alternativa sin servicio: lo levanta en tmux
```

El servicio es un LaunchAgent (`~/Library/LaunchAgents/com.dixi-project.dixi-tower.plist`): arranca al iniciar sesión en la Mac y launchd lo relanza si se cae, sin depender de tmux. Su salida va a `~/.agentes/panel.log`. Guarda el `PATH` del momento en que se instaló; si cambia dónde viven `tmux`, `git`, `gh` o `claude`, hay que reinstalarlo.

Desde el panel se hace todo lo demás: lanzar un agente («＋ Nuevo agente»), ver su consola, escribirle, mandarle teclas y detenerlo.

Por terminal:

```bash
dixi-tower siguiente <proyecto>                    # candidatas del backlog
dixi-tower lanzar <proyecto> <st-id> [--forzar]    # con tarea del tablero
dixi-tower lanzar <proyecto> libre --instruccion <archivo>
dixi-tower estado
dixi-tower ver <agente> | decir <agente> "<msg>" | detener <agente>
dixi-tower reanudar <agente>                       # encender uno cerrado y retomar su conversación
dixi-tower eliminar <agente>                       # quitar uno cerrado y su worktree
tmux attach -t agentes                                             # consolas en vivo
```

## Configuración

Se cambia desde el panel: **Configuración** (valores con los que nace cada agente, en `~/.agentes/config.json`) y **Ajustes** en la ficha de cada agente (su copia propia, en su archivo de estado).

| Ajuste | Opciones | Cuándo aplica |
|---|---|---|
| Motor | `claude` (Claude Code) o `codex` (Codex CLI) | Al encender el agente |
| Autonomía | `supervisada`, `equilibrada`, `autonoma` | Al encender el agente |
| Subagentes | permitidos o no, y máximo abiertos a la vez (1 a 20) | Claude: de inmediato. Codex: al encender |
| Límite de uso semanal y de sesión (5 h) | porcentaje de la cuenta; 0 = sin límite | Claude: de inmediato. Codex: no se aplica |

Cómo se traduce la autonomía en cada motor:

| Nivel | Claude Code | Codex |
|---|---|---|
| Supervisada | `--permission-mode manual` | `--sandbox read-only --ask-for-approval on-request` |
| Equilibrada | `--permission-mode acceptEdits` | `--sandbox workspace-write --ask-for-approval on-request` |
| Autónoma | `--permission-mode auto` | `--approve-for-me` (un revisor automático aprueba) |

En los tres niveles el agente sigue sin poder integrar, desplegar ni leer secretos.

### Diferencias entre motores

| | Claude Code | Codex |
|---|---|---|
| Reglas del agente | `--append-system-prompt` | `-c developer_instructions=…` |
| Estado en el panel | Hooks en cada evento: exacto | Aviso de fin de turno (`notify`) y cambios en su pantalla: aproximado |
| Barrera propia (`guardia.py`) | Sí | No: la barrera es el sandbox de Codex |
| Límites de uso | Sí (Claude los entrega a la barra de estado) | No: Codex no los expone a un script; se ven en el pie de su consola |
| Commits | Sin fricción | Su sandbox protege `.git`: cada commit pide aprobación, salvo en autónoma |

El soporte de Codex está **sin validar con una sesión real**: el arranque se probó con un binario falso y su sandbox con comandos sueltos.

## Cómo funciona

| Pieza | Qué hace |
|---|---|
| `dixi-tower` | Crea el worktree y la rama, arma el prompt y abre el agente en una ventana de la sesión tmux `agentes` |
| `~/.agentes/proyectos.json` | Registro de proyectos (repo, rama base, comando de flujo, tope en revisión). Un repo de la carpeta de proyectos se da de alta solo al lanzarlo (`registro.py`) |
| `worker-settings.json` | Permisos y hooks que se inyectan al agente con `--settings`, sin tocar el repo del proyecto |
| `worker-prompt.md` | Reglas del agente: una tarea, termina en PR, nunca integra ni despliega |
| `hooks/estado-hook.py` | Escribe `~/.agentes/estado/<agente>.json` en cada evento y avisa por macOS cuando el agente se detiene |
| `config.py` | Configuración global y por agente, y comprobación de límites |
| `arranque.py` | Escribe el script que abre o retoma la sesión según motor y autonomía |
| `hooks/barra.py` | Barra de estado del agente: guarda el uso de la cuenta en `~/.agentes/uso/` y muestra la barra propia del usuario |
| `hooks/control.py` | Antes de cada herramienta: aplica los límites de uso y el tope de subagentes |
| `hooks/codex-notify.py` | Fin de turno de un agente Codex: actualiza su estado y avisa |
| `comandos.json` | Comandos propios de cada motor para el autocompletado |
| `hooks/guardia.py` | Bloquea merge, push a la rama base, force push, deploys, AWS de escritura y lectura de secretos |
| `panel.py` | Panel web: lee los archivos de estado, git y tmux; textos en `locales/` |
| `tareas.py`, `estado.py`, `ocupado.py` | Lectura de `tasks/TASKS.md`, tabla de estado y control de worktree en uso |

## Comandos «/» en el panel

Al escribir `/` en la caja de texto aparece el autocompletado con los comandos que ese agente entiende:

| Origen | De dónde salen |
|---|---|
| Del proyecto | `.claude/commands/**/*.md` y `.claude/skills/*/SKILL.md` del worktree del agente. Lo que instala un kit en el proyecto, como los `/dixi.*` de dixi-spec-kit, aparece aquí sin configurar nada |
| Tuyos | `~/.claude/commands` y `~/.claude/skills` |
| Del motor | `comandos.json`: lista curada de comandos propios de Claude Code y de Codex. Ningún motor la entrega a un script, así que puede no coincidir exactamente con la versión instalada |

Con Codex solo se ofrecen los del motor. ↑ ↓ eligen, Tab o Enter completan, Esc cierra; el comando se envía con un segundo Enter.

## Reglas

- **Nombre del agente**: el primero de un proyecto se llama como el proyecto; los siguientes, `<proyecto>@2`, `<proyecto>@3`… Nunca hay dos agentes sobre la misma tarea.
- **Ramas**: con tarea del tablero, `st/<id>-<slug>` (mueve la tarjeta en sys_task); con instrucción libre, `agente/<slug>-<fecha>` (no mueve nada).
- **Ciclo de un agente**: lanzar → (detener ⇄ reanudar) → eliminar. Eliminar exige que esté detenido y sin archivos sin commit; borra su worktree y su estado, y **conserva la rama** con sus commits.
- **Tope**: no se lanza en un proyecto con más de `max_en_revision` tareas en `[r]`, salvo `--forzar`.
- **Los datos de trabajo** viven en `~/.agentes/` (`estado/`, `run/`, `worktrees/`), fuera de cualquier repositorio.

## Variables

| Variable | Por defecto | Para qué |
|---|---|---|
| `DIXI_PROYECTOS_DIR` | `~/projects` | Carpeta cuyos repos se pueden lanzar |
| `DIXI_AGENTES_HOME` | `~/.agentes` | Estado, scripts de arranque y worktrees |
| `DIXI_AGENTES_PUERTO` | `4310` | Puerto del panel |
| `DIXI_AGENTES_AVISOS` | `1` | `0` apaga las notificaciones de macOS |

## Seguridad del panel

Escucha solo en `127.0.0.1`, rechaza peticiones cuya cabecera `Host` no sea local y exige un token aleatorio por arranque para toda acción que escribe (enviar texto o teclas, detener, lanzar). Quien pueda abrir el panel puede dar instrucciones a los agentes: no lo expongas por túnel ni proxy.

## Links

- [README](../README.es.md)
- [Hoja de ruta](../ROADMAP.md)
