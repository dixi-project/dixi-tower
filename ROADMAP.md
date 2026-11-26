# Hoja de ruta de Dixi Tower

## Propósito

Qué falta para pasar de herramienta privada a producto que cualquiera pueda instalar y usar, en orden.

El sitio del proyecto será https://dixi-tower.dixi-project.com/.

## Antes de hacerlo público

### 1. Quitar lo que es propio de Dixi

- [ ] `worker-prompt.md` da por hecho `tasks/TASKS.md`, casillas de sys_task y que integrar despliega a producción: dejarlo genérico y permitir que cada proyecto añada sus reglas.
- [ ] La lectura de tareas (`tareas.py`) y las ramas `st/<id>-…` son la integración con sys_task: convertirla en una integración opcional. Sin ella, todo agente nace con instrucción libre.
- [ ] El tope de «tareas en revisión» depende de esa misma integración.
- [ ] Carpeta de datos `~/.agentes` y variables `DIXI_AGENTES_*`: decidir si se renombran a `~/.dixi-tower` y `DIXI_TOWER_*`, con migración.

### 2. Instalación

- [ ] Publicar en PyPI e instalar con `uv tool install dixi-tower` o `pipx install dixi-tower`. El paquete ya está definido en `pyproject.toml`; falta probar una instalación real.
- [ ] `dixi-tower doctor`: comprobar tmux, git, motores instalados y sesión iniciada.
- [ ] Elegir licencia.

### 3. Motores

- [ ] **Validar Codex con una sesión real**: aviso de fin de turno, retomar sesión, comportamiento con commits (su sandbox protege `.git`).
- [ ] Límites de uso con Codex: hoy no se pueden aplicar porque no los expone a un script.
- [ ] Comandos «/» del motor: la lista es curada a mano; buscar una fuente que no se desfase.

### 4. Idioma

- [ ] Línea de comandos en inglés (`launch`, `status`, `stop`…) conservando los nombres en español como alias.
- [ ] Mensajes del lanzador en los dos idiomas (hoy salen en español).
- [ ] Guía de uso en inglés.
- [ ] Reglas del agente (`worker-prompt.md`) en el idioma del usuario.

### 5. Sistemas

- [ ] Linux: servicio con systemd y avisos con `notify-send`.
- [ ] Windows: solo vía WSL; documentarlo.

### 6. Calidad

- [ ] Pruebas automáticas: hoy las pruebas son guiones manuales con motores falsos.
- [ ] Integración continua.

## Después

- Sitio y documentación en https://dixi-tower.dixi-project.com/, con una URL por idioma.
- Ícono en la barra de menú de macOS con el número de agentes que esperan.
- Cola continua: que al terminar una tarea se tome sola la siguiente.

## Links

- [README](README.es.md)
- [Guía de uso](docs/uso.md)
