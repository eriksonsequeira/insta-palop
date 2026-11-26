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
    "hype": "Tema EM ALTA esta semana (o que toda a gente está a comentar: jogos como o GTA 6, filmes/séries, futebol, música, memes virais, lançamentos, celebridades, eventos). Primeiro descobre o que está mesmo em tendência (Google Trends, YouTube, X/TikTok, notícias) e depois liga-o de forma inteligente a tecnologia, IA ou negócios: os números do negócio, a tecnologia por trás, a estratégia de marketing, a lição para empreendedores. O gancho é o hype; o valor é a ligação. Evita política partidária, tragédias e polémicas pessoais.",
}

SYSTEM = f"""És o editor de conteúdo da conta de Instagram {IG_HANDLE}, sobre tecnologia, negócios e inteligência artificial.

PÚBLICO: pessoas dos PALOP (Cabo Verde, Angola, Moçambique, Guiné-Bissau, São Tomé e Príncipe) e Portugal —
empreendedores, profissionais, estudantes e curiosos que querem usar tecnologia para crescer.

LÍNGUA: português de Portugal (norma europeia, Acordo Ortográfico de 1990). Nunca português do Brasil
(usa "telemóvel", "ecrã", "equipa", "utilizador", "registar", "partilhar", "aplicação"; nada de gerúndio brasileiro
como "estou fazendo" — escreve "estou a fazer").

QUEM É O AUTOR: Erikson Sequeira, empreendedor cabo-verdiano que voltou ao seu país (Cabo Verde) depois de
20 anos fora, para construir e empreender. NUNCA digas que ele é angolano nem que vive/empreende em Angola. Valores: disciplina, ambição, evolução constante, fé. Viaja em trabalho pela Europa.
Os posts que mais funcionam na conta são curiosidades de tecnologia ("Sabias que…", inovações que surpreendem)
explicadas de forma simples. Ocasionalmente (não sempre) podes incluir na legenda uma frase na primeira pessoa
com a perspetiva dele como empreendedor ("Como empreendedor cabo-verdiano, vejo…"), sem inventar experiências concretas.

VOZ: direta, confiante, prática, sem jargão desnecessário. Frases curtas. Fala para "tu". Zero clichés de guru
("isto vai mudar a tua vida", "ninguém te conta"). Útil acima de tudo: cada slide tem de ensinar ou provar algo.

RELEVÂNCIA PALOP: sempre que fizer sentido (sem forçar), liga o tema à realidade local — pagamentos digitais
(vinti4 em Cabo Verde, Multicaixa Express/Unitel Money em Angola, M-Pesa/e-Mola em Moçambique, Orange Money),
turismo e economia azul (Cabo Verde), diáspora, custo de dados móveis, economia informal, startups africanas,
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
- story_gancho: uma frase para o Story que se percebe sozinha (sem precisar do resto do post), máx. 110 caracteres.
- cta_titulo: fecho com uma ideia-chave ou pergunta para comentários (máx. 70 caracteres).

LEGENDA: 600–1500 caracteres. Primeira linha = gancho. Desenvolve com valor extra (não repitas só os slides),
termina com uma pergunta para gerar comentários e um "Guarda este post" ou "Partilha com quem precisa".
Inclui "Fonte: <nome do meio>" no fim (sem URLs). NÃO incluas hashtags na legenda.
hashtags: exatamente 5, sem '#', em minúsculas, misturando gerais e de nicho/PALOP (o país só se o post for sobre ele).
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
    story_gancho: str = Field(default="", description="frase curta para o Story (máx. 110 caracteres) que faz "
                              "a pessoa querer ver o post; autoexplicativa e factual, pode incluir um número confirmado")
    fontes: list[str]


FOCOS = {
    "global": "Notícia/tema GLOBAL (EUA, Europa, Ásia — grandes empresas de IA e tecnologia, tendências mundiais). "
              "No fim liga ao que significa para quem está nos PALOP. Não centres o post num único país africano.",
    "cabo-verde": "Tema com foco em CABO VERDE (startups, governo digital, turismo, economia azul, conectividade, diáspora).",
    "mocambique": "Tema com foco em MOÇAMBIQUE.",
    "angola": "Tema com foco em ANGOLA.",
    "africa": "Tema sobre ÁFRICA em geral (startups, investimento, inovação africana — Nigéria, Quénia, África do Sul, etc.).",
    "guine-stp": "Tema com foco na GUINÉ-BISSAU ou em SÃO TOMÉ E PRÍNCIPE (se não houver notícias recentes relevantes, usa os PALOP em geral).",
    "lusofonia": "Tema de PORTUGAL ou BRASIL com interesse para os PALOP (startups, IA, investimento, oportunidades).",
}
# metade global, o resto em rotação
FOCO_CICLO = ["global", "cabo-verde", "global", "africa", "global", "mocambique",
              "global", "angola", "global", "lusofonia", "global", "guine-stp"]


def choose_foco(history: list[dict]) -> str:
    return FOCO_CICLO[len(history) % len(FOCO_CICLO)]


def choose_angle(history: list[dict]) -> tuple[str, str]:
    """Alterna pilares e formatos: escolhe o menos usado recentemente."""
    last = history[-12:]
    pc = Counter(p["pilar"] for p in last)
    fc = Counter(p["formato"] for p in last)
    prev_pilar = last[-1]["pilar"] if last else None
    pilar = min((p for p in PILARES if p != prev_pilar), key=lambda p: (pc[p], PILARES.index(p)))
    # um post "em alta" a cada 4; notícias são o formato principal; o resto alterna
    if history and all(p.get("formato") != "hype" for p in history[-3:]):
        return pilar, "hype"
    fc.pop("hype", None)
    formato = "noticia-explicada" if fc["noticia-explicada"] <= sum(fc.values()) / 3 else \
        min((f for f in FORMATOS if f != "hype"), key=lambda f: (fc[f], list(FORMATOS).index(f)))
    return pilar, formato


def build_prompt(pilar: str, formato: str, history: list[dict], hint: str = "", foco: str = "global") -> str:
    temas = "\n".join(f"- [{p['pilar']}] {p['tema']}" for p in history[-40:]) or "(nenhum ainda)"
    nomes = {"ia": "Inteligência Artificial", "tecnologia": "Tecnologia", "negocios": "Negócios e empreendedorismo"}
    return (
        f"Cria o próximo post.\n\nPILAR: {nomes[pilar]} (pilar = \"{pilar}\")\n"
        f"FORMATO: {formato} — {FORMATOS[formato]}\n"
        + (f"FOCO GEOGRÁFICO: {FOCOS[foco]}\n\n" if formato != "hype" else
           "FOCO GEOGRÁFICO: o que estiver em alta a nível global ou nos PALOP (prefere o maior hype).\n\n")
        + ("Começa por pesquisar o que está em tendência ESTA SEMANA (o assunto do momento) e só depois a ligação "
           "ao pilar. " if formato == "hype" else
           "Começa por pesquisar na internet as notícias/novidades mais relevantes deste pilar nos últimos dias "
           "(fontes internacionais e também africanas/lusófonas). ")
        + "Escolhe o tema com mais interesse para o público e que NÃO repita nenhum destes temas já publicados:\n"
        f"{temas}\n\n"
        + (f"Indicação extra: {hint}\n\n" if hint else "")
        + "Verifica cada facto com pelo menos uma fonte antes de o usar."
    )


def _system() -> str:
    from .learn import for_prompt
    return SYSTEM.replace("{hoje}", datetime.now(timezone.utc).strftime("%d/%m/%Y")) + for_prompt()


def _parse_cli(prompt: str, model=None, tools: str = "WebSearch,WebFetch", cwd: str | None = None, system: bool = True):
    model = model or Post
    env = {k: v for k, v in os.environ.items() if k != "ANTHROPIC_API_KEY"}  # usar a subscrição
    cmd = [
        "claude", "-p", f"{_system()}\n\n---\n\n{prompt}" if system else prompt,
        "--model", CLAUDE_MODEL, "--output-format", "json",
        "--tools", tools, "--allowedTools", tools,
        "--json-schema", json.dumps(model.model_json_schema()),
    ]
    last = None
    for attempt in range(3):
        r = subprocess.run(cmd, capture_output=True, text=True, env=env, timeout=1200, cwd=cwd)
        try:
            data = json.loads(r.stdout)
            if not data.get("is_error") and data.get("structured_output"):
                return model.model_validate(data["structured_output"])
            last = data.get("result") or data.get("subtype")
        except json.JSONDecodeError:
            last = (r.stderr or r.stdout)[-500:]
        print(f"[claude] tentativa {attempt + 1} falhou: {last}")
    raise RuntimeError(f"Claude Code não devolveu um post válido: {last}")


def _parse_api(prompt: str, model=None):
    model = model or Post
    import anthropic
    schema = json.dumps(model.model_json_schema(), ensure_ascii=False)
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
    return model.model_validate_json(m.group(0))


def write_post(pilar: str, formato: str, history: list[dict], hint: str = "", foco: str = "global") -> Post:
    prompt = build_prompt(pilar, formato, history, hint, foco)
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
2. Se o post é sobre um tema "em alta", confirma que está mesmo em tendência agora e que a ligação a tecnologia/negócios é factual.
   Confirma que a notícia é recente (não apresentada como nova se for antiga) e que nada foi exagerado ou distorcido.
3. Confirma que o texto está em português de Portugal (não do Brasil) e não tem nada ofensivo, político-partidário,
   difamatório, nem conselhos financeiros/médicos perigosos.
4. O autor (Erikson Sequeira) é cabo-verdiano: reprova se o texto disser que ele é angolano ou empreende em Angola.
Pequenas questões de estilo NÃO reprovam. Reprova só por erros factuais, linguagem errada ou risco reputacional."""


def verify(post: BaseModel) -> Verdict:
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


# ---------------- Stories avulsos (curiosidades, dados, ferramentas, dicas) ----------------

PILL_TIPOS = {
    "curiosidade": ("Sabias que?", "Uma curiosidade surpreendente e verdadeira de tecnologia/IA/negócios (invenções, recordes, histórias de empresas, ciência aplicada)."),
    "dado": ("Dado do dia", "Um número recente e impactante (estudo, relatório, resultados de empresa) — o destaque é esse número."),
    "ferramenta": ("Ferramenta do dia", "Uma ferramenta/app/site útil (de preferência gratuita) de IA ou produtividade: o que faz e para que serve."),
    "dica": ("Dica rápida", "Uma dica prática aplicável em 1 minuto (prompt útil, atalho, truque de negócio, segurança digital)."),
    "hype": ("Em alta", "O assunto mais comentado do momento (jogo, filme, futebol, música, meme, lançamento) ligado a tecnologia, IA ou negócios — ex.: quanto custou, que tecnologia usa, quanto fatura, o que ensina a quem empreende."),
    "noticia": ("Última hora", "Uma notícia das últimas 48 horas de IA, tecnologia ou negócios, explicada numa frase."),
}
PILL_CICLO = ["noticia", "hype", "curiosidade", "ferramenta", "hype", "dado", "dica", "curiosidade"]


class StoryPill(BaseModel):
    tipo: str
    pilar: Literal["ia", "tecnologia", "negocios"]
    tema: str = Field(description="tema numa frase curta, para não repetir")
    titulo: str = Field(description="máx. 70 caracteres, gancho forte")
    texto: str = Field(description="máx. 190 caracteres, explica/acrescenta valor")
    destaque: str | None = Field(default=None, description="número ou palavra curta (máx. 12 caracteres), só se confirmado")
    fonte_nome: str = Field(description="nome do meio/empresa fonte (ex.: Reuters), sem URL")
    fontes: list[str]


def choose_pill(stories: list[dict]) -> tuple[str, str]:
    tipo = PILL_CICLO[len(stories) % len(PILL_CICLO)]
    pc = Counter(p["pilar"] for p in stories[-6:])
    pilar = min(PILARES, key=lambda p: (pc[p], PILARES.index(p)))
    return tipo, pilar


def write_pill(tipo: str, pilar: str, history: list[dict], hint: str = "") -> StoryPill:
    nomes = {"ia": "Inteligência Artificial", "tecnologia": "Tecnologia", "negocios": "Negócios"}
    temas = "\n".join(f"- {p['tema']}" for p in history[-60:]) or "(nenhum)"
    prompt = (
        f"Cria UM Story de Instagram (uma única imagem vertical, lida em 5 segundos).\n\n"
        f"TIPO: {tipo} — {PILL_TIPOS[tipo][1]}\nPILAR: {nomes[pilar]} (pilar = \"{pilar}\")\n\n"
        "Pesquisa na internet primeiro. Pode ser global ou dos PALOP — o que for mais interessante. "
        "Texto curtíssimo e claro, PT-PT. Não repitas estes temas já usados:\n"
        f"{temas}\n\n" + (f"Indicação extra: {hint}\n\n" if hint else "")
        + f'Usa tipo = "{tipo}". Nada de legendas nem hashtags.'
    )
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("USE_CLAUDE_CLI") == "1":
        try:
            return _parse_cli(prompt, StoryPill)
        except Exception as e:  # noqa: BLE001
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise
            print(f"[claude] CLI falhou ({e}); a usar API")
    return _parse_api(prompt, StoryPill)
