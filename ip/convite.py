"""Convite para seguir a página: obrigatório em todos os conteúdos, sempre ORIGINAL e ligado ao tema.
Guardamos os últimos convites no histórico para nunca se repetirem."""
from .config import IG_HANDLE

RULES = f"""CONVITE PARA SEGUIR (obrigatório, sempre diferente e criativo):
Uma frase ÚNICA que convida a pessoa a seguir a página {IG_HANDLE} SE gostou do conteúdo.
- Tem de NASCER DO TEMA deste conteúdo: um trocadilho com o assunto, uma comparação com um número da notícia,
  uma piada inteligente, um "plot twist", uma promessa concreta ligada ao tema. Quem o lê deve sorrir e pensar
  "isto só podia ser desta página".
- Português de Portugal, trata por "tu", tom confiante e simpático (nunca pedinte nem agressivo). Máx. 120 caracteres.
- PROIBIDO (clichés): "segue para mais conteúdo", "não te esqueças de seguir", "ativa as notificações",
  "segue-me", "deixa o teu like", "se gostaste, segue", "para mais dicas como esta".
- Não inventes factos: se usares um número, tem de ser um número deste conteúdo.
Exemplos do ESPÍRITO pretendido (NÃO copies, cria sempre um novo):
  · Black Friday → "O único desconto que nunca acaba: seguir {IG_HANDLE} custa 0 €."
  · Satélites de IA → "Se isto te pôs em órbita, aterra aqui: segue {IG_HANDLE}."
  · M-Pesa → "Mais rápido do que um M-Pesa: um toque em Seguir e ficas sempre a par."
  · GTA VI sem IA → "Nenhuma IA escreveu este convite: segue {IG_HANDLE} para mais histórias assim."
"""


def recent(state: dict, n: int = 15) -> list[str]:
    return [c for c in state.get("convites", [])][-n:]


def remember(state: dict, text: str) -> None:
    if text:
        state.setdefault("convites", []).append(text.strip())
        state["convites"] = state["convites"][-40:]


def avoid_block(state: dict) -> str:
    r = recent(state)
    return ("Convites já usados (NÃO repitas nem faças parecido):\n" + "\n".join(f"- {c}" for c in r) + "\n") if r else ""


def with_invite(legenda: str, convite: str) -> str:
    """Põe o convite na legenda, antes da linha "Fonte:" (ou no fim), se ainda lá não estiver."""
    legenda, convite = legenda.strip(), (convite or "").strip()
    if not convite or convite in legenda:
        return legenda
    lines = legenda.split("\n")
    for i in range(len(lines) - 1, -1, -1):
        if lines[i].strip().lower().startswith(("fonte:", "fontes:")):
            return "\n".join(lines[:i]).rstrip() + f"\n\n{convite}\n\n" + "\n".join(lines[i:]).lstrip()
    return f"{legenda}\n\n{convite}"
