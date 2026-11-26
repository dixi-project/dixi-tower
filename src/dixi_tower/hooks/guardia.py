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

base = re.escape(os.environ.get("DIXI_AGENTE_BASE", "main"))
REGLAS = [
    (r"\bgh\s+pr\s+merge\b", "integrar un PR es de una persona"),
    (r"\bgh\s+pr\s+review\b.*--approve", "aprobar un PR es de una persona"),
    (r"\bgit\s+push\b.*(\s--force|\s-f\b|\s\+)", "force push prohibido"),
    (rf"\bgit\s+push\b[^|;&]*[\s:]({base}|main|master|develop)(\s|$)", "no se publica en la rama base: solo ramas st/"),
    (r"\b(cdk|sam|serverless|sls|amplify|eas)\s+(deploy|publish|push|submit)\b", "desplegar no es del agente"),
    (r"\bterraform\s+(apply|destroy)\b", "aplicar IaC no es del agente"),
    (r"\bnpm\s+publish\b", "publicar paquetes no es del agente"),
    (r"\brm\s+-[a-zA-Z]*r[a-zA-Z]*\s+(/|~|\$HOME)/?(\s|$)", "borrado catastrófico"),
    (r"(^|[\s;&|])(cat|less|more|head|tail|source|\.)\s+\S*\.env(\.(?!example)\w+)?(\s|$)", "no se leen secretos; mira .env.example"),
    (r"\b(DROP\s+(DATABASE|TABLE)|TRUNCATE\s+TABLE)\b", "DDL destructivo"),
]
for patron, motivo in REGLAS:
    if re.search(patron, cmd, re.IGNORECASE):
        print(f"Bloqueado por la barrera de agentes locales: {motivo}.", file=sys.stderr)
        sys.exit(2)

# AWS: solo lectura.
for servicio, op in re.findall(r"\baws\s+(\S+)\s+(\S+)", cmd):
    if servicio.startswith("-") or not re.match(r"^(get|list|describe|ls|help|wait|head)", op):
        print("Bloqueado por la barrera de agentes locales: AWS solo en lectura.", file=sys.stderr)
        sys.exit(2)
sys.exit(0)
