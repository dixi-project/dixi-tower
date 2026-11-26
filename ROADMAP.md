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

- [ ] Publicar en PyPI e instalar con `uv tool install dixi-tower` o `pipx install dixi-tower`. El paquete ya está definido en `pyproject.toml`; falta probar una instalación real.
- [x] `dixi-tower doctor`: revisa requisitos, motores e instalación. Falta comprobar que el motor tiene sesión iniciada.
- [ ] Elegir licencia.

### 3. Motores

- [x] Motores propios: cualquier agente de terminal, definido en la configuración.
- [ ] Definir motores propios desde el panel (hoy se editan en `config.json`).
- [ ] **Validar Codex con una sesión real**: aviso de fin de turno, retomar sesión, comportamiento con commits (su sandbox protege `.git`).
- [ ] Límites de uso con Codex: hoy no se pueden aplicar porque no los expone a un script.
- [ ] Comandos «/» del motor: la lista es curada a mano; buscar una fuente que no se desfase.

### 4. Idioma

- [x] Línea de comandos y ayuda en inglés y en español.
- [ ] Mensajes del lanzador en los dos idiomas (hoy salen en español).
- [ ] Guía de uso en inglés.
- [ ] Reglas del agente (`worker-prompt.md`) en el idioma del usuario.

### 5. Sistemas

- [ ] Linux: servicio con systemd y avisos con `notify-send`.
- [ ] Windows: solo vía WSL; documentarlo.

### 6. Calidad

- [x] Prueba de humo repetible (`tests/smoke.sh`), con motores falsos y una sesión tmux aislada.
- [ ] Pruebas del panel en un navegador (hoy se verifican a mano).
- [ ] Integración continua.

## Después

- Sitio y documentación en https://dixi-tower.dixi-project.com/, con una URL por idioma.
- Ícono en la barra de menú de macOS con el número de agentes que esperan.
- Cola continua: que al terminar una tarea se tome sola la siguiente.

## Links

- [README](README.es.md)
- [Guía de uso](docs/uso.md)
