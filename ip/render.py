"""Gera as imagens do carrossel (1080x1350) a partir do template HTML."""
from html import escape
from pathlib import Path

from .brain import Post
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
