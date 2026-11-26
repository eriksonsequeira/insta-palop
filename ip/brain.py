"""Claude pesquisa a internet, escolhe o tema e escreve o carrossel + legenda."""
import json
import os
import re
import subprocess
from collections import Counter
from datetime import datetime, timezone
from typing import Literal

from pydantic import BaseModel, Field

from .config import CLAUDE_MODEL, IG_HANDLE

PILARES = ["ia", "tecnologia", "negocios"]
FORMATOS = {
    "noticia-explicada": "Uma notícia recente (últimos 7 dias) explicada: o que aconteceu, porque importa, o que muda para quem está nos PALOP.",
    "lista-pratica": "Lista prática e acionável (ferramentas, dicas, prompts, passos) que a pessoa pode usar hoje.",
    "mito-realidade": "Desmontar crenças erradas sobre o tema (mito vs. realidade), com factos verificáveis.",
    "caso-de-negocio": "Caso real de uma empresa/startup (de preferência africana ou lusófona): o que fez, números, lição.",
    "tendencia": "Tendência ou dado recente (relatório, estudo) e o que significa para negócios e carreiras nos PALOP.",
    "passo-a-passo": "Tutorial curto: como fazer algo concreto com IA/tecnologia, passo a passo.",
}

SYSTEM = f"""És o editor de conteúdo da conta de Instagram {IG_HANDLE}, sobre tecnologia, negócios e inteligência artificial.

PÚBLICO: pessoas dos PALOP (Angola, Moçambique, Cabo Verde, Guiné-Bissau, São Tomé e Príncipe) e Portugal —
empreendedores, profissionais, estudantes e curiosos que querem usar tecnologia para crescer.

LÍNGUA: português de Portugal (norma europeia, Acordo Ortográfico de 1990). Nunca português do Brasil
(usa "telemóvel", "ecrã", "equipa", "utilizador", "registar", "partilhar", "aplicação"; nada de gerúndio brasileiro
como "estou fazendo" — escreve "estou a fazer").

QUEM É O AUTOR: Erikson Sequeira, empreendedor angolano que voltou a Angola depois de 20 anos em Portugal
para construir e empreender. Valores: disciplina, ambição, evolução constante, fé. Viaja em trabalho pela Europa.
Os posts que mais funcionam na conta são curiosidades de tecnologia ("Sabias que…", inovações que surpreendem)
explicadas de forma simples. Ocasionalmente (não sempre) podes incluir na legenda uma frase na primeira pessoa
com a perspetiva dele como empreendedor ("Como empreendedor em Angola, vejo…"), sem inventar experiências concretas.

VOZ: direta, confiante, prática, sem jargão desnecessário. Frases curtas. Fala para "tu". Zero clichés de guru
("isto vai mudar a tua vida", "ninguém te conta"). Útil acima de tudo: cada slide tem de ensinar ou provar algo.

RELEVÂNCIA PALOP: sempre que fizer sentido (sem forçar), liga o tema à realidade local — mobile money
(Unitel Money, Multicaixa Express, M-Pesa, e-Mola), custo de dados móveis, economia informal, startups africanas,
oportunidades de emprego remoto, educação, agricultura, governo digital.

FACTOS — REGRA DE OURO:
- Pesquisa na internet ANTES de escrever. Usa só informação que encontraste em fontes fiáveis e recentes.
- Nunca inventes números, datas, citações, nomes de produtos ou empresas. Se não confirmaste, não escrevas.
- Lista em `fontes` os URLs exatos onde confirmaste cada facto.
- Citações e ideias atribuídas a alguém: só o que a fonte diz de facto (parafraseia com fidelidade, sem acrescentar).
- Papéis exatos: "fez a palestra de abertura" não é o mesmo que "abriu o evento"; "segundo X" quando é estimativa.
- Se duas fontes dão números diferentes, não uses esse número (ou usa um termo vago como "centenas").
- Evita conteúdo patrocinado/publirreportagem ("Brand Voice", "Sponsored") como fonte principal.
- Hoje é {{hoje}}. Notícias devem ser dos últimos 7 dias; não apresentes como novidade algo antigo.

FORMATO DOS SLIDES (carrossel 4:5):
- capa_titulo: gancho forte, máx. 60 caracteres. capa_subtitulo: máx. 90.
- 4 a 6 slides de conteúdo: titulo máx. 55 caracteres; texto máx. 230 caracteres;
  destaque opcional (número ou frase muito curta, máx. 18 caracteres) — só se for um dado confirmado.
- cta_titulo: fecho com uma ideia-chave ou pergunta para comentários (máx. 70 caracteres).

LEGENDA: 600–1500 caracteres. Primeira linha = gancho. Desenvolve com valor extra (não repitas só os slides),
termina com uma pergunta para gerar comentários e um "Guarda este post" ou "Partilha com quem precisa".
Inclui "Fonte: <nome do meio>" no fim (sem URLs). NÃO incluas hashtags na legenda.
hashtags: exatamente 5, sem '#', em minúsculas, misturando gerais e de nicho/PALOP.
"""


class Slide(BaseModel):
    titulo: str
    texto: str
    destaque: str | None = Field(default=None, description="número/frase curta confirmada, ou null")


class Post(BaseModel):
    pilar: Literal["ia", "tecnologia", "negocios"]
    formato: str
    tema: str = Field(description="o tema numa frase curta, para evitar repetições no futuro")
    capa_titulo: str
    capa_subtitulo: str
    slides: list[Slide]
    cta_titulo: str
    legenda: str
    hashtags: list[str]
    alt_text: str = Field(description="descrição acessível do carrossel, máx. 250 caracteres")
    fontes: list[str]


def choose_angle(history: list[dict]) -> tuple[str, str]:
    """Alterna pilares e formatos: escolhe o menos usado recentemente."""
    last = history[-12:]
    pc = Counter(p["pilar"] for p in last)
    fc = Counter(p["formato"] for p in last)
    prev_pilar = last[-1]["pilar"] if last else None
    pilar = min((p for p in PILARES if p != prev_pilar), key=lambda p: (pc[p], PILARES.index(p)))
    # notícias são o formato principal (conteúdo fresco da internet), mas alterna com os restantes
    formato = "noticia-explicada" if fc["noticia-explicada"] <= sum(fc.values()) / 3 else \
        min(FORMATOS, key=lambda f: (fc[f], list(FORMATOS).index(f)))
    return pilar, formato


def build_prompt(pilar: str, formato: str, history: list[dict], hint: str = "") -> str:
    temas = "\n".join(f"- [{p['pilar']}] {p['tema']}" for p in history[-40:]) or "(nenhum ainda)"
    nomes = {"ia": "Inteligência Artificial", "tecnologia": "Tecnologia", "negocios": "Negócios e empreendedorismo"}
    return (
        f"Cria o próximo post.\n\nPILAR: {nomes[pilar]} (pilar = \"{pilar}\")\n"
        f"FORMATO: {formato} — {FORMATOS[formato]}\n\n"
        "Começa por pesquisar na internet as notícias/novidades mais relevantes deste pilar nos últimos dias "
        "(fontes internacionais e também africanas/lusófonas). Escolhe o tema com mais interesse para o público "
        "e que NÃO repita nenhum destes temas já publicados:\n"
        f"{temas}\n\n"
        + (f"Indicação extra: {hint}\n\n" if hint else "")
        + "Verifica cada facto com pelo menos uma fonte antes de o usar."
    )


def _system() -> str:
    return SYSTEM.replace("{hoje}", datetime.now(timezone.utc).strftime("%d/%m/%Y"))


def _parse_cli(prompt: str) -> Post:
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}  # usar a subscrição
    cmd = [
        "claude", "-p", f"{_system()}\n\n---\n\n{prompt}",
        "--model", CLAUDE_MODEL, "--output-format", "json",
        "--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch,WebFetch",
        "--json-schema", json.dumps(Post.model_json_schema()),
    ]
    last = None
    for attempt in range(3):
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=1200)
        try:
            data = json.loads(r.stdout)
            if not data.get("is_error") and data.get("structured_output"):
                return Post.model_validate(data["structured_output"])
            last = data.get("result") or data.get("subtype")
        except json.JSONDecodeError:
            last = (r.stderr or r.stdout)[-500:]
        print(f"[claude] tentativa {attempt + 1} falhou: {last}")
    raise RuntimeError(f"Claude Code não devolveu um post válido: {last}")


def _parse_api(prompt: str) -> Post:
    import anthropic
    schema = json.dumps(Post.model_json_schema(), ensure_ascii=False)
    resp = anthropic.Anthropic().messages.create(
        model=CLAUDE_MODEL,
        max_tokens=16000,
        system=_system(),
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 8}],
        messages=[{"role": "user", "content": prompt + "\n\nNo fim, responde APENAS com um objeto JSON válido "
                   f"com este schema:\n{schema}"}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    m = re.search(r"\{.*\}", text, re.S)
    if not m:
        raise RuntimeError(f"Resposta sem JSON: {text[-400:]}")
    return Post.model_validate_json(m.group(0))


def write_post(pilar: str, formato: str, history: list[dict], hint: str = "") -> Post:
    prompt = build_prompt(pilar, formato, history, hint)
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("USE_CLAUDE_CLI") == "1":
        try:
            return _clean(_parse_cli(prompt))
        except Exception as e:  # noqa: BLE001
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise
            print(f"[claude] CLI falhou ({e}); a usar API")
    return _clean(_parse_api(prompt))


def _clean(p: Post) -> Post:
    p.hashtags = [h.lstrip("#").strip().lower().replace(" ", "") for h in p.hashtags][:5]
    p.slides = p.slides[:6]
    return p


# ---------------- Verificação automática (substitui a aprovação humana) ----------------

class Verdict(BaseModel):
    aprovado: bool = Field(description="true só se todos os factos estão confirmados nas fontes e o texto está em PT-PT correto")
    problemas: list[str] = Field(description="lista de erros concretos encontrados (vazia se aprovado)")


VERIFY_RULES = """És um verificador de factos rigoroso. Vais receber um post de Instagram já escrito, em JSON.
1. Abre as fontes indicadas (e pesquisa mais se precisares) e confirma CADA número, data, nome, citação e afirmação.
2. Confirma que a notícia é recente (não apresentada como nova se for antiga) e que nada foi exagerado ou distorcido.
3. Confirma que o texto está em português de Portugal (não do Brasil) e não tem nada ofensivo, político-partidário,
   difamatório, nem conselhos financeiros/médicos perigosos.
Pequenas questões de estilo NÃO reprovam. Reprova só por erros factuais, linguagem errada ou risco reputacional."""


def verify(post: Post) -> Verdict:
    prompt = f"{VERIFY_RULES}\n\nHoje é {datetime.now(timezone.utc):%d/%m/%Y}.\n\nPOST:\n{post.model_dump_json(indent=2)}"
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("USE_CLAUDE_CLI") == "1":
        env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}
        cmd = ["claude", "-p", prompt, "--model", CLAUDE_MODEL, "--output-format", "json",
               "--tools", "WebSearch,WebFetch", "--allowedTools", "WebSearch,WebFetch",
               "--json-schema", json.dumps(Verdict.model_json_schema())]
        for _ in range(2):
            r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=900)
            try:
                data = json.loads(r.stdout)
                if data.get("structured_output"):
                    return Verdict.model_validate(data["structured_output"])
            except json.JSONDecodeError:
                pass
    import anthropic
    resp = anthropic.Anthropic().messages.create(
        model=CLAUDE_MODEL, max_tokens=8000,
        tools=[{"type": "web_search_20250305", "name": "web_search", "max_uses": 6}],
        messages=[{"role": "user", "content": prompt + "\n\nResponde no fim APENAS com JSON: "
                   + json.dumps(Verdict.model_json_schema())}],
    )
    text = "".join(b.text for b in resp.content if getattr(b, "type", "") == "text")
    return Verdict.model_validate_json(re.search(r"\{.*\}", text, re.S).group(0))
