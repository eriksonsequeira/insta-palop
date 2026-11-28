"""Análise semanal: o Claude lê as estatísticas e escreve aprendizagens que orientam os próximos conteúdos."""
import json
from datetime import datetime, timezone

from pydantic import BaseModel, Field

from . import brain
from .stats import LEARN, STATS


class Learnings(BaseModel):
    resumo: str = Field(description="2–3 frases: como correu a conta (seguidores, alcance)")
    aprendizagens: list[str] = Field(description="5–8 regras concretas e acionáveis tiradas dos dados "
                                     "(temas, formatos, ganchos, duração, horas) — só o que os números sustentam")
    evitar: list[str] = Field(description="2–4 coisas que os dados mostram que não funcionam")


def table() -> str:
    d = json.loads(STATS.read_text())
    rows = []
    for r in d["media"].values():
        m = r.get("metricas", {})
        rows.append({"data": (r.get("timestamp") or "")[:16], "tipo": r.get("tipo"), "alcance": m.get("reach"),
                     "visualizacoes": m.get("views"), "gostos": r.get("like_count"), "comentarios": r.get("comments_count"),
                     "guardados": m.get("saved"), "partilhas": m.get("shares"), "seguidores_ganhos": m.get("follows"),
                     "inicio_legenda": r.get("legenda_inicio")})
    rows.sort(key=lambda x: x["data"], reverse=True)
    conta = d["conta"][-14:]
    return json.dumps({"conta": conta, "publico": d.get("publico", {}), "publicacoes": rows[:80]}, ensure_ascii=False)


def run() -> None:
    prompt = ("És o analista de crescimento desta conta de Instagram. Abaixo estão as métricas reais das publicações "
              "(as mais recentes primeiro) e a evolução de seguidores. Compara tipos (REELS/FEED/STORY), temas, ganchos "
              "(início da legenda), horas e conteúdos pessoais vs. automáticos. Tira conclusões só do que os números "
              "mostram; se houver poucos dados, diz isso.\n\nDADOS:\n" + table())
    res = brain._parse_cli(prompt, Learnings, tools="", system=False)
    now = datetime.now(timezone.utc).strftime("%d/%m/%Y")
    md = (f"# Aprendizagens (atualizado {now})\n\n{res.resumo}\n\n## Fazer mais\n"
          + "\n".join(f"- {a}" for a in res.aprendizagens) + "\n\n## Evitar\n" + "\n".join(f"- {e}" for e in res.evitar) + "\n")
    LEARN.write_text(md)
    print(md)


def for_prompt() -> str:
    if not LEARN.exists():
        return ""
    return "\n\nAPRENDIZAGENS DOS DADOS DESTA CONTA (segue-as):\n" + LEARN.read_text()[:2500]
