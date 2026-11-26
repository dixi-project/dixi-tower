# Dixi Tower

[English](README.md) · **Español**

## Propósito

Dixi Tower es una torre de control local para agentes de código. Lanza sesiones de Claude Code y de Codex en tu propia máquina, cada una en su worktree y su rama de git, y te deja verlas y dirigirlas todas desde un panel web en `http://localhost:4310/`.

Funciona con la suscripción que ya tienes: sin llaves de API, sin servicio en la nube, y nada sale de tu máquina salvo lo que hagan los propios agentes.

> **Estado: alfa, privado.** Por ahora solo macOS. El soporte de Codex todavía no se ha validado con una sesión real. Ver la [hoja de ruta](ROADMAP.md).

## Qué ofrece

- **Un panel para todos los agentes**: búsqueda, filtro por estado y orden por quién te está esperando.
- **Consola en vivo** de cada agente, con enlaces clicables y control por teclado (flechas, Enter, Esc, 1–3).
- **Autocompletado de comandos «/»**: los del motor, los tuyos y los instalados en el proyecto (por ejemplo los `/dixi.*` de [dixi-spec-kit](https://github.com/dixi-project/dixi-spec-kit)).
- **Ciclo completo de la sesión**: lanzar, detener, encender de nuevo (retomando la conversación) y eliminar.
- **Ajustes por agente**: motor (Claude Code o Codex), nivel de autonomía, subagentes permitidos y cuántos, y límites de uso de la cuenta.
- **Barreras**: un agente nunca integra, despliega, publica en la rama base ni lee secretos. Termina en un pull request.

## Requisitos

- macOS, `bash`, Python 3.9 o posterior (solo biblioteca estándar)
- `tmux` y `git`
- Al menos un motor con sesión iniciada en tu suscripción: [Claude Code](https://claude.com/claude-code) o [Codex CLI](https://github.com/openai/codex)
- Opcional: `gh` (pull requests), `terminal-notifier` (avisos clicables)

## Inicio rápido

Desde un clon de este repositorio:

```sh
./dixi-tower servicio instalar    # panel siempre encendido en http://localhost:4310/
```

Abre el panel y pulsa **＋ Nuevo agente**. Elige un repositorio de tu carpeta de proyectos (`~/projects` por defecto; se cambia con `DIXI_PROYECTOS_DIR`), una tarea o una instrucción libre, y lánzalo.

Ejecuta `./dixi-tower` sin argumentos para ver todos los comandos.

## Cómo funciona

Cada agente es una sesión interactiva del motor dentro de una ventana de la sesión tmux `agentes`. Dixi Tower inyecta permisos, hooks y reglas desde fuera, así que el repositorio del proyecto nunca se modifica. Los hooks reportan el estado de cada agente en `~/.agentes/`, y el panel lee esos archivos, git y tmux.

La guía completa (comandos, configuración, piezas internas y seguridad del panel) está en [docs/uso.md](docs/uso.md).

## Seguridad

El panel escucha solo en `127.0.0.1`, rechaza peticiones cuya cabecera `Host` no sea local y exige un token para toda acción que escribe. Quien pueda abrir el panel puede dar instrucciones a tus agentes: no lo expongas por túnel ni proxy.

## Links

- [Hoja de ruta](ROADMAP.md)
- [Registro de cambios](CHANGELOG.md)
- [Guía de uso](docs/uso.md)
