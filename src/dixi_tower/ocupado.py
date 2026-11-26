"""Sale con 0 si un agente vivo ya usa ese worktree.

  tmux list-windows … | ocupado.py <carpeta-estado> <worktree>
"""
import glob
import json
import os
import sys

estado, wt = sys.argv[1:3]
vivas = set(sys.stdin.read().split("\n"))
for f in glob.glob(os.path.join(estado, "*.json")):
    try:
        d = json.load(open(f, encoding="utf-8"))
    except Exception:
        continue
    nombre = d.get("agente") or d.get("proyecto")
    if nombre in vivas and d.get("worktree") == wt:
        sys.exit(0)
sys.exit(1)
