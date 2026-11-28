# Registro de cambios

## Propósito

Cambios de Dixi Tower por versión. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [Sin publicar]

### Añadido

- Servicio siempre encendido en Linux y en Windows con WSL2 (`dixi-tower service install`), con systemd de usuario. Reiniciar el panel no detiene a los agentes. En Windows, un lanzador en la carpeta de Inicio despierta WSL al iniciar sesión y lo mantiene encendido, así que el panel sigue en `http://localhost:4310/` sin ninguna ventana de Ubuntu abierta.
- Prueba del servicio con systemd (`tests/servicio.sh`) en la integración continua.

## [0.1.0] — 2026-11-28

Primera versión como proyecto propio. Nació dentro de un repositorio interno de Dixi y se separó para poder liberarlo.

### Añadido

- Lanzador de agentes en tmux, cada uno en su worktree y su rama.
- Panel web local con consola en vivo, teclado, enlaces y autocompletado de comandos «/».
- Ciclo de la sesión: lanzar, detener, encender de nuevo y eliminar.
- Varios agentes por proyecto.
- Configuración global y por agente: motor (Claude Code o Codex), autonomía, subagentes y límites de uso.
- Barrera de seguridad y hooks de estado para Claude Code.
- Panel como servicio de macOS.
- Motores propios: cualquier agente de terminal se puede definir como motor.
- Dictado en el panel, con el reconocimiento de voz del navegador.
- Archivos y rutas en el mensaje: arrastrar o pegar archivos (se guarda una copia) y explorador de carpetas para insertar rutas reales.
- Comandos, ayuda y mensajes en inglés y en español, según el idioma del sistema; `dixi-tower doctor`.
- Prueba de humo (`tests/smoke.sh`) y prueba en Linux con Docker (`tests/linux.sh`).
- Linux: avisos de escritorio con `notify-send`.
- Logo, imagen social e ícono del panel.
- Manual de operación con capturas, en inglés y en español (`docs/manual.md`, `docs/manual.es.md`).
- Reglas del agente en inglés (`worker-prompt.en.md`).
- Publicación en PyPI (`uv tool install dixi-tower`) con Trusted Publishing, sin tokens guardados: primero en TestPyPI y, con aprobación, en PyPI.
- Integración continua: prueba de humo en Ubuntu y macOS, desde el repositorio y contra el wheel instalado (`tests/wheel.sh`), y prueba en Debian con Docker.
- Windows a través de WSL2, probado en Windows Server 2025 con Ubuntu: guía en el manual, `doctor` reconoce WSL y avisa si los proyectos están en el disco de Windows, y los avisos de escritorio usan las notificaciones de Windows.

### Cambiado

- La versión vive solo en `src/dixi_tower/__init__.py`; `pyproject.toml` la lee de ahí.
- La instalación recomendada es desde PyPI; la de GitHub queda para probar cambios sin publicar.
- El enlace al tablero de tareas del panel es opcional: se configura con la clave `tablero`.
- Textos del panel pensados para quien empieza: el mensaje sin agentes indica el botón «＋ Nuevo agente» y el contador «Agentes activos» pasa a «Trabajando».
- Las reglas del agente ya no dan por hecho la forma de trabajar de Dixi; cada instalación añade las suyas en `~/.agentes/reglas.md`.
- El tope de tareas en revisión pasa a la configuración y viene desactivado; su mensaje explica cómo saltarlo.
- El registro de proyectos vive en `~/.agentes/proyectos.json`, no dentro del paquete.

### Corregido

- Con Codex, el panel mostraba «Trabajando» mientras esperaba una aprobación; ahora lee su pantalla y muestra «Te necesita».
- Con Codex, un evento interno podía guardar un id de sesión equivocado y romper «encender de nuevo».
- Con Codex, un aviso de actualización dejaba esperando al agente.
- `dixi-tower decir` no enviaba el mensaje a Codex.
- `dixi-tower detener` decía «Detenido» aunque el agente no existiera.
- `dixi-tower panel` ignoraba `DIXI_TOWER_HOME`, `DIXI_TOWER_PROJECTS` y `DIXI_TOWER_SESSION` si tmux ya estaba corriendo.
- Con Claude Code, el panel mostraba «Lanzando» mientras Claude pedía confiar en la carpeta; ahora muestra «Te necesita».
- Con Codex, el uso de la cuenta decía «no disponible» antes de que Codex lo informara.
- Un título largo se cortaba a mitad de palabra; ahora se corta en un espacio y termina en «…».
- El encargo, las reglas, los bloqueos de la barrera y de los límites, y los avisos de escritorio estaban solo en español; ahora siguen el idioma del usuario.
- `doctor` y la ayuda ignoraban `DIXI_TOWER_LANG`.
- Cambiar el `#agente` de la dirección (por ejemplo, al hacer clic en un aviso) no cambiaba de agente si el panel ya estaba abierto.
- Con Codex, el uso de la cuenta mostraba un límite que no se puede hacer cumplir.
- Dos encargos libres lanzados en el mismo minuto chocaban al compartir carpeta y rama.

### Conocido

- En Linux no hay servicio siempre encendido: el panel se levanta con `dixi-tower panel`.

## Links

- [Hoja de ruta](ROADMAP.md)
