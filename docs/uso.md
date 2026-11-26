# Guía de uso de Dixi Tower

## Propósito

Cómo se usa Dixi Tower día a día: comandos, configuración, piezas internas y reglas.

## Uso rápido

Los comandos tienen nombre en español y en inglés (`lanzar`/`launch`, `estado`/`status`, `detener`/`stop`…). `dixi-tower doctor` revisa requisitos e instalación.

```bash
dixi-tower servicio instalar    # panel siempre encendido en http://localhost:4310/
dixi-tower servicio reiniciar   # tras cambiar panel.py o los catálogos
dixi-tower servicio estado      # ¿instalado? ¿responde?
dixi-tower servicio quitar
dixi-tower panel                # alternativa sin servicio: lo levanta en tmux
```

El servicio es un LaunchAgent (`~/Library/LaunchAgents/com.dixi-project.dixi-tower.plist`): arranca al iniciar sesión en la Mac y launchd lo relanza si se cae, sin depender de tmux. Su salida va a `~/.dixi-tower/panel.log`. Guarda el `PATH` del momento en que se instaló; si cambia dónde viven `tmux`, `git`, `gh` o `claude`, hay que reinstalarlo.

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
tmux attach -t dixi-tower                                             # consolas en vivo
```

## Configuración

Se cambia desde el panel: **Configuración** (valores con los que nace cada agente, en `~/.dixi-tower/config.json`) y **Ajustes** en la ficha de cada agente (su copia propia, en su archivo de estado).

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
| `dixi-tower` | Crea el worktree y la rama, arma el prompt y abre el agente en una ventana de la sesión tmux `dixi-tower` |
| `~/.dixi-tower/proyectos.json` | Registro de proyectos (repo, rama base y comando de flujo). Un repo de la carpeta de proyectos se da de alta solo al lanzarlo (`registro.py`) |
| `worker-settings.json` | Permisos y hooks que se inyectan al agente con `--settings`, sin tocar el repo del proyecto |
| `worker-prompt.md` | Reglas del agente: una tarea, termina en PR, nunca integra ni despliega |
| `hooks/estado-hook.py` | Escribe `~/.dixi-tower/estado/<agente>.json` en cada evento y avisa por macOS cuando el agente se detiene |
| `config.py` | Configuración global y por agente, y comprobación de límites |
| `arranque.py` | Escribe el script que abre o retoma la sesión según motor y autonomía |
| `hooks/barra.py` | Barra de estado del agente: guarda el uso de la cuenta en `~/.dixi-tower/uso/` y muestra la barra propia del usuario |
| `hooks/control.py` | Antes de cada herramienta: aplica los límites de uso y el tope de subagentes |
| `hooks/codex-notify.py` | Fin de turno de un agente Codex: actualiza su estado y avisa |
| `comandos.json` | Comandos propios de cada motor para el autocompletado |
| `hooks/guardia.py` | Bloquea merge, push a la rama base, force push, deploys, AWS de escritura y lectura de secretos |
| `panel.py` | Panel web: lee los archivos de estado, git y tmux; textos en `locales/` |
| `tareas.py`, `estado.py`, `ocupado.py` | Lectura de `tasks/TASKS.md`, tabla de estado y control de worktree en uso |

## Motores propios

Además de Claude Code y Codex, puedes usar cualquier agente que se abra desde la terminal: otro CLI, un modelo local, un guion tuyo. Se definen en la clave `motores` de la configuración (`config.json` en la carpeta de datos):

```json
{
  "motores": {
    "aider": {
      "comando": "aider --message {instruccion}",
      "reanudar": "aider --restore-chat-history"
    }
  }
}
```

- `comando` abre la sesión. `{instruccion}` se sustituye por el encargo y `{reglas}` por las reglas del agente; ambos son opcionales.
- `reanudar` es opcional: lo que se ejecuta al encender de nuevo un agente detenido. Si falta, se usa `comando` con el encargo «Continúa con el encargo anterior».
- El motor aparece en los selectores del panel y en `--engine <nombre>`.

Con un motor propio, Dixi Tower te da lo que no depende del motor: worktree y rama propios, consola en vivo, teclado, ciclo de vida y estado aproximado (por cambios en su pantalla). No aplican la autonomía, los subagentes, los límites de uso ni la barrera propia: eso depende de lo que tu motor ofrezca.

## Dictado

En el panel puedes dictar en vez de escribir: mantén presionada la **barra espaciadora** con la caja vacía, o el botón **Dictar**, y suelta para terminar. El texto queda en la caja para que lo revises; no se envía solo.

Usa el reconocimiento de voz del navegador, que **no es local**: en Chrome el audio se transcribe en servidores de Google y en Safari lo procesa Apple. Si eso no es aceptable para tu trabajo, no lo uses.

## Reglas del agente

Todo agente recibe las reglas de `worker-prompt.md`: un encargo, una rama, termina en un pull request, nunca integra, despliega ni lee secretos.

Para añadir las tuyas, crea `~/.dixi-tower/reglas.md`. Su contenido se agrega al final de las reglas de cada agente la próxima vez que se enciende. Sirve para convenciones de tu equipo: idioma de los commits, tamaño máximo de un pull request, qué archivos no se tocan.

## Integración con tareas (opcional)

Dixi Tower funciona sin ningún gestor de tareas: cada agente nace con una instrucción libre y una rama `agente/<resumen>-<fecha>`.

Si un proyecto tiene `tasks/TASKS.md` con el formato de [sys_task](https://task.dixi-project.com/) (líneas `- [ ] **Título** <!-- st:id -->`), se activa sola una integración:

- El formulario de «Nuevo agente» ofrece las tareas pendientes, por prioridad.
- La rama se llama `st/<id>-<resumen>`, que es la convención con la que sys_task mueve la tarjeta.
- Se puede fijar un **tope de tareas en revisión** por proyecto en Configuración: con más tareas en `[r]` que el tope, no se lanza un agente nuevo salvo que se fuerce. De fábrica es 0, desactivado.

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
- **Tope en revisión** (solo con la integración de tareas): ver «Integración con tareas».
- **Los datos de trabajo** viven en `~/.dixi-tower/` (`estado/`, `run/`, `worktrees/`), fuera de cualquier repositorio.

## Variables

Los nombres anteriores (`DIXI_AGENTES_*`, `DIXI_PROYECTOS_DIR`) se siguen aceptando.

| Variable | Por defecto | Para qué |
|---|---|---|
| `DIXI_TOWER_PROJECTS` | `~/projects` | Carpeta cuyos repositorios se pueden lanzar |
| `DIXI_TOWER_HOME` | `~/.dixi-tower` | Carpeta de datos: estado, configuración, scripts de arranque y worktrees. Si solo existe `~/.dixi-tower` (instalaciones anteriores), se usa esa |
| `DIXI_TOWER_PORT` | `4310` | Puerto del panel |
| `DIXI_TOWER_NOTIFY` | `1` | `0` apaga las notificaciones |
| `DIXI_TOWER_SESSION` | `dixi-tower` | Nombre de la sesión tmux de los agentes |

## Seguridad del panel

Escucha solo en `127.0.0.1`, rechaza peticiones cuya cabecera `Host` no sea local y exige un token aleatorio por arranque para toda acción que escribe (enviar texto o teclas, detener, lanzar). Quien pueda abrir el panel puede dar instrucciones a los agentes: no lo expongas por túnel ni proxy.

## Links

- [README](../README.es.md)
- [Hoja de ruta](../ROADMAP.md)
