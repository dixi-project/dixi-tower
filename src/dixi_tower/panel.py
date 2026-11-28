#!/usr/bin/env python3
"""Panel local de Dixi Tower.

Servidor en 127.0.0.1 que muestra, renderizado en el servidor, el estado y la
consola de cada agente (archivos ~/.agentes/estado/*.json, git y tmux) y permite
escribirles, mandarles teclas y detenerlos.

  python3 panel.py [puerto]        →  http://localhost:4310/

Rutas: /  (redirige al idioma del navegador) · /es/ · /en/ · fragmentos /<idioma>/lista,
/<idioma>/agente/<proyecto> y /<idioma>/terminal/<proyecto> · POST /api/accion.

Seguridad: solo escucha en 127.0.0.1, exige que la cabecera Host sea local
(contra DNS rebinding) y, para escribir, un token aleatorio por arranque que
solo conoce la página servida (contra peticiones de otros sitios). El token se
conserva en ~/.agentes/panel.token entre reinicios.
"""
import glob
import html
import json
import os
import re
import secrets
import subprocess
import sys
import threading
import time
from http.server import BaseHTTPRequestHandler, ThreadingHTTPServer
from urllib.parse import quote, unquote

import config
from mensajes import t as tr

DIR = os.path.dirname(os.path.abspath(__file__))
HOME_AG = config.HOME_AG
REGISTRO = os.environ.get("DIXI_AGENTES_REGISTRO", os.path.join(HOME_AG, "proyectos.json"))


def sesion():
    """Sesión tmux de los agentes. Se llama `dixi-tower`; si aún vive una sesión
    `agentes` de antes del cambio de nombre, se sigue usando esa."""
    fija = config.entorno("DIXI_TOWER_SESSION", "DIXI_AGENTES_SESION")
    if fija:
        return fija
    vivas = sh("tmux", "list-sessions", "-F", "#S").splitlines()
    return "agentes" if "agentes" in vivas and "dixi-tower" not in vivas else "dixi-tower"


def nombre_motor(t, motor):
    return t.get("motor_" + motor, motor)

IDIOMAS = ("es", "en")
COLUMNAS, FILAS = 140, 45
TECLAS = {"Enter", "Escape", "Up", "Down", "1", "2", "3"}


def token_persistente():
    """Token de las acciones. Se guarda (solo lectura del dueño) para que reiniciar
    el panel no invalide las páginas que ya están abiertas."""
    ruta = os.path.join(HOME_AG, "panel.token")
    try:
        valor = open(ruta, encoding="utf-8").read().strip()
        if len(valor) >= 24:
            return valor
    except OSError:
        pass
    valor = secrets.token_urlsafe(32)
    os.makedirs(HOME_AG, exist_ok=True)
    descriptor = os.open(ruta, os.O_WRONLY | os.O_CREAT | os.O_TRUNC, 0o600)
    with os.fdopen(descriptor, "w", encoding="utf-8") as fh:
        fh.write(valor)
    return valor


TOKEN = token_persistente()
PUERTO = 4310
CAT = {
    i: json.load(open(os.path.join(DIR, "locales", f"{i}.json"), encoding="utf-8"))
    for i in IDIOMAS
}
_cache = {}
_cache_lock = threading.Lock()


def sh(*args, cwd=None, espera=5, entrada=None):
    try:
        r = subprocess.run(args, capture_output=True, text=True, cwd=cwd, timeout=espera, input=entrada)
        return r.stdout.rstrip() if r.returncode == 0 else ""
    except Exception:
        return ""


def cacheado(clave, vida, fn):
    """Devuelve el valor en caché; si venció, lo recalcula en segundo plano."""
    ahora = time.time()
    with _cache_lock:
        ts, valor, ocupado = _cache.get(clave, (0, None, False))
        if ahora - ts < vida or ocupado:
            return valor
        _cache[clave] = (ts, valor, True)

    def trabajo():
        nuevo = fn()
        with _cache_lock:
            _cache[clave] = (time.time(), nuevo, False)

    threading.Thread(target=trabajo, daemon=True).start()
    return valor


def en_revision(repo, base):
    txt = (sh("git", "-C", repo, "show", f"origin/{base}:tasks/TASKS.md")
           or sh("git", "-C", repo, "show", f"{base}:tasks/TASKS.md"))
    return len(re.findall(r"^\s*- \[r\] ", txt, re.M))


def pull_request(wt, rama):
    crudo = sh("gh", "pr", "view", rama, "--json", "url,number,state", cwd=wt, espera=10)
    try:
        return json.loads(crudo)
    except Exception:
        return {}


def ventanas_vivas():
    return set(sh("tmux", "list-windows", "-t", sesion(), "-F", "#W").splitlines())


def proyectos_con_estado():
    return {os.path.basename(f)[:-5] for f in glob.glob(os.path.join(HOME_AG, "estado", "*.json"))}


# ── Colores de la terminal: secuencias ANSI → HTML ─────────────────────────
PALETA = ["#6b7280", "#ff7b72", "#7ee787", "#e3b341", "#79c0ff", "#d2a8ff", "#76e3ea", "#d7dce4",
          "#8b949e", "#ffa198", "#a5f0b0", "#f2cc60", "#a5d6ff", "#e2c5ff", "#b3f0ff", "#ffffff"]
ESCAPE = re.compile(r"\x1b\[([0-9;?]*)([A-Za-z])|\x1b\][^\x07\x1b]*(?:\x07|\x1b\\)|\x1b[()][A-Za-z0-9]")


def color256(n):
    if n < 16:
        return PALETA[n]
    if n < 232:
        n -= 16
        r, g, b = (n // 36, (n // 6) % 6, n % 6)
        return "#%02x%02x%02x" % tuple(0 if v == 0 else 55 + 40 * v for v in (r, g, b))
    gris = 8 + 10 * (n - 232)
    return "#%02x%02x%02x" % (gris, gris, gris)


URL = re.compile(r"https?://[^\s<>\"'`│┃]+")


def enlazar(trozo):
    """Escapa el texto y convierte las URLs http(s) en enlaces que abren en pestaña nueva."""
    out, pos = [], 0
    for m in URL.finditer(trozo):
        u = m.group(0).rstrip(".,;:!?)]}»…")
        out.append(html.escape(trozo[pos:m.start()], quote=False))
        out.append(f'<a href="{html.escape(u, quote=True)}" target="_blank" rel="noopener noreferrer">{html.escape(u, quote=False)}</a>')
        pos = m.start() + len(u)
    out.append(html.escape(trozo[pos:], quote=False))
    return "".join(out)


def ansi_html(txt):
    out, pos = [], 0
    fg, negrita, tenue = None, False, False

    def emitir(trozo):
        if not trozo:
            return
        estilo = []
        if fg:
            estilo.append(f"color:{fg}")
        if negrita:
            estilo.append("font-weight:600")
        if tenue:
            estilo.append("opacity:.6")
        seguro = enlazar(trozo)
        out.append(f'<span style="{";".join(estilo)}">{seguro}</span>' if estilo else seguro)

    for m in ESCAPE.finditer(txt):
        emitir(txt[pos:m.start()])
        pos = m.end()
        if m.group(2) != "m":
            continue
        try:
            cods = [int(c) if c else 0 for c in (m.group(1) or "0").split(";")]
        except ValueError:
            continue
        i = 0
        while i < len(cods):
            c = cods[i]
            if c == 0:
                fg, negrita, tenue = None, False, False
            elif c == 1:
                negrita = True
            elif c == 2:
                tenue = True
            elif c == 22:
                negrita = tenue = False
            elif 30 <= c <= 37:
                fg = PALETA[c - 30]
            elif 90 <= c <= 97:
                fg = PALETA[c - 90 + 8]
            elif c == 39:
                fg = None
            elif c in (38, 48):
                col = None
                if i + 2 < len(cods) and cods[i + 1] == 5:
                    col = color256(max(0, min(255, cods[i + 2])))
                    i += 2
                elif i + 4 < len(cods) and cods[i + 1] == 2:
                    col = "#%02x%02x%02x" % tuple(max(0, min(255, v)) for v in cods[i + 2:i + 5])
                    i += 4
                if c == 38:
                    fg = col
            i += 1
    emitir(txt[pos:])
    return "".join(out)


def pantalla(proyecto):
    destino = f"{sesion()}:{proyecto}"
    if sh("tmux", "display-message", "-p", "-t", destino, "#{window_width}x#{window_height}") != f"{COLUMNAS}x{FILAS}":
        sh("tmux", "resize-window", "-t", destino, "-x", str(COLUMNAS), "-y", str(FILAS))
    crudo = sh("tmux", "capture-pane", "-e", "-p", "-t", destino, "-S", "-150")
    lineas = [l.rstrip() for l in crudo.splitlines()]
    while lineas and not ESCAPE.sub("", lineas[-1]).strip():
        lineas.pop()
    return "\n".join(lineas)


RANGO = {"te_necesita": 0, "en_pausa": 1, "lanzando": 2, "trabajando": 3, "cerrado": 4}
NOMBRE_OK = re.compile(r"^[\w.@-]+$")   # agente: <proyecto> o <proyecto>@N


_pantallas = {}   # agente → (huella de su pantalla, cuándo cambió por última vez)


def estado_por_pantalla(agente):
    """Para motores sin hooks de estado (Codex): trabajando si su pantalla cambió
    hace poco, en pausa si lleva unos segundos quieta. Es una aproximación."""
    huella = hash(sh("tmux", "capture-pane", "-p", "-t", f"{sesion()}:{agente}"))
    anterior, cambio = _pantallas.get(agente, (None, time.time()))
    if huella != anterior:
        cambio = time.time()
    _pantallas[agente] = (huella, cambio)
    quieta = int(time.time() - cambio)
    return ("trabajando" if quieta < 10 else "en_pausa"), quieta


# Avisos de Claude Code antes de su primer hook (confiar en la carpeta, aceptar
# condiciones): sin esto el panel lo dejaría en «lanzando» mientras te espera.
CLAUDE_ARRANQUE = ("Yes, I trust this folder", "Enter to confirm", "Do you trust the files in this folder?")


def espera_al_arrancar(agente, pantalla=None):
    if pantalla is None:
        pantalla = sh("tmux", "capture-pane", "-p", "-t", f"{sesion()}:{agente}")
    return any(s in pantalla for s in CLAUDE_ARRANQUE)


# Textos con los que Codex pide una respuesta de la persona.
CODEX_ESPERA = ("Would you like to run the following command?", "Would you like to make the following edits?",
                "Press enter to confirm or esc to cancel", "Trust this folder?", "enter continue · esc")


def estado_codex(agente, pantalla=None):
    """Estado de un agente Codex leyendo su pantalla: sus avisos de aprobación y el
    estado de su pie («Working» / «Ready»). También guarda el uso de la cuenta que
    muestra ese pie. Si no reconoce nada, recurre a si la pantalla cambia."""
    if pantalla is None:
        pantalla = sh("tmux", "capture-pane", "-p", "-t", f"{sesion()}:{agente}")
    cola = "\n".join(pantalla.splitlines()[-30:])
    _, quieta = estado_por_pantalla(agente)
    sesion_5h, semana = re.search(r"5h (\d+)% left", cola), re.search(r"weekly (\d+)%", cola)
    if sesion_5h or semana:
        uso = {"actualizado": time.time()}
        if sesion_5h:
            uso["sesion"] = 100 - int(sesion_5h.group(1))
        if semana:
            uso["semana"] = 100 - int(semana.group(1))
        try:
            os.makedirs(os.path.join(HOME_AG, "uso"), exist_ok=True)
            with open(os.path.join(HOME_AG, "uso", f"{agente}.json"), "w", encoding="utf-8") as fh:
                json.dump(uso, fh)
        except OSError:
            pass
    if any(p in cola for p in CODEX_ESPERA):
        return "te_necesita", quieta
    if "esc to interrupt" in cola or "· Working ·" in cola:
        return "trabajando", quieta
    if "· Ready ·" in cola:
        return "en_pausa", quieta
    return estado_por_pantalla(agente)


def ligero():
    """Estado de todos los agentes sin tocar git: sirve para listas de decenas."""
    vivas = ventanas_vivas()
    agentes = []
    for f in sorted(glob.glob(os.path.join(HOME_AG, "estado", "*.json"))):
        try:
            d = json.load(open(f, encoding="utf-8"))
        except Exception:
            continue
        ag = os.path.basename(f)[:-5]
        p = d.get("proyecto") or ag
        viva = ag in vivas
        estado = d.get("estado", "lanzando") if viva else "cerrado"
        edad = max(0, int(time.time() - d.get("actualizado", time.time())))
        motor = (d.get("config") or {}).get("motor") or "claude"
        if viva and motor == "codex":
            estado, edad = estado_codex(ag)
        elif viva and motor == "claude" and estado == "lanzando" and espera_al_arrancar(ag):
            estado = "te_necesita"
        elif viva and motor != "claude":
            estado, edad = estado_por_pantalla(ag)
        agentes.append({
            "agente": ag,
            "proyecto": p,
            "viva": viva,
            "estado": estado if estado in RANGO else "lanzando",
            "titulo": d.get("titulo") or "",
            "tarea": d.get("tarea") or "",
            "rama": d.get("rama") or "",
            "worktree": d.get("worktree") or "",
            "motor": (d.get("config") or {}).get("motor") or "claude",
            "edad": edad,
        })
    agentes.sort(key=lambda a: (RANGO[a["estado"]], -a["edad"], a["agente"]))
    return agentes


def hace(seg, t):
    if seg < 90:
        return t["hace_s"].format(n=seg)
    if seg < 5400:
        return t["hace_min"].format(n=seg // 60)
    return t["hace_h"].format(n=seg // 3600)


def lista(idioma):
    """Fragmento de la barra lateral: filtros por estado y un botón por agente."""
    t = CAT[idioma]
    e = html.escape
    agentes = ligero()
    if not agentes:
        return f'<p class="vacio">{e(t["vacio"])}</p>'
    cuenta = lambda *estados: sum(1 for a in agentes if a["estado"] in estados)
    out = ['<div class="chips">']
    for clave, filtro, clase, n in (
        ("todos", "", "todos", len(agentes)),
        ("resumen_te_necesitan", "te_necesita", "te_necesita", cuenta("te_necesita")),
        ("resumen_en_pausa", "en_pausa", "en_pausa", cuenta("en_pausa")),
        ("resumen_activos", "lanzando,trabajando", "trabajando", cuenta("lanzando", "trabajando")),
        ("resumen_cerrados", "cerrado", "cerrado", cuenta("cerrado")),
    ):
        out.append(f'<button type="button" class="chip e-{clase}" data-filtro="{filtro}" aria-pressed="false"><b>{n}</b> {e(t[clave])}</button>')
    out.append("</div><ul>")
    for a in agentes:
        busca = f'{a["agente"]} {a["titulo"]} {a["tarea"]}'.lower()
        out.append(
            f'<li><button type="button" class="item e-{a["estado"]}" data-p="{e(a["agente"], quote=True)}" '
            f'data-estado="{a["estado"]}" data-rango="{RANGO[a["estado"]]}" data-edad="{a["edad"]}" '
            f'data-nombre="{e(a["agente"].lower(), quote=True)}" data-busca="{e(busca, quote=True)}">'
            f'<i aria-hidden="true"></i><span class="n">{e(a["agente"])}</span>'
            f'<span class="s">{e(t["estado_" + a["estado"]])} · {e(hace(a["edad"], t))} · {e(nombre_motor(t, a["motor"]))}</span>'
            f'<span class="t">{e(a["titulo"])}</span></button></li>'
        )
    out.append(f'</ul><p id="nada" class="vacio" hidden>{e(t["sin_resultados"])}</p>')
    return "\n".join(out)


def ficha(idioma, agente):
    """Fragmento con los datos del agente elegido (aquí sí se consulta git)."""
    t = CAT[idioma]
    e = html.escape
    a = next((x for x in ligero() if x["agente"] == agente), None)
    if a is None:
        return ""
    proyecto = a["proyecto"]
    try:
        conf = json.load(open(REGISTRO, encoding="utf-8")).get(proyecto, {})
    except Exception:
        conf = {}
    base = conf.get("base", "main")
    wt = a["worktree"]
    hay_wt = os.path.isdir(wt)
    commits = ""
    if hay_wt:
        commits = (sh("git", "-C", wt, "rev-list", "--count", f"origin/{base}..HEAD")
                   or sh("git", "-C", wt, "rev-list", "--count", f"{base}..HEAD"))
    sucios = len(sh("git", "-C", wt, "status", "--porcelain").splitlines()) if hay_wt else 0
    filas = [
        (t["tarea"], e(t["sin_tarea"]) if a["tarea"] == "libre" else f"<code>st:{e(a['tarea'])}</code>"),
        (t["rama"], f"<code>{e(a['rama'])}</code>"),
        (t["commits"], e(str(commits or 0))),
        (t["sin_commit"], e(str(sucios))),
        (t["ultima_senal"], e(hace(a["edad"], t))),
    ]
    if conf.get("repo"):
        rev = cacheado(("rev", proyecto), 60, lambda r=conf["repo"], b=base: en_revision(r, b))
        if rev is not None:
            tope = config.global_()["tope_revision"]
            if tope:
                aviso = ' class="alerta"' if rev > tope else ""
                filas.append((t["en_revision"], f"<span{aviso}>{e(t['en_revision_valor'].format(n=rev, max=tope))}</span>"))
            elif rev:
                filas.append((t["en_revision"], e(str(rev))))
    pr = (cacheado(("pr", a["rama"]), 90, lambda w=wt, r=a["rama"]: pull_request(w, r)) if hay_wt and a["rama"] else None) or {}
    url = pr.get("url", "")
    if url.startswith("https://"):
        filas.append((t["pr"], f'<a href="{e(url, quote=True)}" target="_blank" rel="noopener">#{e(str(pr.get("number", "")))} · {e(str(pr.get("state", "")).lower())}</a>'))
    else:
        filas.append((t["pr"], f'<span class="tenue">{e(t["pr_ninguno"])}</span>'))
    conf = config.de_agente(agente)
    filas.append((t["motor"], e(nombre_motor(t, conf["motor"]))))
    filas.append((t["autonomia"], e(t["autonomia_" + conf["autonomia"]])))
    u = config.uso(agente) if conf["motor"] in config.MOTORES else {}
    partes = []
    for clave, tope in (("semana", conf["limites"]["semana"]), ("sesion", conf["limites"]["sesion"])):
        if isinstance(u.get(clave), (int, float)):
            if conf["motor"] != "claude":   # con Codex el uso se muestra, pero el límite no se puede hacer cumplir
                partes.append(f'{e(t["uso_" + clave])} {u[clave]:.0f}%')
                continue
            limite = t["uso_limite"].format(n=tope) if tope else t["uso_sin_limite"]
            partes.append(f'{e(t["uso_" + clave])} {u[clave]:.0f}% <span class="tenue">({e(limite)})</span>')
    if isinstance(u.get("contexto_libre"), (int, float)):
        partes.append(e(t["uso_contexto"].format(n=f'{u["contexto_libre"]:.0f}')))
    if partes and conf["motor"] != "claude":
        partes.append(f'<span class="tenue">{e(t["uso_sin_control"])}</span>')
    if partes:
        filas.append((t["uso"], " · ".join(partes)))
    elif conf["motor"] != "claude":
        clave = "uso_pendiente" if conf["motor"] == "codex" else "uso_codex"
        filas.append((t["uso"], f'<span class="tenue">{e(t[clave])}</span>'))
    sub = conf["subagentes"]
    filas.append((t["subagentes"], e(t["subagentes_max"].format(n=sub["max"]) if sub["permitidos"] else t["subagentes_no"])))
    tope = config.limite_alcanzado(agente, idioma) if conf["motor"] == "claude" else ""
    aviso = f'<p class="tope" role="status">{e(t["tope_alcanzado"].format(motivo=tope))}</p>' if tope else ""
    return (
        f'<div class="ficha e-{a["estado"]}" data-viva="{1 if a["viva"] else 0}">'
        f'<header><h2>{e(a["agente"])}</h2><span class="estado"><i aria-hidden="true"></i>{e(t["estado_" + a["estado"]])}</span>'
        f'<button type="button" class="b" data-ajustes>{e(t["ajustes"])}</button></header>{aviso}'
        f'<p class="titulo">{e(a["titulo"])}</p>'
        "<dl>" + "".join(f"<div><dt>{e(k)}</dt><dd>{v}</dd></div>" for k, v in filas) + "</dl></div>"
    )


SUGERIDA = re.compile(r"^(?:\x1b\[[0-9;]*m)*❯\xa0\x1b\[2m([^\x1b]+)\x1b\[0m\s*$")


def sugerencia(crudo):
    """Texto que el agente propone en su caja de entrada (aparece atenuado)."""
    for linea in reversed(crudo.split("\n")[-14:]):
        if "❯" in linea:
            m = SUGERIDA.match(linea)
            texto = m.group(1).strip() if m else ""
            return "" if texto.startswith("Try ") else texto[:500]
    return ""


def terminal(idioma, proyecto):
    """Devuelve (HTML de la consola, sugerencia del agente)."""
    if proyecto in proyectos_con_estado() and proyecto in ventanas_vivas():
        crudo = pantalla(proyecto)
        return ansi_html(crudo), sugerencia(crudo)
    return f'<span style="opacity:.6">{html.escape(CAT[idioma]["pantalla_vacia"])}</span>', ""


TAREA_OK = re.compile(r"^[0-9a-f]{6,40}$")
COMANDO_OK = re.compile(r"^[\w.:-]{1,80}$")


def _descripcion(ruta):
    """`description:` del encabezado de un comando o skill, si lo tiene."""
    try:
        with open(ruta, encoding="utf-8", errors="replace") as fh:
            cabeza = fh.read(3000)
    except OSError:
        return ""
    m = re.search(r"^description:\s*[\"']?(.+?)[\"']?\s*$", cabeza, re.M) if cabeza.startswith("---") else None
    return m.group(1).strip()[:160] if m else ""


def _de_carpeta(base, origen):
    """Comandos (`commands/**/*.md`) y skills (`skills/<nombre>/SKILL.md`) de una carpeta .claude."""
    encontrados = []
    raiz = os.path.join(base, "commands")
    for carpeta, _, archivos in os.walk(raiz):
        for a in sorted(archivos):
            if a.endswith(".md"):
                rel = os.path.relpath(os.path.join(carpeta, a), raiz)[:-3].replace(os.sep, ":")
                if COMANDO_OK.match(rel):
                    encontrados.append({"c": "/" + rel, "d": _descripcion(os.path.join(carpeta, a)), "o": origen})
    raiz = os.path.join(base, "skills")
    try:
        nombres = sorted(os.listdir(raiz))
    except OSError:
        nombres = []
    for n in nombres:
        ficha_skill = os.path.join(raiz, n, "SKILL.md")
        if COMANDO_OK.match(n) and os.path.isfile(ficha_skill):
            encontrados.append({"c": "/" + n, "d": _descripcion(ficha_skill), "o": origen})
    return encontrados


def comandos(idioma, agente):
    """Comandos «/» que se pueden escribirle a un agente: los del proyecto (su
    carpeta .claude, donde también vive lo que instala un kit como dixi-spec-kit),
    los del usuario y los propios de su motor."""
    a = next((x for x in ligero() if x["agente"] == agente), None)
    if a is None:
        return []
    motor = a["motor"]
    lista = []
    if motor == "claude":
        if os.path.isdir(a["worktree"]):
            lista += _de_carpeta(os.path.join(a["worktree"], ".claude"), "proyecto")
        lista += _de_carpeta(os.path.expanduser("~/.claude"), "usuario")
    try:
        propios = json.load(open(os.path.join(DIR, "comandos.json"), encoding="utf-8")).get(motor, [])
    except Exception:
        propios = []
    lista += [{"c": p["c"], "d": p.get(idioma) or p.get("es", ""), "o": "motor"} for p in propios]
    vistos, unicos = set(), []
    for c in lista:                      # gana el primero: proyecto, luego usuario, luego motor
        if c["c"] not in vistos:
            vistos.add(c["c"])
            unicos.append(c)
    return unicos


def carpeta():
    """Carpeta de proyectos en uso. Se consulta en cada petición: cambiarla en Configuración no pide reiniciar."""
    return config.carpeta_proyectos()


def carpetas():
    """Repos git que son hijos directos de la carpeta de proyectos."""
    base = carpeta()
    try:
        nombres = sorted(os.listdir(base), key=str.lower) if base else []
    except OSError:
        return []
    return [n for n in nombres
            if NOMBRE_OK.match(n) and "@" not in n and not n.startswith(".")
            and os.path.exists(os.path.join(base, n, ".git"))]


def info_carpeta():
    """La carpeta de proyectos tal como la ve Configuración › Proyectos."""
    efectiva, origen = config.carpeta_proyectos(), config.origen_carpeta()
    modo = ("ninguna" if not efectiva else "carpeta") if origen == "config" else "predeterminada"
    entorno = next((v for v in ("DIXI_TOWER_PROJECTS", "DIXI_PROYECTOS_DIR") if os.environ.get(v)), "predeterminada")
    disponible = bool(efectiva) and os.path.isdir(efectiva)
    return {"modo": modo, "valor": efectiva if modo == "carpeta" else "", "efectiva": efectiva,
            "origen": origen, "disponible": disponible, "elegir": modo == "predeterminada" and not disponible,
            "base": config.entorno("DIXI_TOWER_PROJECTS", "DIXI_PROYECTOS_DIR", os.path.expanduser("~/projects")),
            "base_origen": entorno}


def validar_ruta_repo(ruta):
    """(ruta real, None) si `ruta` es la raíz de un repo git fuera de la carpeta de
    datos; si no, (None, clave del mensaje). Las mismas reglas que registro.py."""
    if (not isinstance(ruta, str) or not ruta or len(ruta) > 1024 or not os.path.isabs(ruta)
            or any(ord(c) < 32 or ord(c) == 127 for c in ruta)):
        return None, "p_ruta_invalida"
    real = os.path.realpath(ruta)
    if not os.path.exists(os.path.join(real, ".git")) or not os.path.isdir(real):
        return None, "p_ruta_invalida"
    datos = os.path.realpath(HOME_AG)
    if real == datos or real.startswith(datos + os.sep):
        return None, "p_ruta_en_datos"
    return real, None


def opciones_proyecto(idioma):
    e = html.escape
    return (f'<option value="">{e(CAT[idioma]["elige_proyecto"])}</option>'
            + "".join(f'<option value="{e(n, quote=True)}">{e(n)}</option>' for n in carpetas()))


def opciones_tarea(idioma, repo):
    """Tareas [ ] con id del backlog del proyecto, leídas de su copia local (sin red)."""
    e = html.escape
    out = [f'<option value="libre">{e(CAT[idioma]["tarea_libre"])}</option>']
    txt = ""
    for ref in ("origin/HEAD", "origin/main", "origin/master", "HEAD"):
        txt = sh("git", "-C", repo, "show", f"{ref}:tasks/TASKS.md")
        if txt:
            break
    filas = []
    for n, linea in enumerate(txt.splitlines()):
        m = re.match(r"^\s*- \[ \] (.*)$", linea)
        st = m and re.search(r"<!--\s*st:([0-9a-f]+)\s*-->", m.group(1))
        if not st or "bloquead" in linea.lower():
            continue
        tit = re.search(r"\*\*(.+?)\*\*", m.group(1))
        pri = re.search(r"_\(P(\d)\)_", m.group(1))
        filas.append((int(pri.group(1)) if pri else 9, n, st.group(1), tit.group(1) if tit else m.group(1)))
    for pri, _, ident, titulo in sorted(filas)[:80]:
        marca = f"P{pri} · " if pri < 9 else ""
        out.append(f'<option value="{ident}">{e(marca + titulo[:110])}</option>')
    return "".join(out)


def lanzar(datos):
    i = datos.get("_idioma")
    tarea, instr = datos.get("tarea") or "libre", datos.get("instruccion") or ""
    if datos.get("ruta") is not None:
        destino, error = validar_ruta_repo(datos["ruta"])
        if error:
            return 400, tr(error, i)
        p = re.sub(r"[^\w-]", "-", os.path.basename(destino)).strip("-") or "repo"
    else:
        p = datos.get("proyecto")
        if not isinstance(p, str) or p not in carpetas():
            return 400, tr("p_proyecto_invalido", i)
        destino = os.path.join(carpeta(), p)
    if not isinstance(tarea, str) or not (tarea == "libre" or TAREA_OK.match(tarea)):
        return 400, tr("p_tarea_invalida", i)
    if not isinstance(instr, str) or len(instr) > 8000:
        return 400, tr("p_instruccion_invalida", i)
    instr = "".join(ch for ch in instr if ch in "\n\t" or ord(ch) >= 32).strip()
    if tarea == "libre" and not instr:
        return 400, tr("falta_instruccion", i)
    args = ["bash", os.path.join(DIR, "agentes.sh"), "lanzar", destino, tarea]
    if datos.get("motor") in config.motores_disponibles():
        args += ["--motor", datos["motor"]]
    if datos.get("autonomia") in config.AUTONOMIAS:
        args += ["--autonomia", datos["autonomia"]]
    if datos.get("forzar") is True:
        args.append("--forzar")
    if instr:
        ruta = os.path.join(HOME_AG, "run", f"{p}.{int(time.time() * 1000)}.instruccion.txt")
        os.makedirs(os.path.dirname(ruta), exist_ok=True)
        with open(ruta, "w", encoding="utf-8") as fh:
            fh.write(instr + "\n")
        args += ["--instruccion", ruta]
    try:
        r = subprocess.run(args, capture_output=True, text=True, timeout=240, env=entorno_idioma(datos))
    except subprocess.TimeoutExpired:
        return 500, tr("p_lanzar_lento", i)
    if r.returncode != 0:
        lineas = [l for l in r.stderr.strip().splitlines() if l.strip()]
        return 409, (lineas[-1] if lineas else tr("p_lanzar_fallo", i))[:400]
    creado = next((l[7:].strip() for l in r.stdout.splitlines() if l.startswith("AGENTE=")), p)
    return 200, creado


ADJUNTO_MAX = 25 * 1024 * 1024


def guardar_adjunto(agente, nombre, datos):
    """Guarda una copia de un archivo soltado o pegado en el panel y devuelve su
    ruta. Una página web no conoce la ruta original de lo que se le suelta, así
    que el agente trabaja sobre esta copia, en la carpeta de datos."""
    limpio = re.sub(r"[^\w.\-]", "_", os.path.basename(nombre or ""))[:100].lstrip(".") or "archivo"
    carpeta = os.path.join(HOME_AG, "adjuntos", agente)
    os.makedirs(carpeta, exist_ok=True)
    base, n = time.strftime("%m%d-%H%M%S"), 1
    ruta = os.path.join(carpeta, f"{base}-{limpio}")
    while os.path.exists(ruta):
        n += 1
        ruta = os.path.join(carpeta, f"{base}-{n}-{limpio}")
    with open(ruta, "wb") as fh:
        fh.write(datos)
    return ruta


def explorar(ruta, i=None):
    """Lista una carpeta del usuario para elegir una ruta real. Solo dentro de su
    carpeta personal y sin archivos ocultos (donde suelen vivir llaves y secretos)."""
    casa = os.path.realpath(os.path.expanduser("~"))
    actual = os.path.realpath(ruta if isinstance(ruta, str) and ruta else (carpeta() or casa))
    if not os.path.isdir(actual):
        actual = casa
    if actual != casa and not actual.startswith(casa + os.sep):
        return 403, tr("p_fuera_de_casa", i)
    try:
        nombres = sorted(os.listdir(actual), key=str.lower)
    except OSError:
        return 403, tr("p_sin_lectura", i)
    carpetas, archivos = [], []
    for n in nombres:
        if not n.startswith("."):
            (carpetas if os.path.isdir(os.path.join(actual, n)) else archivos).append(n)
    return 200, json.dumps({"ruta": actual, "padre": os.path.dirname(actual) if actual != casa else None,
                            "carpetas": carpetas[:500], "archivos": archivos[:500]}, ensure_ascii=False)


def entorno_idioma(datos):
    """Entorno para el lanzador, con el idioma de la página que pidió la acción."""
    return {**os.environ, "DIXI_TOWER_LANG": datos.get("_idioma") or "es"}


def accion(datos):
    """Ejecuta una acción de la página. Devuelve (código HTTP, mensaje)."""
    i = datos.get("_idioma")
    if datos.get("explorar") is True:
        return explorar(datos.get("ruta"), i)
    if datos.get("lanzar") is True:
        return lanzar(datos)
    if datos.get("tareas") is True:
        repo, error = validar_ruta_repo(datos.get("ruta"))
        return (400, tr(error, i)) if error else (200, opciones_tarea(i or "es", repo))
    if datos.get("guardar_config") is True:
        nueva, ag = datos.get("config"), datos.get("agente")
        if not isinstance(nueva, dict):
            return 400, tr("p_config_invalida", i)
        if ag is None:
            try:
                config.guardar_global(nueva)
            except ValueError as ex:
                return 400, tr(ex.args[0] if ex.args and ex.args[0] in ("p_carpeta_invalida", "p_tablero_invalido") else "p_config_invalida", i)
            return 200, "guardada"
        if not isinstance(ag, str) or not NOMBRE_OK.match(ag) or ag not in proyectos_con_estado():
            return 404, tr("p_agente_desconocido", i)
        config.guardar_agente(ag, {k: v for k, v in nueva.items() if k not in ("carpeta_proyectos", "tablero")})
        return 200, "guardada"
    orden = "reanudar" if datos.get("reanudar") is True else "eliminar" if datos.get("eliminar") is True else None
    if orden:
        ag = datos.get("proyecto")
        if not isinstance(ag, str) or not NOMBRE_OK.match(ag) or ag not in proyectos_con_estado():
            return 404, tr("p_agente_desconocido", i)
        try:
            r = subprocess.run(["bash", os.path.join(DIR, "agentes.sh"), orden, ag], capture_output=True, text=True, timeout=90,
                               env=entorno_idioma(datos))
        except subprocess.TimeoutExpired:
            return 500, tr("p_lento", i)
        if r.returncode != 0:
            lineas = [l for l in r.stderr.strip().splitlines() if l.strip()]
            return 409, (lineas[-1] if lineas else tr("p_fallo", i))[:400]
        return 200, orden
    p = datos.get("proyecto")
    if not isinstance(p, str) or p not in proyectos_con_estado() or p not in ventanas_vivas():
        return 404, tr("p_sin_ventana", i)
    destino = f"{sesion()}:{p}"
    if datos.get("detener") is True:
        subprocess.run(["bash", os.path.join(DIR, "agentes.sh"), "detener", p], capture_output=True, timeout=15)
        return 200, "detenido"
    tecla = datos.get("tecla")
    if tecla is not None:
        if tecla not in TECLAS:
            return 400, tr("p_tecla", i)
        subprocess.run(["tmux", "send-keys", "-t", destino, tecla], capture_output=True, timeout=5)
        return 200, "tecla enviada"
    texto = datos.get("texto")
    if isinstance(texto, str) and texto.strip() and len(texto) <= 8000:
        limpio = "".join(ch for ch in texto.strip() if ch in "\n\t" or ord(ch) >= 32)
        # Pegado entre corchetes: los saltos de línea llegan como texto, no como envíos.
        subprocess.run(["tmux", "load-buffer", "-b", "panel-web", "-"], input=limpio, text=True, capture_output=True, timeout=5)
        subprocess.run(["tmux", "paste-buffer", "-p", "-d", "-b", "panel-web", "-t", destino], capture_output=True, timeout=5)
        time.sleep(0.3)
        subprocess.run(["tmux", "send-keys", "-t", destino, "Enter"], capture_output=True, timeout=5)
        return 200, "texto enviado"
    return 400, tr("p_peticion", i)


CSS = """
:root{--fondo:#f5f6f8;--panel:#fff;--texto:#1c2330;--tenue:#667085;--borde:#e2e5ea;
--azul:#1f5fc4;--ambar:#b25e00;--rojo:#c0271d;--gris:#7a8494;--codigo:#f0f2f5;--sobre-azul:#fff;--elegido:#e8f0fd}
@media (prefers-color-scheme:dark){:root{--fondo:#11141a;--panel:#1a1f28;--texto:#e7eaf0;
--tenue:#98a2b3;--borde:#2c333f;--azul:#6ea8ff;--ambar:#f0a94a;--rojo:#ff7b6e;--gris:#8b95a5;--codigo:#232a35;--sobre-azul:#0d1117;--elegido:#22304a}}
*{box-sizing:border-box}
[hidden]{display:none!important}
html,body{height:100%}
body{margin:0;background:var(--fondo);color:var(--texto);
font:14px/1.45 -apple-system,BlinkMacSystemFont,"Segoe UI",Roboto,sans-serif}
.app{display:grid;grid-template-columns:330px minmax(0,1fr);height:100vh}
aside{display:flex;flex-direction:column;min-height:0;background:var(--panel);border-right:1px solid var(--borde)}
.marca{padding:16px 16px 10px}
h1{margin:0;font-size:18px;letter-spacing:-.01em;display:flex;align-items:center;gap:8px}
.marca p{margin:2px 0 0;color:var(--tenue);font-size:12.5px}
.controles{display:grid;gap:8px;padding:0 16px 12px}
input[type=search],input[type=text],input[type=url],select,textarea{width:100%;padding:8px 10px;border:1px solid var(--borde);border-radius:6px;
background:var(--fondo);color:var(--texto);font:13.5px/1.4 inherit;font-family:inherit}
.controles label{display:grid;gap:3px;color:var(--tenue);font-size:12px}
#lado{flex:1;min-height:0;overflow-y:auto;padding:0 8px 12px;border-top:1px solid var(--borde)}
.chips{display:flex;flex-wrap:wrap;gap:6px;padding:12px 8px 10px}
.chip{font-size:12px;padding:5px 9px;border-radius:999px;border:1px solid var(--borde);background:transparent;color:var(--texto);cursor:pointer}
.chip b{color:var(--c,var(--texto));font-variant-numeric:tabular-nums}
.chip[aria-pressed=true]{background:var(--elegido);border-color:var(--azul)}
#lado ul{list-style:none;margin:0;padding:0;display:grid;gap:2px}
.item{display:grid;grid-template-columns:14px minmax(0,1fr);gap:1px 8px;width:100%;text-align:left;padding:8px 10px;
border:0;border-left:3px solid transparent;border-radius:6px;background:transparent;color:var(--texto);cursor:pointer;font:inherit}
.item:hover{background:var(--fondo)}
.item[aria-current=true]{background:var(--elegido);border-left-color:var(--azul)}
.item i{grid-row:1/4;width:9px;height:9px;border-radius:50%;background:var(--c);margin-top:6px}
.item .n{font-weight:600;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.item .s{font-size:12px;color:var(--c)}
.item .t{font-size:12px;color:var(--tenue);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.e-lanzando,.e-trabajando{--c:var(--azul)}.e-en_pausa{--c:var(--ambar)}
.e-te_necesita{--c:var(--rojo)}.e-cerrado{--c:var(--gris)}
.e-trabajando i,.e-lanzando i{animation:pulso 1.6s ease-in-out infinite}
@keyframes pulso{50%{opacity:.25}}
@media (prefers-reduced-motion:reduce){i{animation:none!important}}
.pie{padding:10px 16px;border-top:1px solid var(--borde);color:var(--tenue);font-size:12px;display:grid;gap:4px}
.pie a{color:var(--azul);text-decoration:none}
.pie nav a[aria-current]{color:var(--texto);font-weight:600}
main{display:flex;flex-direction:column;min-width:0;min-height:0;padding:14px 18px 14px}
#fuera{display:none;margin:0 0 10px;padding:8px 12px;border:1px solid var(--rojo);border-radius:8px;color:var(--rojo)}
#fuera.visible{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;justify-content:space-between}
#vacio{margin:auto;color:var(--tenue)}
#detalle{display:flex;flex-direction:column;flex:1;min-height:0}
.ficha header{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center}
h2{margin:0;font-size:17px}
.estado{display:inline-flex;align-items:center;gap:7px;color:var(--c);font-weight:600;font-size:13px}
.estado i{width:9px;height:9px;border-radius:50%;background:var(--c)}
.titulo{margin:4px 0 8px}
dl{margin:0;display:flex;flex-wrap:wrap;gap:6px 22px}
dt{color:var(--tenue);font-size:11.5px}
dd{margin:0;font-size:13px;overflow-wrap:anywhere;font-variant-numeric:tabular-nums}
code{font:12px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--codigo);padding:1px 5px;border-radius:4px}
.ficha a{color:var(--azul);text-decoration:none}
.alerta{color:var(--rojo);font-weight:600}.tenue,.vacio{color:var(--tenue)}
.vacio{padding:12px 8px;font-size:13px}
.barra{display:flex;align-items:center;justify-content:space-between;gap:12px;margin:12px 0 6px}
h3{margin:0;font-size:11.5px;font-weight:600;color:var(--tenue);text-transform:uppercase;letter-spacing:.05em}
.letra{display:inline-flex;gap:6px;align-items:center;color:var(--tenue);font-size:12px}
#term{flex:1;min-height:120px;margin:0;padding:12px 14px;background:#0d1117;color:#d7dce4;border-radius:8px 8px 0 0;
overflow:auto;font:12px/1.4 ui-monospace,SFMono-Regular,Menlo,monospace;white-space:pre;tab-size:8}
#consola{background:var(--codigo);border-radius:0 0 8px 8px;padding:10px;position:relative}
#sugerencias{position:absolute;left:10px;right:10px;bottom:calc(100% - 4px);margin:0;padding:4px;list-style:none;max-height:300px;overflow-y:auto;
background:var(--panel);border:1px solid var(--borde);border-radius:8px;box-shadow:0 8px 24px rgba(0,0,0,.28);z-index:5}
#sugerencias li{display:grid;grid-template-columns:minmax(120px,max-content) minmax(0,1fr) max-content;gap:12px;align-items:baseline;padding:6px 9px;border-radius:5px;cursor:pointer;font-size:13px}
#sugerencias li[aria-selected=true]{background:var(--elegido)}
#sugerencias b{font:600 12.5px ui-monospace,SFMono-Regular,Menlo,monospace}
#sugerencias span{color:var(--tenue);overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
#sugerencias small{color:var(--tenue);font-size:11px}
#consola textarea{display:block;resize:vertical;min-height:48px;background:var(--panel)}
.botones{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;margin-top:8px}
.teclas{display:inline-flex;flex-wrap:wrap;gap:6px;align-items:center;font-size:12.5px}
button.b{font:13px/1 inherit;font-family:inherit;padding:7px 10px;border-radius:6px;border:1px solid var(--borde);
background:var(--panel);color:var(--texto);cursor:pointer}
button.b:hover{border-color:var(--tenue)}
button.primario{background:var(--azul);border-color:var(--azul);color:var(--sobre-azul);font-weight:600;padding:7px 18px}
button.peligro{margin-left:auto;color:var(--rojo)}
button.peligro.armado{background:var(--rojo);border-color:var(--rojo);color:var(--sobre-azul)}
:focus-visible{outline:2px solid var(--azul);outline-offset:1px}
#term:focus{box-shadow:0 0 0 2px var(--azul)}
#term a{color:inherit;text-decoration:underline;text-decoration-color:#79c0ff;text-underline-offset:2px}
#term a:hover{color:#79c0ff}
.ayuda{margin:8px 0 0;font-size:12px;color:var(--tenue)}
#abrir-nuevo{padding:9px 12px}
#consola.soltar{outline:2px dashed var(--azul);outline-offset:-2px}
#ayuda-adjunto{color:var(--ambar)}
#ex-ruta{font:12.5px ui-monospace,SFMono-Regular,Menlo,monospace;background:var(--codigo);padding:6px 9px;border-radius:6px;overflow-wrap:anywhere;margin-top:12px}
#ex-lista{list-style:none;margin:10px 0 0;padding:0;max-height:46vh;overflow-y:auto;border:1px solid var(--borde);border-radius:8px}
#ex-lista button{display:block;width:100%;text-align:left;padding:7px 11px;border:0;border-bottom:1px solid var(--borde);background:transparent;color:var(--texto);font:13px/1.3 inherit;font-family:inherit;cursor:pointer}
#ex-lista li:last-child button{border-bottom:0}
#ex-lista button:hover{background:var(--elegido)}
#ex-lista .ex-carpeta{font-weight:600}
#ex-error{color:var(--rojo)}
#dictar{display:inline-flex;align-items:center;gap:6px}
#dictar.grabando{background:var(--rojo);border-color:var(--rojo);color:var(--sobre-azul)}
#ayuda-dictado{color:var(--rojo)}
input[type=number]{width:100%;padding:8px 10px;border:1px solid var(--borde);border-radius:6px;background:var(--fondo);color:var(--texto);font:13.5px/1.4 inherit;font-family:inherit}
.par{display:grid;grid-template-columns:1fr 1fr;gap:0 14px}
.ficha header .b{margin-left:auto;padding:5px 10px;font-size:12px}
.tope{margin:8px 0 0;padding:8px 12px;border:1px solid var(--ambar);border-radius:8px;color:var(--ambar);font-size:13px}
#apagado{display:flex;flex-wrap:wrap;gap:10px 16px;align-items:center;background:var(--codigo);border-radius:0 0 8px 8px;padding:12px;font-size:13px}
#r-error{color:var(--rojo);flex-basis:100%}
#aviso-carpeta{display:flex;flex-wrap:wrap;gap:8px 14px;align-items:center;justify-content:space-between;margin:0 0 10px;padding:8px 12px;border:1px solid var(--ambar);border-radius:8px}
#aviso-carpeta[hidden]{display:none}
dialog{border:1px solid var(--borde);border-radius:12px;background:var(--panel);color:var(--texto);padding:20px 22px;width:min(580px,92vw)}
dialog::backdrop{background:rgba(0,0,0,.5)}
dialog p{margin:6px 0 0;font-size:13px}
dialog label{display:grid;gap:4px;margin-top:14px;font-size:12.5px;color:var(--tenue)}
dialog label.fila{display:flex;gap:8px;align-items:center;color:var(--texto)}
dialog textarea{resize:vertical}
.pestanas{display:flex;gap:4px;margin-top:14px;border-bottom:1px solid var(--borde)}
.pestanas button{font:13px/1 inherit;font-family:inherit;padding:8px 12px;border:0;border-bottom:2px solid transparent;background:transparent;color:var(--tenue);cursor:pointer}
.pestanas button[aria-selected=true]{color:var(--texto);font-weight:600;border-bottom-color:var(--azul)}
.ruta-fila{display:flex;gap:8px}.ruta-fila input{flex:1}
dialog fieldset{border:0;padding:0;margin:14px 0 0}dialog legend{padding:0;font-size:12.5px;color:var(--tenue)}
#n-error{color:var(--rojo)}
dialog .botones{justify-content:flex-end;margin-top:18px}
button:disabled,select:disabled{opacity:.55;cursor:default}
@media (max-width:820px){.app{grid-template-columns:1fr;height:auto}aside{max-height:45vh}main{height:100vh}}
"""

JS = """
(function(){
  function $(id){return document.getElementById(id);}
  var lang=document.documentElement.lang,token=document.querySelector('meta[name="panel-token"]').content,
      lado=$('lado'),ficha=$('ficha'),term=$('term'),form=$('consola'),txt=form.querySelector('textarea'),
      filtro=$('filtro'),orden=$('orden'),fuera=$('fuera'),reloj=$('reloj'),detalle=$('detalle'),vacio=$('vacio'),
      parar=form.querySelector('[data-detener]');
  var sel=null,borradores={},filtroEstado='',armado=false,temporizador=null,propuesta='',ultimo=null,pulsando=false,enfocar=false,
      tam=parseInt(localStorage.getItem('torre.letra')||'12',10)||12;
  orden.value=localStorage.getItem('torre.orden')||'atencion';
  if(!orden.value)orden.value='atencion';

  function hora(){reloj.textContent=new Intl.DateTimeFormat(lang,{timeStyle:'medium'}).format(new Date());}
  function bien(){fuera.classList.remove('visible');hora();}
  function mal(){fuera.classList.add('visible');}
  function traer(ruta){return fetch(ruta,{cache:'no-store'}).then(function(r){if(!r.ok)throw 0;return r.text();});}
  function letra(d){tam=Math.max(8,Math.min(18,tam+d));term.style.fontSize=tam+'px';localStorage.setItem('torre.letra',tam);}
  function items(){return [].slice.call(lado.querySelectorAll('.item'));}
  function visibles(){return items().filter(function(b){return !b.parentNode.hidden;});}
  function sugerir(s){propuesta=s||'';txt.placeholder=propuesta?txt.dataset.sugerida.replace('{texto}',function(){return propuesta;}):txt.dataset.base;}
  function armar(si){armado=si;parar.classList.toggle('armado',si);parar.textContent=si?parar.dataset.confirmar:parar.dataset.normal;}

  function aplicar(){
    var ul=lado.querySelector('ul');if(!ul)return;
    var q=filtro.value.trim().toLowerCase(),modo=orden.value,lis=[].slice.call(ul.children),n=0,
        estados=filtroEstado?filtroEstado.split(','):null;
    lis.sort(function(a,b){
      var x=a.firstElementChild.dataset,y=b.firstElementChild.dataset;
      if(modo==='nombre')return x.nombre.localeCompare(y.nombre);
      if(modo==='reciente')return (x.edad-y.edad)||x.nombre.localeCompare(y.nombre);
      return (x.rango-y.rango)||(y.edad-x.edad)||x.nombre.localeCompare(y.nombre);
    });
    lis.forEach(function(li){
      var b=li.firstElementChild,d=b.dataset,
          ok=(!q||d.busca.indexOf(q)>-1)&&(!estados||estados.indexOf(d.estado)>-1);
      li.hidden=!ok;if(ok)n++;
      b.setAttribute('aria-current',d.p===sel?'true':'false');
      ul.appendChild(li);
    });
    [].forEach.call(lado.querySelectorAll('.chip'),function(c){
      c.setAttribute('aria-pressed',c.dataset.filtro===filtroEstado?'true':'false');});
    var nada=$('nada');if(nada)nada.hidden=n>0;
  }

  function elegir(p){
    if(!p||p===sel)return;
    if(sel)borradores[sel]=txt.value;
    sel=p;txt.value=borradores[p]||'';armar(false);sugerir('');cerrarSug();cargarComandos(p);clearTimeout(temporizador);
    history.replaceState(null,'','#'+encodeURIComponent(p));
    vacio.hidden=true;detalle.hidden=false;ficha.innerHTML='';term.innerHTML='';ultimo=null;$('apagado').hidden=true;$('r-error').hidden=true;clearTimeout(tEl);armarEl(false);
    aplicar();cargarFicha();cargarTerm(true);
    var b=items().filter(function(x){return x.dataset.p===p;})[0];
    if(b)b.scrollIntoView({block:'nearest'});
    enfocar=true;if(!form.hidden)txt.focus({preventScroll:true});
  }

  function cargarLista(){
    return traer('lista').then(function(h){
      var arriba=lado.scrollTop;
      lado.innerHTML=h;aplicar();lado.scrollTop=arriba;
      var nombres=items().map(function(b){return b.dataset.p;});
      if(!sel||nombres.indexOf(sel)<0){
        var pedido=decodeURIComponent(location.hash.slice(1)),v=visibles();
        sel=null;
        if(nombres.indexOf(pedido)>-1)elegir(pedido);
        else if(v.length)elegir(v[0].dataset.p);
        else{detalle.hidden=true;vacio.hidden=false;}
      }
      bien();
    }).catch(mal);
  }
  function cargarFicha(){
    if(!sel)return;var p=sel;
    traer('agente/'+encodeURIComponent(p)).then(function(h){
      if(p!==sel)return;
      ficha.innerHTML=h;
      var viva=!!(ficha.firstElementChild&&ficha.firstElementChild.dataset.viva==='1');
      form.hidden=!viva;$('apagado').hidden=viva;
      if(enfocar){enfocar=false;if(!form.hidden&&!$('nuevo').open)txt.focus({preventScroll:true});}
    }).catch(mal);
  }
  function cargarTerm(alFondo){
    if(!sel)return;var p=sel,s=window.getSelection();
    if(!alFondo&&String(s).length&&term.contains(s.anchorNode))return;
    fetch('terminal/'+encodeURIComponent(p),{cache:'no-store'}).then(function(r){
      if(!r.ok)throw 0;
      var s=decodeURIComponent(r.headers.get('X-Sugerencia')||'');
      return r.text().then(function(h){return [h,s];});
    }).then(function(par){
      if(p!==sel)return;
      var h=par[0];sugerir(par[1]);
      if(h===ultimo||pulsando)return;ultimo=h;
      var pegado=alFondo||term.scrollHeight-term.scrollTop-term.clientHeight<40,arriba=term.scrollTop,lado_=term.scrollLeft;
      term.innerHTML=h;
      term.scrollTop=pegado?term.scrollHeight:arriba;term.scrollLeft=lado_;
    }).catch(mal);
  }
  function accion(datos){
    return fetch('/api/accion',{method:'POST',cache:'no-store',
      headers:{'Content-Type':'application/json','X-Panel-Token':token,'X-Idioma':lang},body:JSON.stringify(datos)})
      .then(function(r){if(r.status===403){location.reload();return;}if(!r.ok)throw 0;setTimeout(function(){cargarTerm(true);cargarLista();cargarFicha();},500);})
      .catch(mal);
  }

  lado.addEventListener('click',function(ev){
    var b=ev.target.closest('.item'),c=ev.target.closest('.chip');
    if(b)elegir(b.dataset.p);
    else if(c){filtroEstado=c.dataset.filtro;aplicar();}
  });
  term.addEventListener('pointerdown',function(){pulsando=true;});
  document.addEventListener('pointerup',function(){setTimeout(function(){pulsando=false;},150);});
  filtro.addEventListener('input',aplicar);
  orden.addEventListener('change',function(){localStorage.setItem('torre.orden',orden.value);aplicar();});
  $('reanudar').addEventListener('click',function(){
    var b=$('reanudar'),er=$('r-error'),p=sel;
    if(!p||b.disabled)return;
    er.hidden=true;b.disabled=true;b.textContent=b.dataset.ocupado;
    fetch('/api/accion',{method:'POST',cache:'no-store',
      headers:{'Content-Type':'application/json','X-Panel-Token':token,'X-Idioma':lang},body:JSON.stringify({proyecto:p,reanudar:true})})
      .then(function(r){if(r.status===403){location.reload();}return r.text().then(function(m){if(!r.ok)throw m;});})
      .then(function(){enfocar=true;return cargarLista();}).then(function(){cargarFicha();cargarTerm(true);})
      .catch(function(m){er.textContent=(typeof m==='string'&&m)?m:er.dataset.generico;er.hidden=false;})
      .then(function(){b.disabled=false;b.textContent=b.dataset.normal;});
  });
  var bEl=$('eliminar'),tEl=null;
  function armarEl(si){bEl.classList.toggle('armado',si);bEl.textContent=si?bEl.dataset.confirmar:bEl.dataset.normal;}
  bEl.addEventListener('click',function(){
    var er=$('r-error'),p=sel;
    if(!p)return;
    clearTimeout(tEl);
    if(!bEl.classList.contains('armado')){armarEl(true);tEl=setTimeout(function(){armarEl(false);},5000);return;}
    armarEl(false);er.hidden=true;
    fetch('/api/accion',{method:'POST',cache:'no-store',
      headers:{'Content-Type':'application/json','X-Panel-Token':token,'X-Idioma':lang},body:JSON.stringify({proyecto:p,eliminar:true})})
      .then(function(r){if(r.status===403){location.reload();}return r.text().then(function(m){if(!r.ok)throw m;});})
      .then(function(){delete borradores[p];history.replaceState(null,'','#');return cargarLista();})
      .catch(function(m){er.textContent=(typeof m==='string'&&m)?m:er.dataset.generico;er.hidden=false;});
  });
  $('reintentar').addEventListener('click',function(){cargarLista().then(function(){cargarFicha();cargarTerm(true);});});
  $('menor').addEventListener('click',function(){letra(-1);});
  $('mayor').addEventListener('click',function(){letra(1);});
  form.addEventListener('submit',function(ev){
    ev.preventDefault();
    var v=txt.value;if(!sel||!v.trim())return;
    txt.value='';borradores[sel]='';accion({proyecto:sel,texto:v});
  });
  // ── Adjuntos: soltar o pegar archivos (se guarda una copia y se inserta su ruta) y
  // explorador para insertar la ruta real de un archivo o carpeta.
  var adj=$('ayuda-adjunto');
  function pedir(datos){
    return fetch('/api/accion',{method:'POST',cache:'no-store',
      headers:{'Content-Type':'application/json','X-Panel-Token':token,'X-Idioma':lang},body:JSON.stringify(datos)})
      .then(function(r){if(r.status===403&&!datos.explorar){location.reload();}return r.text().then(function(m){if(!r.ok)throw m;return m;});});
  }
  function citar(ruta){return ruta.indexOf(' ')>-1?"'"+ruta+"'":ruta;}
  function insertar(texto){
    var a=txt.selectionStart,b=txt.selectionEnd,v=txt.value,antes=v.slice(0,a),despues=v.slice(b);
    if(antes&&!/ $/.test(antes))antes+=' ';
    txt.value=antes+texto+' '+despues;
    var c=(antes+texto+' ').length;txt.focus();txt.setSelectionRange(c,c);cerrarSug();
  }
  function avisoAdj(clave,nombre){adj.textContent=(adj.dataset[clave]||'').replace('{nombre}',function(){return nombre||'';});adj.hidden=false;}
  function subir(archivos){
    if(!sel||!archivos.length)return;
    var p=sel,cola=[].slice.call(archivos);
    avisoAdj('subiendo');
    (function siguiente(){
      var f=cola.shift();
      if(!f){adj.hidden=true;return;}
      if(f.size>25*1024*1024){avisoAdj('grande',f.name);return;}
      fetch('/api/adjunto/'+encodeURIComponent(p),{method:'POST',cache:'no-store',
        headers:{'X-Panel-Token':token,'X-Idioma':lang,'X-Nombre':encodeURIComponent(f.name),'Content-Type':'application/octet-stream'},body:f})
        .then(function(r){return r.text().then(function(m){if(!r.ok)throw m;return m;});})
        .then(function(ruta){if(p===sel)insertar(citar(ruta));siguiente();})
        .catch(function(){avisoAdj('error',f.name);});
    })();
  }
  var ex=$('explorar'),exL=$('ex-lista'),exR=$('ex-ruta'),exE=$('ex-error'),exActual=null,exElegir=null;
  // Cada apertura fija su modo: alElegir (si se pasa) pone el explorador en modo carpeta: sin archivos y entregando la ruta a esa función.
  function abrirExplorar(ruta,alElegir){
    exElegir=alElegir||null;
    var modoCarpeta=!!exElegir;
    $('ex-t').textContent=$('ex-t').dataset[modoCarpeta?'carpeta':'normal'];
    $('ex-nota').textContent=$('ex-nota').dataset[modoCarpeta?'carpeta':'normal'];
    pedir({explorar:true,ruta:ruta||exActual||null}).then(function(m){
      var d=JSON.parse(m);exActual=d.ruta;exR.textContent=d.ruta;exL.textContent='';exE.hidden=true;
      function fila(nombre,tipo,destino){
        var li=document.createElement('li'),b=document.createElement('button');
        b.type='button';b.className='ex-'+tipo;b.textContent=nombre;b.dataset.tipo=tipo;b.dataset.destino=destino;
        li.appendChild(b);exL.appendChild(li);
      }
      if(d.padre)fila('..','carpeta',d.padre);
      d.carpetas.forEach(function(n){fila(n+'/','carpeta',d.ruta+'/'+n);});
      if(!modoCarpeta)d.archivos.forEach(function(n){fila(n,'archivo',d.ruta+'/'+n);});
      if(!ex.open)ex.showModal();
    }).catch(function(m){
      if(ruta&&!ex.open&&modoCarpeta){abrirExplorar(null,alElegir);return;}
      exE.textContent=(typeof m==='string'&&m)?m:'';exE.hidden=!exE.textContent;if(!ex.open)mal();});
  }
  $('adjuntar').addEventListener('click',function(){if(sel)abrirExplorar();});
  $('ex-cancelar').addEventListener('click',function(){ex.close();});
  $('ex-usar').addEventListener('click',function(){
    if(!exActual)return;
    ex.close();
    if(exElegir)exElegir(exActual);else insertar(citar(exActual));
  });
  ex.addEventListener('close',function(){exElegir=null;});
  exL.addEventListener('click',function(ev){
    var b=ev.target.closest('button');if(!b)return;
    if(b.dataset.tipo==='carpeta')abrirExplorar(b.dataset.destino,exElegir);
    else{ex.close();insertar(citar(b.dataset.destino));}
  });
  ['dragenter','dragover'].forEach(function(n){form.addEventListener(n,function(ev){
    if(ev.dataTransfer&&[].indexOf.call(ev.dataTransfer.types||[],'Files')>-1){ev.preventDefault();form.classList.add('soltar');}
  });});
  ['dragleave','dragend'].forEach(function(n){form.addEventListener(n,function(){form.classList.remove('soltar');});});
  form.addEventListener('drop',function(ev){
    form.classList.remove('soltar');
    var dt=ev.dataTransfer;if(!dt||[].indexOf.call(dt.types||[],'Files')<0)return;   // texto arrastrado: lo inserta el navegador
    ev.preventDefault();
    var archivos=[],carpeta=false,items=dt.items||[];
    for(var i=0;i<items.length;i++){
      if(items[i].kind!=='file')continue;
      var entrada=items[i].webkitGetAsEntry?items[i].webkitGetAsEntry():null;
      if(entrada&&entrada.isDirectory){carpeta=true;continue;}
      var f=items[i].getAsFile();if(f)archivos.push(f);
    }
    if(!items.length)archivos=[].slice.call(dt.files||[]);
    if(archivos.length)subir(archivos);
    if(carpeta){avisoAdj('carpeta');abrirExplorar();}
  });
  txt.addEventListener('paste',function(ev){
    var f=ev.clipboardData&&ev.clipboardData.files;
    if(f&&f.length){ev.preventDefault();subir(f);}
  });

  // ── Dictado: mantener presionada la barra espaciadora (con la caja vacía) o el botón.
  // Usa el reconocimiento de voz del navegador; el texto queda en la caja, no se envía solo.
  var Rec=window.SpeechRecognition||window.webkitSpeechRecognition,mic=$('dictar'),ayudaVoz=$('ayuda-dictado'),
      rec=null,dictando=false,esperaVoz=null,baseVoz='';
  if(!Rec)mic.hidden=true;
  function idiomaVoz(){
    var n=navigator.language||lang;
    return n.toLowerCase().indexOf(lang)===0?n:(lang==='es'?'es-ES':'en-US');
  }
  function empezarVoz(){
    if(!Rec||dictando||!sel)return;
    baseVoz=txt.value?txt.value.replace(/ *$/,' '):'';
    rec=new Rec();rec.lang=idiomaVoz();rec.continuous=true;rec.interimResults=true;
    rec.onresult=function(ev){
      var dicho='';
      for(var i=0;i<ev.results.length;i++)dicho+=ev.results[i][0].transcript;
      txt.value=baseVoz+dicho.replace(/^ +/,'');
    };
    rec.onerror=function(ev){
      if(ev.error==='not-allowed'||ev.error==='service-not-allowed'){ayudaVoz.textContent=ayudaVoz.dataset.permiso;ayudaVoz.hidden=false;}
    };
    rec.onend=function(){dictando=false;mic.classList.remove('grabando');sugerir(propuesta);txt.focus();};
    try{rec.start();}catch(e){return;}
    dictando=true;mic.classList.add('grabando');ayudaVoz.hidden=true;txt.placeholder=txt.dataset.escuchando;
  }
  function terminarVoz(){if(rec&&dictando){try{rec.stop();}catch(e){}}}
  mic.addEventListener('pointerdown',function(ev){ev.preventDefault();txt.focus();empezarVoz();});
  ['pointerup','pointerleave','pointercancel'].forEach(function(n){mic.addEventListener(n,terminarVoz);});
  txt.addEventListener('keydown',function(ev){
    if(ev.key!==' '||ev.altKey||ev.metaKey||ev.ctrlKey||!Rec)return;
    if(dictando||esperaVoz){ev.preventDefault();ev.stopImmediatePropagation();return;}
    if(txt.value!=='')return;                 // con texto, la barra espaciadora escribe un espacio
    ev.preventDefault();ev.stopImmediatePropagation();
    esperaVoz=setTimeout(function(){esperaVoz='activo';empezarVoz();},300);
  });
  txt.addEventListener('keyup',function(ev){
    if(ev.key!==' ')return;
    if(esperaVoz&&esperaVoz!=='activo')clearTimeout(esperaVoz);
    esperaVoz=null;terminarVoz();
  });

  // ── Autocompletado de comandos «/» del motor, del proyecto y del usuario
  var sug=$('sugerencias'),catalogo={},visiblesSug=[],activo=0;
  function cargarComandos(p){
    if(catalogo[p])return;
    catalogo[p]=[];
    fetch('comandos/'+encodeURIComponent(p),{cache:'no-store'}).then(function(r){if(!r.ok)throw 0;return r.json();})
      .then(function(l){catalogo[p]=l;pintarSug();}).catch(function(){delete catalogo[p];});
  }
  function cerrarSug(){sug.hidden=true;visiblesSug=[];}
  function marcarSug(){
    [].forEach.call(sug.children,function(li,i){li.setAttribute('aria-selected',i===activo?'true':'false');});
    if(sug.children[activo])sug.children[activo].scrollIntoView({block:'nearest'});
  }
  function pintarSug(){
    var v=txt.value;
    if(!sel||!/^[/][A-Za-z0-9_.:-]*$/.test(v)){cerrarSug();return;}
    cargarComandos(sel);
    var q=v.toLowerCase(),todos=catalogo[sel]||[];
    var empiezan=todos.filter(function(c){return c.c.toLowerCase().indexOf(q)===0;}),
        contienen=todos.filter(function(c){return c.c.toLowerCase().indexOf(q)!==0&&c.c.toLowerCase().indexOf(q.slice(1))>0;});
    visiblesSug=empiezan.concat(contienen).slice(0,40);
    if(!visiblesSug.length){cerrarSug();return;}
    sug.textContent='';
    visiblesSug.forEach(function(c,i){
      var li=document.createElement('li'),b=document.createElement('b'),d=document.createElement('span'),o=document.createElement('small');
      li.setAttribute('role','option');li.dataset.i=i;
      b.textContent=c.c;d.textContent=c.d||'';o.textContent=sug.dataset[c.o]||'';
      li.appendChild(b);li.appendChild(d);li.appendChild(o);sug.appendChild(li);
    });
    activo=Math.min(activo,visiblesSug.length-1);if(activo<0)activo=0;
    sug.hidden=false;marcarSug();
  }
  function aceptarSug(i){
    var c=visiblesSug[i];if(!c)return;
    txt.value=c.c+' ';cerrarSug();txt.focus();
  }
  txt.addEventListener('input',function(){activo=0;pintarSug();});
  txt.addEventListener('blur',function(){setTimeout(cerrarSug,150);});
  sug.addEventListener('mousedown',function(ev){
    var li=ev.target.closest('li');if(li){ev.preventDefault();aceptarSug(+li.dataset.i);}
  });
  txt.addEventListener('keydown',function(ev){
    if(sug.hidden||ev.isComposing)return;
    if(ev.key==='ArrowDown'||ev.key==='ArrowUp'){
      activo=(activo+(ev.key==='ArrowDown'?1:visiblesSug.length-1))%visiblesSug.length;marcarSug();
    }else if(ev.key==='Tab'||ev.key==='Enter'){aceptarSug(activo);
    }else if(ev.key==='Escape'){cerrarSug();
    }else return;
    ev.preventDefault();ev.stopImmediatePropagation();
  });

  txt.addEventListener('keydown',function(ev){
    if(ev.isComposing||ev.altKey||ev.metaKey||ev.ctrlKey)return;
    if(ev.key==='Enter'&&!ev.shiftKey){
      ev.preventDefault();
      if(txt.value.trim()!=='')form.requestSubmit();
      else if(sel){txt.value='';accion({proyecto:sel,tecla:'Enter'});}
      return;
    }
    if(txt.value!=='')return;
    if(ev.key==='Tab'&&!ev.shiftKey&&propuesta){ev.preventDefault();txt.value=propuesta;return;}
    var k={ArrowUp:'Up',ArrowDown:'Down',Escape:'Escape'}[ev.key];
    // Con un menú abierto (el agente te necesita), 1-3 eligen la opción sin salir de la caja.
    if(!k&&/^[123]$/.test(ev.key)&&ficha.querySelector('.e-te_necesita'))k=ev.key;
    if(k&&sel){ev.preventDefault();accion({proyecto:sel,tecla:k});}
  });
  term.addEventListener('keydown',function(ev){
    if(ev.altKey||ev.metaKey||ev.ctrlKey||!sel)return;
    var k={ArrowUp:'Up',ArrowDown:'Down',Escape:'Escape',Enter:'Enter','1':'1','2':'2','3':'3'}[ev.key];
    if(k){ev.preventDefault();accion({proyecto:sel,tecla:k});}
  });
  form.addEventListener('click',function(ev){
    var b=ev.target.closest('button');
    if(!b||b.type==='submit'||!sel)return;
    if(b.dataset.tecla){accion({proyecto:sel,tecla:b.dataset.tecla});return;}
    if(b===parar){
      clearTimeout(temporizador);
      if(armado){armar(false);accion({proyecto:sel,detener:true});}
      else{armar(true);temporizador=setTimeout(function(){armar(false);},5000);}
    }
  });
  document.addEventListener('keydown',function(ev){
    if(!ev.altKey||(ev.key!=='ArrowDown'&&ev.key!=='ArrowUp'))return;
    var v=visibles();if(!v.length)return;
    ev.preventDefault();
    var i=v.map(function(b){return b.dataset.p;}).indexOf(sel);
    i=ev.key==='ArrowDown'?Math.min(v.length-1,i+1):Math.max(0,i<0?0:i-1);
    elegir(v[i].dataset.p);
  });

  // ── Configuración global y ajustes por agente (ajAgente=null → global)
  var aj=$('ajustes'),ajAgente=null,ajE=$('aj-error'),ajTablero='';
  var pestanas=[].slice.call(aj.querySelectorAll('[data-pestana]'));
  function mostrarPestana(nombre,foco){
    pestanas.forEach(function(b){
      var activa=b.dataset.pestana===nombre;
      b.setAttribute('aria-selected',activa?'true':'false');b.tabIndex=activa?0:-1;
      $(b.getAttribute('aria-controls')).hidden=!activa;
      if(activa&&foco)b.focus();
    });
  }
  $('aj-pestanas').addEventListener('click',function(ev){var b=ev.target.closest('[data-pestana]');if(b)mostrarPestana(b.dataset.pestana,false);});
  $('aj-pestanas').addEventListener('keydown',function(ev){
    var i=pestanas.indexOf(document.activeElement);if(i<0)return;
    var j={ArrowRight:(i+1)%pestanas.length,ArrowLeft:(i+pestanas.length-1)%pestanas.length,Home:0,End:pestanas.length-1}[ev.key];
    if(j===undefined)return;
    ev.preventDefault();mostrarPestana(pestanas[j].dataset.pestana,true);
  });
  function leerConfig(agente){
    return fetch('/api/config'+(agente?'/'+encodeURIComponent(agente):''),{cache:'no-store'})
      .then(function(r){if(!r.ok)throw 0;return r.json();});
  }
  var ajCarpeta0={modo:null,ruta:''};
  function estadoCarpeta(){
    var r=document.querySelector('input[name=aj-cmodo]:checked');
    return {modo:r?r.value:null,ruta:$('aj-carpeta').value.trim()};
  }
  function rellenarCarpeta(cp){
    var r=document.querySelector('input[name=aj-cmodo]:checked');if(r)r.checked=false;
    if(cp.modo!=='predeterminada')document.querySelector('input[name=aj-cmodo][value='+cp.modo+']').checked=true;
    $('aj-carpeta').value=cp.modo==='carpeta'?cp.valor:(cp.base||'');
    $('aj-c-sugerida').hidden=cp.modo!=='predeterminada';
    $('aj-c-aviso').hidden=cp.disponible||cp.modo==='ninguna';
    ajCarpeta0=estadoCarpeta();
  }
  function abrirAjustes(agente,pestana){
    leerConfig(agente).then(function(d){
      var c=d.config,modo=agente?'agente':'global';
      ajAgente=agente||null;ajE.hidden=true;
      $('aj-t').textContent=$('aj-t').dataset[modo].replace('{agente}',function(){return agente||'';});
      $('aj-nota').textContent=$('aj-nota').dataset[modo];
      $('aj-motor').value=c.motor;$('aj-autonomia').value=c.autonomia;
      $('aj-sub').checked=c.subagentes.permitidos;$('aj-submax').value=c.subagentes.max;
      $('aj-submax').disabled=!c.subagentes.permitidos;
      $('aj-semana').value=c.limites.semana;$('aj-sesion').value=c.limites.sesion;
      $('aj-pestanas').hidden=!!agente;
      if(!agente){
        $('aj-tope').value=c.tope_revision||0;
        ajTablero=d.tablero||'';$('aj-tablero').value=ajTablero;
        rellenarCarpeta(d.carpeta_proyectos);
      }
      mostrarPestana(pestana||'agentes',!!pestana);
      aj.showModal();
    }).catch(mal);
  }
  $('abrir-config').addEventListener('click',function(){abrirAjustes(null);});
  $('aviso-carpeta-abrir').addEventListener('click',function(){abrirAjustes(null,'proyectos');});
  ficha.addEventListener('click',function(ev){if(ev.target.closest('[data-ajustes]')&&sel)abrirAjustes(sel);});
  $('aj-sub').addEventListener('change',function(){$('aj-submax').disabled=!$('aj-sub').checked;});
  $('aj-cancelar').addEventListener('click',function(){aj.close();});
  $('aj-carpeta').addEventListener('input',function(){document.querySelector('input[name=aj-cmodo][value=carpeta]').checked=true;});
  $('aj-elegir').addEventListener('click',function(){
    abrirExplorar($('aj-carpeta').value.trim()||undefined,function(ruta){
      $('aj-carpeta').value=ruta;document.querySelector('input[name=aj-cmodo][value=carpeta]').checked=true;
    });
  });
  $('form-ajustes').addEventListener('submit',function(ev){
    ev.preventDefault();ajE.hidden=true;
    var c={motor:$('aj-motor').value,autonomia:$('aj-autonomia').value,
      subagentes:{permitidos:$('aj-sub').checked,max:parseInt($('aj-submax').value,10)||1},
      limites:{semana:parseInt($('aj-semana').value,10)||0,sesion:parseInt($('aj-sesion').value,10)||0}};
    if(!ajAgente){
      c.tope_revision=parseInt($('aj-tope').value,10)||0;
      var cs=estadoCarpeta();
      if(cs.modo==='carpeta'&&!cs.ruta){
        mostrarPestana('proyectos',true);ajE.textContent=ajE.dataset.sinruta;ajE.hidden=false;return;
      }
      if(cs.modo&&(cs.modo!==ajCarpeta0.modo||cs.ruta!==ajCarpeta0.ruta))c.carpeta_proyectos=cs.modo==='ninguna'?'':cs.ruta;
      c.tablero=$('aj-tablero').value.trim();
    }
    fetch('/api/accion',{method:'POST',cache:'no-store',
      headers:{'Content-Type':'application/json','X-Panel-Token':token,'X-Idioma':lang},
      body:JSON.stringify({guardar_config:true,agente:ajAgente,config:c})})
      .then(function(r){if(r.status===403){location.reload();}return r.text().then(function(m){if(!r.ok)throw m;});})
      .then(function(){
        aj.close();
        if(!ajAgente&&c.tablero!==ajTablero){location.reload();return;}
        if(!ajAgente)leerConfig(null).then(function(d){$('aviso-carpeta').hidden=!d.carpeta_proyectos.elegir;}).catch(function(){});
        cargarFicha();
      })
      .catch(function(m){ajE.textContent=(typeof m==='string'&&m)?m:ajE.dataset.generico;ajE.hidden=false;});
  });

  var dlg=$('nuevo'),nP=$('n-proyecto'),nT=$('n-tarea'),nI=$('n-instr'),nE=$('n-error'),nL=$('n-lanzar'),nF=$('n-forzar');
  var nR=$('n-ruta'),OTRA='__otra__';
  function pedirRuta(){return nP.hidden||nP.value===OTRA;}
  // La ruta se pide cuando no hay carpeta de proyectos o se eligió «Otro repositorio».
  function ajustarNuevo(){
    var r=pedirRuta();
    $('n-bloque-ruta').hidden=!r;nR.required=r;nP.required=!nP.hidden;
  }
  function cargarTareas(){
    nT.disabled=true;nT.innerHTML='';nE.hidden=true;
    if(pedirRuta()){
      if(!nR.value.trim())return;
      pedir({tareas:true,ruta:nR.value.trim()}).then(function(h){nT.innerHTML=h;nT.disabled=false;})
        .catch(function(m){nE.textContent=(typeof m==='string'&&m)?m:nE.dataset.generico;nE.hidden=false;});
    }else if(nP.value){
      traer('tareas/'+encodeURIComponent(nP.value)).then(function(h){nT.innerHTML=h;nT.disabled=false;}).catch(mal);
    }
  }
  $('abrir-nuevo').addEventListener('click',function(){
    nE.hidden=true;nT.innerHTML='';nT.disabled=true;nR.value='';
    Promise.all([leerConfig(null).catch(function(){return null;}),traer('carpetas')]).then(function(r){
      var d=r[0],sin=!!d&&!d.carpeta_proyectos.disponible;
      if(d){$('n-motor').value=d.config.motor;$('n-autonomia').value=d.config.autonomia;}
      nP.innerHTML=r[1]+'<option value="'+OTRA+'">'+$('n-lbl-proyecto').dataset.otra+'</option>';
      nP.hidden=sin;$('n-lbl-proyecto').hidden=sin;$('n-sin-carpeta').hidden=!sin;
      nP.value=sin?OTRA:'';ajustarNuevo();dlg.showModal();(sin?nR:nP).focus();
    }).catch(mal);
  });
  nP.addEventListener('change',function(){ajustarNuevo();cargarTareas();});
  nR.addEventListener('change',cargarTareas);
  $('n-elegir').addEventListener('click',function(){
    abrirExplorar(nR.value.trim()||undefined,function(ruta){nR.value=ruta;cargarTareas();});
  });
  $('n-cancelar').addEventListener('click',function(){dlg.close();});
  $('form-nuevo').addEventListener('submit',function(ev){
    ev.preventDefault();
    if(nL.disabled)return;
    var destino=pedirRuta()?{ruta:nR.value.trim()}:{proyecto:nP.value},p=destino.proyecto||destino.ruta;
    if(!p)return;
    nE.hidden=true;nL.disabled=true;nL.textContent=nL.dataset.ocupado;
    fetch('/api/accion',{method:'POST',cache:'no-store',
      headers:{'Content-Type':'application/json','X-Panel-Token':token,'X-Idioma':lang},
      body:JSON.stringify(Object.assign({lanzar:true,tarea:nT.value||'libre',instruccion:nI.value,forzar:nF.checked,motor:$('n-motor').value,autonomia:$('n-autonomia').value},destino))})
      .then(function(r){if(r.status===403){location.reload();}return r.text().then(function(m){if(!r.ok)throw m;return m;});})
      .then(function(m){p=m||p;dlg.close();nI.value='';nF.checked=false;return cargarLista();})
      .then(function(){elegir(p);})
      .catch(function(m){nE.textContent=(typeof m==='string'&&m)?m:nE.dataset.generico;nE.hidden=false;})
      .then(function(){nL.disabled=false;nL.textContent=nL.dataset.normal;});
  });

  letra(0);aplicar();
  var inicial=decodeURIComponent(location.hash.slice(1)),v0=visibles();
  if(items().some(function(b){return b.dataset.p===inicial;}))elegir(inicial);
  else if(v0.length)elegir(v0[0].dataset.p);
  // Cambiar solo el #agente (un aviso de escritorio, un enlace, la barra de direcciones)
  // no recarga la página: se cambia de agente aquí.
  window.addEventListener('hashchange',function(){
    var p=decodeURIComponent(location.hash.slice(1));
    if(items().some(function(b){return b.dataset.p===p;}))elegir(p);
  });
  hora();
  setInterval(function(){cargarTerm(false);},1500);
  setInterval(function(){cargarLista().then(cargarFicha);},4000);
})();
"""


def pagina(idioma):
    t = CAT[idioma]
    e = html.escape
    cp = info_carpeta()
    aviso_carpeta = (f'<div id="aviso-carpeta" role="status"{"" if cp["elegir"] else " hidden"}>'
                     f'<p><strong>{e(t["aviso_carpeta_titulo"])}</strong> {e(t["aviso_carpeta_texto"].format(carpeta=cp["efectiva"]))}</p>'
                     f'<button type="button" class="b primario" id="aviso-carpeta-abrir">{e(t["aviso_carpeta_boton"])}</button></div>')
    alternos = "".join(f'<link rel="alternate" hreflang="{i}" href="/{i}/">' for i in IDIOMAS)
    selector = " · ".join(
        f'<a href="/{i}/" hreflang="{i}"' + (' aria-current="page"' if i == idioma else "") + f">{i.upper()}</a>"
        for i in IDIOMAS
    )
    opciones = "".join(f'<option value="{v}">{e(t["orden_" + v])}</option>' for v in ("atencion", "nombre", "reciente"))
    op_motor = "".join(f'<option value="{m}">{e(nombre_motor(t, m))}</option>' for m in config.motores_disponibles())
    op_autonomia = "".join(f'<option value="{a}">{e(t["autonomia_" + a])}</option>' for a in config.AUTONOMIAS)
    teclas = "".join(
        f'<button type="button" class="b" data-tecla="{k}">{e(v)}</button>'
        for k, v in (("Enter", "Enter"), ("Escape", t["tecla_esc"]), ("Up", "↑"), ("Down", "↓"), ("1", "1"), ("2", "2"), ("3", "3"))
    )
    url_tablero = config.tablero()
    enlace_tablero = (f'    <a href="{e(url_tablero, quote=True)}" target="_blank" rel="noopener">{e(t["tablero"])}</a>'
                      if url_tablero else "")
    return f"""<!doctype html>
<html lang="{idioma}">
<head>
<meta charset="utf-8">
<meta name="viewport" content="width=device-width, initial-scale=1">
<title>{e(t["titulo_pagina"])}</title>
<meta name="description" content="{e(t["descripcion"], quote=True)}">
<meta name="robots" content="noindex">
<meta name="panel-token" content="{TOKEN}">
<link rel="canonical" href="/{idioma}/">
<link rel="icon" href="/favicon.svg" type="image/svg+xml">
{alternos}<link rel="alternate" hreflang="x-default" href="/">
<style>{CSS}</style>
</head>
<body>
<div class="app">
<aside aria-label="{e(t["agentes"], quote=True)}">
  <div class="marca"><h1><img src="/favicon.svg" alt="" width="22" height="22">{e(t["encabezado"])}</h1><p>{e(t["subtitulo"])}</p></div>
  <div class="controles">
    <input type="search" id="filtro" placeholder="{e(t["filtro"], quote=True)}" aria-label="{e(t["filtro"], quote=True)}" autocomplete="off">
    <label>{e(t["orden"])}<select id="orden">{opciones}</select></label>
    <button type="button" class="b primario" id="abrir-nuevo">{e(t["nuevo"])}</button>
    <button type="button" class="b" id="abrir-config">{e(t["config_boton"])}</button>
  </div>
  <div id="lado">
{lista(idioma)}
  </div>
  <div class="pie">
    <span>{e(t["actualizado"])} <time id="reloj"></time> · {e(t["atajos"])}</span>
{enlace_tablero}
    <nav>{selector}</nav>
  </div>
</aside>
<main>
  {aviso_carpeta}
  <div id="fuera" role="alert"><span>{e(t["sin_conexion"])}</span><button type="button" class="b" id="reintentar">{e(t["reintentar"])}</button></div>
  <p id="vacio">{e(t["elige"])}</p>
  <div id="detalle" hidden>
    <div id="ficha"></div>
    <div class="barra">
      <h3>{e(t["consola"])}</h3>
      <span class="letra">
        <button type="button" class="b" id="menor" aria-label="{e(t["letra_menor"], quote=True)}" title="{e(t["letra_menor"], quote=True)}">A−</button>
        <button type="button" class="b" id="mayor" aria-label="{e(t["letra_mayor"], quote=True)}" title="{e(t["letra_mayor"], quote=True)}">A+</button>
      </span>
    </div>
    <pre id="term" tabindex="0"></pre>
    <form id="consola">
      <ul id="sugerencias" role="listbox" aria-label="{e(t["comandos"], quote=True)}" data-proyecto="{e(t["comando_proyecto"], quote=True)}" data-usuario="{e(t["comando_usuario"], quote=True)}" data-motor="{e(t["comando_motor"], quote=True)}" hidden></ul>
      <textarea name="texto" rows="2" placeholder="{e(t["escribir"], quote=True)}" aria-label="{e(t["escribir"], quote=True)}" data-base="{e(t["escribir"], quote=True)}" data-sugerida="{e(t["sugerida"], quote=True)}" data-escuchando="{e(t["dictado_escuchando"], quote=True)}"></textarea>
      <div class="botones">
        <button type="submit" class="b primario">{e(t["enviar"])}</button>
        <button type="button" class="b" id="dictar" title="{e(t["dictado_aviso"], quote=True)}"><svg viewBox="0 0 16 16" width="13" height="13" aria-hidden="true"><path fill="currentColor" d="M8 10.5a2.5 2.5 0 0 0 2.5-2.5V4a2.5 2.5 0 0 0-5 0v4A2.5 2.5 0 0 0 8 10.5Zm4-2.5a.75.75 0 0 1 1.5 0 5.5 5.5 0 0 1-4.75 5.45V15a.75.75 0 0 1-1.5 0v-1.55A5.5 5.5 0 0 1 2.5 8 .75.75 0 0 1 4 8a4 4 0 0 0 8 0Z"/></svg> {e(t["dictar"])}</button>
        <button type="button" class="b" id="adjuntar" title="{e(t["ruta_aviso"], quote=True)}">{e(t["ruta_boton"])}</button>
        <span class="teclas"><span class="tenue">{e(t["teclas"])}</span>{teclas}</span>
        <button type="button" class="b peligro" data-detener data-normal="{e(t["detener"], quote=True)}" data-confirmar="{e(t["confirmar"], quote=True)}">{e(t["detener"])}</button>
      </div>
      <p class="ayuda">{e(t["teclado"])}</p>
      <p class="ayuda">{e(t["adjuntos_ayuda"])}</p>
      <p class="ayuda" id="ayuda-adjunto" role="status" data-subiendo="{e(t["adjunto_subiendo"], quote=True)}" data-error="{e(t["adjunto_error"], quote=True)}" data-grande="{e(t["adjunto_grande"], quote=True)}" data-carpeta="{e(t["adjunto_carpeta"], quote=True)}" hidden></p>
      <p class="ayuda" id="ayuda-dictado" role="status" data-permiso="{e(t["dictado_permiso"], quote=True)}" hidden></p>
    </form>
    <div id="apagado" hidden>
      <span>{e(t["pantalla_vacia"])}</span>
      <button type="button" class="b primario" id="reanudar" data-normal="{e(t["reanudar"], quote=True)}" data-ocupado="{e(t["reanudando"], quote=True)}">{e(t["reanudar"])}</button>
      <button type="button" class="b peligro" id="eliminar" data-normal="{e(t["eliminar"], quote=True)}" data-confirmar="{e(t["confirmar"], quote=True)}">{e(t["eliminar"])}</button>
      <span id="r-error" role="alert" data-generico="{e(t["error_reanudar"], quote=True)}" hidden></span>
    </div>
  </div>
</main>
</div>
<dialog id="nuevo" aria-labelledby="nuevo-t">
  <form id="form-nuevo">
    <h2 id="nuevo-t">{e(t["nuevo_titulo"])}</h2>
    <p class="tenue">{e(t["nuevo_nota"])}</p>
    <label id="n-lbl-proyecto" data-otra="{e(t["n_otra_ruta"], quote=True)}">{e(t["proyecto"])}<select id="n-proyecto"></select></label>
    <div id="n-bloque-ruta" hidden>
      <p class="tenue" id="n-sin-carpeta" hidden>{e(t["n_sin_carpeta"])}</p>
      <label>{e(t["n_ruta_label"])}<span class="ruta-fila"><input type="text" id="n-ruta" autocomplete="off" spellcheck="false"><button type="button" class="b" id="n-elegir">{e(t["carpeta_elegir"])}</button></span><span>{e(t["n_ruta_ayuda"])}</span></label>
    </div>
    <label>{e(t["tarea_label"])}<select id="n-tarea" disabled></select></label>
    <label>{e(t["instruccion"])}<textarea id="n-instr" rows="4"></textarea><span>{e(t["instruccion_ayuda"])}</span></label>
    <div class="par">
      <label>{e(t["motor"])}<select id="n-motor">{op_motor}</select></label>
      <label>{e(t["autonomia"])}<select id="n-autonomia">{op_autonomia}</select></label>
    </div>
    <label class="fila"><input type="checkbox" id="n-forzar"> {e(t["forzar"])}</label>
    <p id="n-error" role="alert" data-generico="{e(t["error_lanzar"], quote=True)}" hidden></p>
    <div class="botones">
      <button type="button" class="b" id="n-cancelar">{e(t["cancelar"])}</button>
      <button type="submit" class="b primario" id="n-lanzar" data-normal="{e(t["lanzar"], quote=True)}" data-ocupado="{e(t["lanzando"], quote=True)}">{e(t["lanzar"])}</button>
    </div>
  </form>
</dialog>
<dialog id="explorar" aria-labelledby="ex-t">
  <h2 id="ex-t" data-normal="{e(t["ruta_titulo"], quote=True)}" data-carpeta="{e(t["ruta_titulo_carpeta"], quote=True)}">{e(t["ruta_titulo"])}</h2>
  <p class="tenue" id="ex-nota" data-normal="{e(t["ruta_nota"], quote=True)}" data-carpeta="{e(t["ruta_nota_carpeta"], quote=True)}">{e(t["ruta_nota"])}</p>
  <p id="ex-ruta"></p>
  <ul id="ex-lista"></ul>
  <p id="ex-error" role="alert" hidden></p>
  <div class="botones">
    <button type="button" class="b" id="ex-cancelar">{e(t["cancelar"])}</button>
    <button type="button" class="b primario" id="ex-usar">{e(t["ruta_usar"])}</button>
  </div>
</dialog>
<dialog id="ajustes" aria-labelledby="aj-t">
  <form id="form-ajustes">
    <h2 id="aj-t" data-global="{e(t["config_titulo"], quote=True)}" data-agente="{e(t["ajustes_titulo"], quote=True)}"></h2>
    <p class="tenue" id="aj-nota" data-global="{e(t["config_nota"], quote=True)}" data-agente="{e(t["ajustes_nota"], quote=True)}"></p>
    <div class="pestanas" role="tablist" id="aj-pestanas" aria-label="{e(t["config_tabs"], quote=True)}">
      <button type="button" role="tab" id="tab-agentes" data-pestana="agentes" aria-controls="pan-agentes" aria-selected="true">{e(t["config_tab_agentes"])}</button>
      <button type="button" role="tab" id="tab-proyectos" data-pestana="proyectos" aria-controls="pan-proyectos" aria-selected="false" tabindex="-1">{e(t["config_tab_proyectos"])}</button>
      <button type="button" role="tab" id="tab-tareas" data-pestana="tareas" aria-controls="pan-tareas" aria-selected="false" tabindex="-1">{e(t["config_tab_tareas"])}</button>
    </div>
    <div role="tabpanel" id="pan-agentes" aria-labelledby="tab-agentes">
    <div class="par">
      <label>{e(t["motor"])}<select id="aj-motor">{op_motor}</select></label>
      <label>{e(t["autonomia"])}<select id="aj-autonomia">{op_autonomia}</select></label>
    </div>
    <p class="tenue">{e(t["autonomia_ayuda"])}</p>
    <label class="fila"><input type="checkbox" id="aj-sub"> {e(t["subagentes_permitir"])}</label>
    <label>{e(t["subagentes_cuantos"])}<input type="number" id="aj-submax" min="1" max="20" step="1"></label>
    <div class="par">
      <label>{e(t["limite_semana"])}<input type="number" id="aj-semana" min="0" max="100" step="1"></label>
      <label>{e(t["limite_sesion"])}<input type="number" id="aj-sesion" min="0" max="100" step="1"></label>
    </div>
    <p class="tenue">{e(t["limites_ayuda"])}</p>
    <p class="tenue">{e(t["codex_nota"])}</p>
    </div>
    <div role="tabpanel" id="pan-proyectos" aria-labelledby="tab-proyectos" hidden>
      <fieldset>
        <legend>{e(t["carpeta_label"])}</legend>
        <label class="fila"><input type="radio" name="aj-cmodo" value="carpeta"> {e(t["carpeta_modo_carpeta"])}</label>
        <span class="ruta-fila"><input type="text" id="aj-carpeta" autocomplete="off" spellcheck="false" aria-label="{e(t["carpeta_modo_carpeta"], quote=True)}"><button type="button" class="b" id="aj-elegir">{e(t["carpeta_elegir"])}</button></span>
        <p class="tenue" id="aj-c-sugerida" hidden>{e(t["carpeta_sugerida"])}</p>
        <label class="fila"><input type="radio" name="aj-cmodo" value="ninguna"> {e(t["carpeta_modo_ninguna"])}</label>
      </fieldset>
      <p class="tenue">{e(t["carpeta_ayuda"])}</p>
      <p class="alerta" id="aj-c-aviso" hidden>{e(t["carpeta_no_existe"])}</p>
    </div>
    <div role="tabpanel" id="pan-tareas" aria-labelledby="tab-tareas" hidden>
      <label>{e(t["tope_revision"])}<input type="number" id="aj-tope" min="0" max="99" step="1"></label>
      <p class="tenue">{e(t["tope_revision_ayuda"])}</p>
      <label>{e(t["tablero_label"])}<input type="url" id="aj-tablero" autocomplete="off" spellcheck="false" placeholder="https://"></label>
      <p class="tenue">{e(t["tablero_ayuda"])}</p>
    </div>
    <p id="aj-error" role="alert" data-generico="{e(t["error_config"], quote=True)}" data-sinruta="{e(t["carpeta_falta"], quote=True)}" hidden></p>
    <div class="botones">
      <button type="button" class="b" id="aj-cancelar">{e(t["cancelar"])}</button>
      <button type="submit" class="b primario">{e(t["guardar"])}</button>
    </div>
  </form>
</dialog>
<script>{JS}</script>
</body>
</html>"""


class Manejador(BaseHTTPRequestHandler):
    def _enviar(self, codigo, cuerpo="", cabeceras=None, tipo="text/html; charset=utf-8", cache="no-store"):
        datos = cuerpo.encode("utf-8")
        self.send_response(codigo)
        self.send_header("Content-Type", tipo)
        self.send_header("Content-Length", str(len(datos)))
        self.send_header("Cache-Control", cache)
        self.send_header("X-Frame-Options", "DENY")
        self.send_header("Referrer-Policy", "no-referrer")
        for k, v in (cabeceras or {}).items():
            self.send_header(k, v)
        try:
            self.end_headers()
            self.wfile.write(datos)
        except (BrokenPipeError, ConnectionResetError):
            pass   # el navegador cerró la conexión (cambio de agente o recarga): no es un error

    def _host_local(self):
        return self.headers.get("Host", "") in (f"localhost:{PUERTO}", f"127.0.0.1:{PUERTO}")

    def do_GET(self):
        if not self._host_local():
            return self._enviar(403, "403")
        ruta = self.path.split("?")[0]
        if ruta == "/":
            pedido = self.headers.get("Accept-Language", "")
            orden = [p.split(";")[0].strip().lower()[:2] for p in pedido.split(",")]
            idioma = next((i for i in orden if i in IDIOMAS), IDIOMAS[0])
            return self._enviar(302, "", {"Location": f"/{idioma}/", "Vary": "Accept-Language"})
        if ruta == "/favicon.svg":
            with open(os.path.join(DIR, "static", "favicon.svg"), encoding="utf-8") as f:
                return self._enviar(200, f.read(), tipo="image/svg+xml", cache="max-age=86400")
        partes =[unquote(p) for p in ruta.split("/") if p]
        if partes[:2] == ["api", "config"] and len(partes) <= 3:
            if len(partes) == 2:
                return self._enviar(200, json.dumps({"config": config.global_(), "carpeta_proyectos": info_carpeta(),
                                                     "tablero": config.tablero() or ""}))
            if NOMBRE_OK.match(partes[2]) and partes[2] in proyectos_con_estado():
                return self._enviar(200, json.dumps({"config": config.de_agente(partes[2]),
                                                     "vivo": partes[2] in ventanas_vivas()}))
            return self._enviar(404, "404")
        if partes and partes[0] in IDIOMAS:
            idioma, cab = partes[0], {"Content-Language": partes[0]}
            if len(partes) == 1:
                if not ruta.endswith("/"):
                    return self._enviar(301, "", {"Location": f"/{idioma}/"})
                return self._enviar(200, pagina(idioma), cab)
            if partes[1:] == ["lista"]:
                return self._enviar(200, lista(idioma), cab)
            if len(partes) == 3 and partes[1] == "comandos" and NOMBRE_OK.match(partes[2]):
                return self._enviar(200, json.dumps(comandos(idioma, partes[2]), ensure_ascii=False), cab)
            if partes[1:] == ["carpetas"]:
                return self._enviar(200, opciones_proyecto(idioma), cab)
            if len(partes) == 3 and partes[1] == "tareas" and partes[2] in carpetas():
                return self._enviar(200, opciones_tarea(idioma, os.path.join(carpeta(), partes[2])), cab)
            if len(partes) == 3 and NOMBRE_OK.match(partes[2]) and partes[2] in proyectos_con_estado():
                if partes[1] == "agente":
                    return self._enviar(200, ficha(idioma, partes[2]), cab)
                if partes[1] == "terminal":
                    cuerpo, sug = terminal(idioma, partes[2])
                    return self._enviar(200, cuerpo, dict(cab, **{"X-Sugerencia": quote(sug)}))
        self._enviar(404, "404")

    def do_POST(self):
        origen = self.headers.get("Origin")
        permitido = (f"http://localhost:{PUERTO}", f"http://127.0.0.1:{PUERTO}")
        if (not self._host_local() or (origen and origen not in permitido)
                or not secrets.compare_digest(self.headers.get("X-Panel-Token", ""), TOKEN)):
            return self._enviar(403, "403")
        if self.path.startswith("/api/adjunto/"):
            agente = unquote(self.path[len("/api/adjunto/"):])
            if not NOMBRE_OK.match(agente) or agente not in proyectos_con_estado():
                return self._enviar(404, "404")
            try:
                largo = int(self.headers.get("Content-Length", "0"))
            except ValueError:
                return self._enviar(400, "400")
            if largo <= 0 or largo > ADJUNTO_MAX:
                return self._enviar(413, "413")
            ruta = guardar_adjunto(agente, unquote(self.headers.get("X-Nombre", "")), self.rfile.read(largo))
            return self._enviar(200, ruta)
        if self.path != "/api/accion":
            return self._enviar(404, "404")
        try:
            largo = int(self.headers.get("Content-Length", "0"))
            if largo > 20000:
                return self._enviar(413, "413")
            datos = json.loads(self.rfile.read(largo).decode("utf-8"))
            if not isinstance(datos, dict):
                raise ValueError
        except Exception:
            return self._enviar(400, "400")
        datos["_idioma"] = "en" if self.headers.get("X-Idioma") == "en" else "es"
        codigo, mensaje = accion(datos)
        self._enviar(codigo, mensaje)

    def log_message(self, *args):
        pass


if __name__ == "__main__":
    PUERTO = int(sys.argv[1]) if len(sys.argv) > 1 else int(config.entorno("DIXI_TOWER_PORT", "DIXI_AGENTES_PUERTO", "4310"))
    servidor = ThreadingHTTPServer(("127.0.0.1", PUERTO), Manejador)
    print(f"Panel de la torre en http://localhost:{PUERTO}/  (Ctrl-C para detener)")
    try:
        servidor.serve_forever()
    except KeyboardInterrupt:
        pass
