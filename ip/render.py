"""Gera as imagens do carrossel (1080x1350) a partir do template HTML."""
from html import escape
from pathlib import Path

from .brain import PILL_TIPOS, Post, StoryPill
from .config import IG_HANDLE, TEMPLATES

ACCENTS = {"ia": "#A78BFA", "tecnologia": "#2DD4BF", "negocios": "#F5B83D"}
LABELS = {"ia": "Inteligência Artificial", "tecnologia": "Tecnologia", "negocios": "Negócios"}


def _footer(i: int, n: int) -> str:
    dots = "".join(f'<i class="{"on" if j <= i else ""}"></i>' for j in range(n))
    return f'<footer><span class="handle">{escape(IG_HANDLE)}</span><span class="progress">{dots}</span></footer>'


def _cover_title(t: str) -> str:
    """Pinta a última palavra do título com a cor do pilar."""
    words = escape(t).split(" ")
    if len(words) > 2:
        words[-1] = f"<em>{words[-1]}</em>"
    return " ".join(words)


def build_html(post: Post) -> str:
    n = len(post.slides) + 2
    parts = [
        f'<section class="slide cover"><div class="chip">{LABELS[post.pilar]}</div>'
        f"<h1>{_cover_title(post.capa_titulo)}</h1>"
        f'<p class="sub">{escape(post.capa_subtitulo)}</p>'
        f'<div class="swipe">Desliza <span>→</span></div>{_footer(0, n)}</section>'
    ]
    for i, s in enumerate(post.slides, start=1):
        big = ""
        if s.destaque:
            cls = "big small" if len(s.destaque) > 7 else "big"
            big = f'<div class="{cls}">{escape(s.destaque)}</div>'
        parts.append(
            f'<section class="slide content"><div class="num">{i:02d} / {len(post.slides):02d}</div>'
            f"<h2>{escape(s.titulo)}</h2>{big}"
            f'<p class="body{"" if big else " solo"}">{escape(s.texto)}</p>{_footer(i, n)}</section>'
        )
    parts.append(
        f'<section class="slide cta"><div class="chip">Resumo</div><h2>{escape(post.cta_titulo)}</h2>'
        '<div class="actions">'
        '<div class="act"><b>↓</b>Guarda para rever depois</div>'
        '<div class="act"><b>↗</b>Partilha com quem precisa</div>'
        f'<div class="act"><b>+</b>Segue {escape(IG_HANDLE)}</div>'
        f"</div>{_footer(n - 1, n)}</section>"
    )
    tpl = (TEMPLATES / "carousel.html").read_text()
    return tpl.replace("__ACCENT__", ACCENTS[post.pilar]).replace("__SLIDES__", "\n".join(parts))


def build_story_html(post: Post) -> str:
    """Story 1080x1920: título + dado principal + chamada para o post. Respeita as zonas seguras (topo/fundo)."""
    big = ""
    if post.story_gancho:
        big = f'<div class="story-fact"><p class="hook">{escape(post.story_gancho)}</p></div>'

    section = (
        f'<section class="slide story"><div class="chip">{LABELS[post.pilar]}</div>'
        f"<h1>{_cover_title(post.capa_titulo)}</h1>"
        f'<p class="sub">{escape(post.capa_subtitulo)}</p>{big}'
        f'<div class="story-cta"><span>Novo post no meu perfil</span><b>→</b></div>'
        f'<div class="story-handle">{escape(IG_HANDLE)}</div></section>'
    )
    extra = """<style>
  .slide.story { height: 1920px; padding: 250px 88px 340px; }
  .slide.story h1 { margin-top: 64px; font-size: 118px; }
  .slide.story .sub { font-size: 44px; }
  .story-fact { margin-top: 80px; padding-top: 48px; border-top: 2px solid rgba(244,241,234,.12); }
  .story-fact .big { margin: 0; }
  .hook { font: 600 54px/1.25 "Space Grotesk", sans-serif; color: var(--ink); letter-spacing: -.01em; text-wrap: balance; }
  .fact-label { font: 500 38px/1.3 Inter, sans-serif; color: var(--muted); margin-top: 16px; }
  .story-cta { margin-top: auto;
    display: flex; justify-content: space-between; align-items: center;
    background: var(--accent); color: #0A0E1A; border-radius: 28px; padding: 36px 44px;
    font: 700 46px/1 "Space Grotesk", sans-serif; }
  .story-cta b { font-size: 60px; }
  .story-handle { margin-top: 28px; text-align: center; font: 600 32px/1 Inter, sans-serif; color: var(--muted); }
</style>"""
    tpl = (TEMPLATES / "carousel.html").read_text()
    return tpl.replace("__ACCENT__", ACCENTS[post.pilar]).replace("</head>", extra + "</head>").replace("__SLIDES__", section)


STORY_CSS = """<style>
  .slide.story { height: 1920px; padding: 250px 88px 340px; }
  .slide.story h1 { margin-top: 64px; font-size: 118px; }
  .slide.story .sub { font-size: 44px; }
  .story-fact { margin-top: 80px; padding-top: 48px; border-top: 2px solid rgba(244,241,234,.12); }
  .story-fact .big { margin: 0; }
  .hook { font: 600 54px/1.25 "Space Grotesk", sans-serif; color: var(--ink); letter-spacing: -.01em; text-wrap: balance; }
  .story-cta { margin-top: auto; display: flex; justify-content: space-between; align-items: center;
    background: var(--accent); color: #0A0E1A; border-radius: 28px; padding: 36px 44px;
    font: 700 46px/1 "Space Grotesk", sans-serif; }
  .story-cta b { font-size: 60px; }
  .story-handle { margin-top: 28px; text-align: center; font: 600 32px/1 Inter, sans-serif; color: var(--muted); }
  .pill .big { margin-top: auto; font-size: 230px; }
  .pill .big.small { font-size: 150px; }
  .pill h2 { font-size: 92px; margin-top: 48px; }
  .pill .big + h2 { margin-top: 28px; }
  .pill .chip + h2 { margin-top: auto; }
  .pill .body { margin-top: 44px; font-size: 48px; line-height: 1.4; color: #D9DCE5; }
  .pill .src { margin-top: 36px; font: 500 30px/1 Inter, sans-serif; color: var(--muted); }
  .pill .follow { margin-top: 72px; border: 2px solid var(--accent); color: var(--ink); border-radius: 28px;
    padding: 32px 44px; font: 600 40px/1.2 Inter, sans-serif; text-align: center; }
  .pill .follow b { color: var(--accent); }
</style>"""


def build_pill_html(p: StoryPill) -> str:
    big = ""
    if p.destaque:
        cls = "big small" if len(p.destaque) > 6 else "big"
        big = f'<div class="{cls}">{escape(p.destaque)}</div>'
    section = (
        f'<section class="slide story pill"><div class="chip">{escape(PILL_TIPOS.get(p.tipo, ("Tech",))[0])}</div>'
        f"{big}<h2>{escape(p.titulo)}</h2>"
        f'<p class="body">{escape(p.texto)}</p>'
        f'<p class="src">Fonte: {escape(p.fonte_nome)}</p>'
        f'<div class="follow">Segue <b>{escape(IG_HANDLE)}</b> para mais tecnologia, IA e negócios</div></section>'
    )
    tpl = (TEMPLATES / "carousel.html").read_text()
    return tpl.replace("__ACCENT__", ACCENTS[p.pilar]).replace("</head>", STORY_CSS + "</head>").replace("__SLIDES__", section)


def render_pill(p: StoryPill, out_dir: Path) -> Path:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as pw:
        browser = pw.chromium.launch()
        f = _shoot(build_pill_html(p), out_dir, "story", (1080, 1920), browser.new_page())[0]
        browser.close()
    return f


def _shoot(html_text: str, out_dir: Path, name: str, size: tuple[int, int], page) -> list[Path]:
    html = out_dir / f"_{name}.html"
    html.write_text(html_text)
    page.set_viewport_size({"width": size[0], "height": size[1]})
    page.goto(html.resolve().as_uri(), wait_until="networkidle")
    page.evaluate("document.fonts.ready")
    files = []
    els = page.query_selector_all("section.slide")
    for i, el in enumerate(els, start=1):
        f = out_dir / (f"{name}.jpg" if len(els) == 1 and name == "story" else f"{i:02d}.jpg")
        el.screenshot(path=str(f), type="jpeg", quality=92)
        files.append(f)
    html.unlink()
    return files


def render_story(post: Post, out_dir: Path) -> Path:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    with sync_playwright() as p:
        browser = p.chromium.launch()
        f = _shoot(build_story_html(post), out_dir, "story", (1080, 1920), browser.new_page())[0]
        browser.close()
    return f


def render(post: Post, out_dir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    out_dir.mkdir(parents=True, exist_ok=True)
    html = out_dir / "slides.html"
    html.write_text(build_html(post))
    files = []
    with sync_playwright() as p:
        browser = p.chromium.launch()
        page = browser.new_page(viewport={"width": 1080, "height": 1350})
        page.goto(html.resolve().as_uri(), wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        for i, el in enumerate(page.query_selector_all("section.slide"), start=1):
            f = out_dir / f"{i:02d}.jpg"
            el.screenshot(path=str(f), type="jpeg", quality=92)
            files.append(f)
        browser.close()
    html.unlink()
    return files
