"""Agenda: decide o que já devia ter saído hoje (hora de Lisboa) e lança UMA tarefa de cada vez.
Corre de 15 em 15 min (agendador do GitHub + "despertador" externo). Se uma verificação falhar, a seguinte apanha o atraso."""
import json
import subprocess
from datetime import datetime, timedelta
from zoneinfo import ZoneInfo

from .config import ROOT

TZ = ZoneInfo("Europe/Lisbon")
FILE = ROOT / "agenda.json"
BUSY_NAMES = {"Reel diário", "Criar post", "Stories avulsos", "Estatísticas"}

# (nome, hora Lisboa, workflow, janela máxima de atraso em horas)
SLOTS = [
    ("estatisticas", "05:05", "stats.yml", 18),
    ("reel_manha", "08:15", "reels.yml", 4),
    ("carrossel", "11:45", "post.yml", 4),
    ("story_tarde", "15:15", "stories.yml", 3),
    ("reel_noite", "19:15", "reels.yml", 3),
    ("story_noite", "21:50", "stories.yml", 1.5),
]


def _busy() -> bool:
    """Há alguma tarefa de conteúdo a correr ou em fila? (o grupo de concorrência só guarda 1 em espera)"""
    out = subprocess.run(["gh", "run", "list", "--limit", "20", "--json", "workflowName,status"],
                         capture_output=True, text=True, check=True).stdout
    return any(r["status"] in ("queued", "in_progress", "waiting", "pending", "requested")
               and r["workflowName"] in BUSY_NAMES for r in json.loads(out))


def tick() -> None:
    now = datetime.now(TZ)
    today = now.strftime("%Y-%m-%d")
    data = json.loads(FILE.read_text()) if FILE.exists() else {}
    done = data.setdefault(today, [])
    for k in [k for k in data if k < (now - timedelta(days=7)).strftime("%Y-%m-%d")]:
        data.pop(k)
    due = []
    for name, hhmm, wf, max_late in SLOTS:
        h, m = map(int, hhmm.split(":"))
        at = now.replace(hour=h, minute=m, second=0, microsecond=0)
        if name in done or now < at:
            continue
        if now - at > timedelta(hours=max_late):
            print(f"[agenda] {name} ({hhmm}) passou da janela — saltado")
            done.append(name)
            continue
        due.append((name, hhmm, wf))
    if due:
        if _busy():
            print(f"[agenda] pendentes {[d[0] for d in due]}, mas há uma tarefa a correr — fica para a próxima verificação")
        else:
            name, hhmm, wf = due[0]
            subprocess.run(["gh", "workflow", "run", wf], check=True)
            done.append(name)
            print(f"[agenda] lançado {name} ({hhmm} Lisboa) → {wf}")
    else:
        print(f"[agenda] {now:%H:%M} Lisboa — nada pendente (feito hoje: {done})")
    FILE.write_text(json.dumps(data, indent=1) + "\n")


if __name__ == "__main__":
    tick()
