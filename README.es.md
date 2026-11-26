# Dixi Tower

[English](README.md) · **Español**

## Propósito

Dixi Tower es una torre de control local para agentes de código. Lanza sesiones de agentes de código en tu propia máquina (Claude Code, Codex o cualquier agente que abras desde la terminal), cada una en su worktree y su rama de git, y te deja verlas y dirigirlas todas desde un panel web en `http://localhost:4310/`.

Funciona con la suscripción que ya tienes: sin llaves de API, sin servicio en la nube, y nada sale de tu máquina salvo lo que hagan los propios agentes.

> **Estado: alfa, privado.** Por ahora solo macOS. El soporte de Codex todavía no se ha validado con una sesión real. Ver la [hoja de ruta](ROADMAP.md).

## Qué ofrece

- **Un panel para todos los agentes**: búsqueda, filtro por estado y orden por quién te está esperando.
- **Consola en vivo** de cada agente, con enlaces clicables y control por teclado (flechas, Enter, Esc, 1–3).
- **Autocompletado de comandos «/»**: los del motor, los tuyos y los instalados en el proyecto (por ejemplo los `/dixi.*` de [dixi-spec-kit](https://github.com/dixi-project/dixi-spec-kit)).
- **Ciclo completo de la sesión**: lanzar, detener, encender de nuevo (retomando la conversación) y eliminar.
- **Trae tu propio agente**: además de Claude Code y Codex, define como motor cualquier agente de terminal.
- **Archivos y rutas en el mensaje**: arrastra o pega archivos e imágenes, o elige una carpeta, y su ruta se inserta para el agente.
- **Dictado**: mantén presionada la barra espaciadora para hablar en vez de escribir (usa el reconocimiento de voz del navegador).
- **Ajustes por agente**: motor, nivel de autonomía, subagentes permitidos y cuántos, y límites de uso de la cuenta.
- **Barreras**: un agente nunca integra, despliega, publica en la rama base ni lee secretos. Termina en un pull request.

## Requisitos

- macOS, `bash`, Python 3.9 o posterior (solo biblioteca estándar)
- `tmux` y `git`
- Al menos un motor: [Claude Code](https://claude.com/claude-code) o [Codex CLI](https://github.com/openai/codex) con sesión iniciada en tu suscripción, o el tuyo
- Opcional: `gh` (pull requests), `terminal-notifier` (avisos clicables)

## Inicio rápido

Desde un clon de este repositorio:

```sh
./dixi-tower doctor               # revisa requisitos
./dixi-tower servicio instalar    # panel siempre encendido en http://localhost:4310/ (macOS)
./dixi-tower panel                # o bien: el panel dentro de tmux (cualquier sistema)
```

Abre el panel y pulsa **＋ Nuevo agente**. Elige un repositorio de tu carpeta de proyectos (`~/projects` por defecto; se cambia con `DIXI_TOWER_PROJECTS`), escribe una instrucción y lánzalo.

Ejecuta `./dixi-tower` sin argumentos para ver todos los comandos.

## Cómo funciona

Cada agente es una sesión interactiva del motor dentro de una ventana de la sesión tmux `dixi-tower`. Dixi Tower inyecta permisos, hooks y reglas desde fuera, así que el repositorio del proyecto nunca se modifica. Los hooks reportan el estado de cada agente en `~/.dixi-tower/`, y el panel lee esos archivos, git y tmux.

La guía completa (comandos, configuración, piezas internas y seguridad del panel) está en [docs/uso.md](docs/uso.md).

## Seguridad

El panel escucha solo en `127.0.0.1`, rechaza peticiones cuya cabecera `Host` no sea local y exige un token para toda acción que escribe. Quien pueda abrir el panel puede dar instrucciones a tus agentes: no lo expongas por túnel ni proxy.

## Licencia

[MIT](LICENSE) © 2026 Dixi Project.

## Links

- [Hoja de ruta](ROADMAP.md)
- [Registro de cambios](CHANGELOG.md)
- [Guía de uso](docs/uso.md)
