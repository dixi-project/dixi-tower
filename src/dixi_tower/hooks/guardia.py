"""Barrera PreToolUse(Bash) de los agentes locales.

Se suma a los hooks propios de cada proyecto; cubre también a los proyectos que
aún no tienen el motor instalado. Bloquea (exit 2) lo que un agente local nunca
hace: integrar, publicar en la rama base, desplegar, operar AWS o leer secretos.
Es una barrera de expresiones regulares: reduce el riesgo, no sustituye la
revisión humana del PR.
"""
import json
import os
import re
import sys

if not os.environ.get("DIXI_AGENTE"):
    sys.exit(0)
try:
    cmd = (json.load(sys.stdin).get("tool_input") or {}).get("command", "")
except Exception:
    sys.exit(0)



def bloquear(clave):
    """Bloquea con el motivo en el idioma del agente. Si los textos no cargan, bloquea igual."""
    try:
        sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
        from mensajes import t
        texto = t("h_bloqueado", motivo=t(clave))
    except Exception:
        texto = f"Blocked by the local agent guard: {clave}."
    print(texto, file=sys.stderr)
    sys.exit(2)


base = re.escape(os.environ.get("DIXI_AGENTE_BASE", "main"))
REGLAS = [
    (r"\bgh\s+pr\s+merge\b", "g_merge"),
    (r"\bgh\s+pr\s+review\b.*--approve", "g_aprobar"),
    (r"\bgit\s+push\b.*(\s--force|\s-f\b|\s\+)", "g_force"),
    (rf"\bgit\s+push\b[^|;&]*[\s:]({base}|main|master|develop)(\s|$)", "g_base"),
    (r"\b(cdk|sam|serverless|sls|amplify|eas)\s+(deploy|publish|push|submit)\b", "g_desplegar"),
    (r"\bterraform\s+(apply|destroy)\b", "g_iac"),
    (r"\bnpm\s+publish\b", "g_publicar"),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+(/|~|\$HOME)/?(\s|$)", "g_borrado"),
    (r"(^|[\s;&|])(cat|less|more|head|tail|source|\.)\s+\S*\.env(\.(?!example)\w+)?(\s|$)", "g_secretos"),
    (r"\b(DROP\s+(DATABASE|TABLE)|TRUNCATE\s+TABLE)\b", "g_ddl"),
]
for patron, clave in REGLAS:
    if re.search(patron, cmd, re.IGNORECASE):
        bloquear(clave)

# AWS: solo lectura.
for servicio, op in re.findall(r"\baws\s+(\S+)\s+(\S+)", cmd):
    if servicio.startswith("-") or not re.match(r"^(get|list|describe|ls|help|wait|head)", op):
        bloquear("g_aws")
sys.exit(0)
