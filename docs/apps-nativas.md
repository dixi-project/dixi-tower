# Tarea: apps de Dixi Tower para macOS, Linux, iOS y Android

## Propósito

Que Dixi Tower se instale y se use como una app, no solo como un comando y una pestaña del navegador. En el escritorio, la app levanta la torre y la muestra; en el móvil, controla una torre que ya corre en un ordenador.

Windows no tendrá app nativa, pero **Dixi Tower sí corre en Windows**: con WSL2, igual que en macOS y Linux, con el panel siempre encendido en el navegador (ver el manual y el servicio de WSL2). Lo que queda fuera es solo la app.

Estado: **sin empezar**. Hay cuenta de Apple Developer para firmar y publicar.

## Lo que no cambia

- **La torre sigue siendo el panel en Python** (`panel.py` y el lanzador). Las apps no lo reescriben: lo traen dentro (escritorio) o se conectan a él (móvil).
- **Dependencias que ninguna app puede traer**: el motor (Claude Code, Codex o uno propio) con **la sesión iniciada por cada usuario**, y `git`. tmux y Python sí se pueden incluir en las apps de escritorio.
- Por eso, toda app de escritorio arranca con un **asistente de primer uso**, que es `dixi-tower doctor` en pantalla: muestra qué falta y cómo conseguirlo.
- **Idiomas**: las apps siguen el idioma del sistema (ES y EN como mínimo), con catálogos de traducción y sin textos fijos en el código, igual que el panel.

## Escritorio

### macOS

App nativa en **Swift**: una ventana con WKWebView y un ícono en la barra de menú.

- **Dentro de la app**: Python (python-build-standalone), el paquete `dixi_tower` y tmux. No se usa Chrome.
- **Al abrir**: registra el servicio de launchd (el mismo que `dixi-tower service install`, pero con las rutas de la app) y espera a que responda `localhost:4310`. El panel sigue vivo aunque se cierre la ventana.
- **Barra de menú**: el número de agentes que esperan (estado `te_necesita`), con un clic abre el agente. Sustituye la entrada «Ícono en la barra de menú» de la hoja de ruta.
- **Avisos** nativos (UserNotifications) en lugar de `terminal-notifier`.
- **Distribución**: `.dmg` **firmado con Developer ID y notarizado**, también por `brew install --cask dixi-tower`, con actualizaciones automáticas (Sparkle). Fuera de la Mac App Store, porque el sandbox no deja lanzar tmux ni los motores.
- **Convivencia**: si ya hay un servicio instalado con `uv`/`pipx`, la app lo detecta y ofrece quedarse con uno solo.

### Linux

Misma idea, con **Tauri** (WebView del sistema, binario pequeño), o una ventana GTK con WebKitGTK si Tauri complica el empaquetado.

- **Servicio**: unidad de usuario de **systemd** (`systemctl --user`). Cubre también la entrada pendiente «servicio siempre encendido con systemd».
- **Distribución**: AppImage y `.deb`; más adelante Flatpak, si su sandbox lo permite.
- tmux y git se declaran como dependencias del paquete y no se incluyen dentro.

## Móvil: control remoto

En iOS y Android no pueden correr tmux ni los motores. La app del móvil es un **control remoto de una torre que corre en un ordenador**: muestra los agentes y su consola, avisa cuando alguien te necesita y deja escribir, aprobar y detener.

### Lo que necesita antes la torre

Hoy el panel **solo escucha en 127.0.0.1**, exige un `Host` local y protege las escrituras con un token de la página (ver «Panel security» en `docs/usage.md`). Para el móvil hace falta, sin debilitar eso:

1. **Emparejamiento**: el panel muestra un código QR con la dirección y una credencial propia del dispositivo, revocable desde el panel. Nunca se reutiliza el token de la página.
2. **Camino de red**, sin abrir puertos a internet. Por orden de preferencia:
   - una red privada tipo Tailscale o WireGuard que el usuario ya tenga;
   - un relé saliente opcional (la torre se conecta hacia fuera y el móvil también), con cifrado de extremo a extremo.
   Escuchar en `0.0.0.0` dentro de la red local solo con permiso explícito y con TLS.
3. **API JSON documentada** para la lista, el estado, la consola (en flujo) y las acciones. Hoy el panel devuelve HTML hecho en el servidor; la API vive a su lado.
4. **Avisos push**: la torre avisa al relé y este usa APNs (iOS) o FCM (Android). Sin relé no hay push, solo avisos con la app abierta.

### iOS

- **SwiftUI**, compartiendo con la app de macOS el modelo de datos y el cliente de la API.
- Pantallas: lista de agentes con su estado, consola en vivo con teclado y comandos «/», aprobar o rechazar, detener y reanudar.
- Publicación en la **App Store** con la cuenta de desarrollador (antes, TestFlight). La revisión de Apple exige que la app sirva de algo sin un servidor propio de Apple: hay que documentar el emparejamiento y dar una cuenta de demostración.

### Android

- **Kotlin + Jetpack Compose**, con las mismas pantallas que iOS.
- Publicación en **Google Play** (cuenta de desarrollador de Google, aún pendiente) y APK firmado en las versiones de GitHub.
- Si mantener dos apps nativas cuesta demasiado: una sola app en **Kotlin Multiplatform** o **Flutter** para iOS y Android. Se decide al empezar el móvil.

## Orden propuesto

1. **PWA del panel** (`manifest.json`, íconos): Chrome y Edge ofrecen instalarla. Es barata y valida el uso «como app».
2. **App de macOS** (firmada y notarizada, cask de Homebrew).
3. **Linux** (Tauri o GTK, systemd, AppImage y `.deb`).
4. **API, emparejamiento y relé** en la torre: es el requisito del móvil.
5. **iOS** (TestFlight, luego App Store).
6. **Android** (Google Play).

## Criterios de terminado (por app)

- Se instala sin terminal en una máquina limpia, y el asistente de primer uso lleva hasta un agente funcionando.
- Pasa `tests/smoke.sh` contra la torre que trae (escritorio) o contra una torre de prueba (móvil).
- Textos en ES y EN según el sistema.
- Firmada y publicada en su canal; las instrucciones de instalación están en el README y en el manual.

## Links

- [Hoja de ruta](../ROADMAP.md)
- [Guía de uso: seguridad del panel](usage.md#panel-security)
