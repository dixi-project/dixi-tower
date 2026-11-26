# Registro de cambios

## Propósito

Cambios de Dixi Tower por versión. El formato sigue [Keep a Changelog](https://keepachangelog.com/es-ES/1.1.0/).

## [0.1.0] — sin publicar

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
- Comandos y ayuda en inglés y en español; `dixi-tower doctor`.
- Prueba de humo (`tests/smoke.sh`).

### Cambiado

- Las reglas del agente ya no dan por hecho la forma de trabajar de Dixi; cada instalación añade las suyas en `~/.agentes/reglas.md`.
- El tope de tareas en revisión pasa a la configuración y viene desactivado; su mensaje explica cómo saltarlo.
- El registro de proyectos vive en `~/.agentes/proyectos.json`, no dentro del paquete.

### Corregido

- Dos encargos libres lanzados en el mismo minuto chocaban al compartir carpeta y rama.

### Conocido

- El soporte de Codex no se ha validado con una sesión real.
- Solo macOS.

## Links

- [Hoja de ruta](ROADMAP.md)
