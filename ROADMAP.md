# Hoja de ruta de Dixi Tower

## Propósito

Qué falta para pasar de herramienta privada a producto que cualquiera pueda instalar y usar, en orden.

El sitio del proyecto será https://dixi-tower.dixi-project.com/.

## Antes de hacerlo público

### 1. Quitar lo que es propio de Dixi

- [x] Reglas del agente genéricas; las de cada instalación van en `~/.agentes/reglas.md`.
- [x] La integración con tareas es opcional y se activa sola si el proyecto tiene `tasks/TASKS.md`; sin ella, todo agente nace con instrucción libre.
- [x] El tope de «tareas en revisión» es configurable y viene desactivado.
- [x] Nombres nuevos para la carpeta de datos (`~/.dixi-tower`), la sesión tmux (`dixi-tower`) y las variables (`DIXI_TOWER_*`). Los anteriores se siguen aceptando.
- [ ] Comando para migrar una instalación anterior de `~/.agentes` a `~/.dixi-tower` (hay que reparar los worktrees).
- [ ] Las reglas por proyecto (hoy solo hay reglas por instalación).

### 2. Instalación

- [x] Instalación con `uv tool install` o `pipx install` desde GitHub, probada con la prueba de humo contra lo instalado.
- [x] Publicar en PyPI (`uv tool install dixi-tower`): al empujar una etiqueta `v*`, `release.yml` construye, prueba el wheel y publica con Trusted Publishing, primero en TestPyPI y, con aprobación, en PyPI.
- [x] `dixi-tower doctor`: revisa requisitos, motores e instalación. Falta comprobar que el motor tiene sesión iniciada.
- [x] Licencia MIT.

### 3. Motores

- [x] Motores propios: cualquier agente de terminal, definido en la configuración.
- [ ] Definir motores propios desde el panel (hoy se editan en `config.json`).
- [x] Codex validado con una sesión real: arranque, fin de turno, aprobación de commits, estado en el panel y retomar la sesión.
- [ ] Límites de uso con Codex: ya se muestran (leídos de su pie); falta aplicarlos, quizá con sus hooks.
- [ ] Comandos «/» del motor: la lista es curada a mano; buscar una fuente que no se desfase.

### 4. Idioma

- [x] Línea de comandos y ayuda en inglés y en español.
- [x] Mensajes del lanzador en los dos idiomas, según el idioma del sistema o `DIXI_TOWER_LANG`.
- [x] Guía de uso en inglés (`docs/usage.md`).
- [x] Reglas del agente, encargo, bloqueos y avisos en el idioma del usuario.

### 5. Sistemas

- [x] Linux probado en Debian 12 (`tests/linux.sh`): panel, agentes, instalación con pip y avisos con `notify-send`.
- [x] Linux y Windows (WSL2): servicio siempre encendido con systemd de usuario (`tests/servicio.sh` en la CI); en Windows, una entrada en las aplicaciones de inicio despierta WSL al iniciar sesión, sin ventana.
- [x] Windows vía WSL2: documentado en el manual, `doctor` lo reconoce y avisa si los proyectos están en el disco de Windows, y los avisos usan las notificaciones de Windows.
- [x] Windows vía WSL2 probado en Windows Server 2025 con Ubuntu (`tests/windows/`): instalación, `doctor`, panel en Edge, agente con Claude Code y avisos de Windows que abren el agente.
- [ ] Windows nativo, sin WSL: solo si hay demanda. Exige manejar las terminales sin tmux (ConPTY) y pasar el lanzador de bash a Python.

### 6. Calidad

- [x] Prueba de humo repetible (`tests/smoke.sh`), con motores falsos y una sesión tmux aislada.
- [ ] Pruebas del panel en un navegador (hoy se verifican a mano).
- [x] Integración continua (`ci.yml`): en cada push y PR, `tests/smoke.sh` en Ubuntu y macOS desde el repositorio y contra el wheel instalado (`tests/wheel.sh`), y `tests/linux.sh` en Debian con Docker.

## Después

- Sitio y documentación en https://dixi-tower.dixi-project.com/, con una URL por idioma.
- Apps para macOS, Linux, iOS y Android: en el escritorio levantan la torre y la muestran (en macOS, con el ícono en la barra de menú y el número de agentes que esperan); en el móvil la controlan a distancia. Plan en [docs/apps-nativas.md](docs/apps-nativas.md). Windows sin app nativa: la torre corre ahí con WSL2.
- Cola continua: que al terminar una tarea se tome sola la siguiente.

## Links

- [README](README.es.md)
- [Guía de uso](docs/uso.md)
