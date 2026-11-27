"""Analiza un tasks/TASKS.md (por stdin) con las casillas de sys_task.

  tareas.py lista        candidatas [ ] con id estable, por prioridad y orden
  tareas.py revision     cuántas tareas están en [r]
  tareas.py una <st-id>  "título<TAB>slug<TAB>línea" de esa tarea
  tareas.py slug         "título<TAB>slug" a partir de una instrucción libre
"""
import re
import sys
import unicodedata

from mensajes import t

LINEA = re.compile(r"^\s*- \[(.)\] (.*)$")
ST = re.compile(r"<!--\s*st:([0-9a-f]+)\s*-->")
TITULO = re.compile(r"\*\*(.+?)\*\*")
PRIO = re.compile(r"_\(P(\d)\)_")


def slug(texto, largo=40):
    plano = unicodedata.normalize("NFKD", texto).encode("ascii", "ignore").decode()
    return re.sub(r"[^a-z0-9]+", "-", plano.lower()).strip("-")[:largo].strip("-")


def leer():
    filas = []
    for n, cruda in enumerate(sys.stdin.read().splitlines(), 1):
        m = LINEA.match(cruda)
        if not m:
            continue
        marca, resto = m.groups()
        st = ST.search(resto)
        t = TITULO.search(resto)
        p = PRIO.search(resto)
        filas.append({
            "n": n, "marca": marca, "linea": cruda.strip(),
            "id": st.group(1) if st else None,
            "titulo": t.group(1) if t else ST.sub("", resto).strip(),
            "prio": int(p.group(1)) if p else 9,
            "bloqueada": "bloquead" in resto.lower(),
        })
    return filas


def main():
    modo = sys.argv[1] if len(sys.argv) > 1 else "lista"
    if modo == "slug":
        primera = next((l.strip() for l in sys.stdin.read().splitlines() if l.strip()), "")
        titulo = " ".join(primera.split())[:90]
        print(f"{titulo}\t{slug(titulo) or 'tarea'}")
        return
    filas = leer()
    if modo == "revision":
        print(sum(1 for f in filas if f["marca"] == "r"))
    elif modo == "una":
        for f in filas:
            if f["id"] == sys.argv[2]:
                print(f"{f['titulo']}\t{slug(f['titulo'])}\t{f['linea']}")
                return
        sys.exit(t("tarea_no_encontrada", id=sys.argv[2]))
    else:
        cand = [f for f in filas if f["marca"] == " " and f["id"] and not f["bloqueada"]]
        cand.sort(key=lambda f: (f["prio"], f["n"]))
        for f in cand[:15]:
            prio = f"P{f['prio']}" if f["prio"] < 9 else "--"
            print(f"{prio}  st:{f['id']}  {f['titulo'][:110]}")
        print(t("candidatas", n=len(cand)))


if __name__ == "__main__":
    main()
