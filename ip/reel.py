"""Reels: guião (Claude) → narração PT-PT (edge-tts) → cenas verticais (Playwright) → vídeo (ffmpeg)."""
import asyncio
import json
import os
import subprocess
from html import escape
from pathlib import Path

from pydantic import BaseModel, Field

from . import brain
from .config import IG_HANDLE, TEMPLATES
from .render import ACCENTS, LABELS, STORY_CSS

VOICE = os.environ.get("REEL_VOICE", "pt-PT-DuarteNeural")
FPS = 30


class Cena(BaseModel):
    fala: str = Field(description="o que a voz diz nesta cena: 1–2 frases, máx. 28 palavras, PT-PT falado e natural")
    titulo: str = Field(description="texto grande no ecrã, máx. 45 caracteres")
    destaque: str | None = Field(default=None, description="número/palavra curta confirmada (máx. 12 caracteres) ou null")


class ReelScript(BaseModel):
    cenas: list[Cena] = Field(description="5 a 7 cenas; a 1.ª é o gancho (pergunta ou dado chocante), a última o fecho")
    legenda: str = Field(description="legenda do Reel, 300–900 caracteres, termina com pergunta; sem hashtags")
    hashtags: list[str]


RULES = """Transforma este post de Instagram (já verificado) num guião de REEL vertical de 30 a 45 segundos, narrado.
- Cena 1 = gancho nos primeiros 2 segundos: pergunta intrigante ou o dado mais surpreendente. Nada de "Olá" nem apresentações.
- Frases curtas, ritmo rápido, linguagem falada de Portugal (tu). Números escritos como se dizem ("três vírgula oito mil milhões").
- Usa SÓ os factos do post (não acrescentes factos novos).
- Última cena: conclusão + "Segue para mais" (curto).
- O texto do ecrã (titulo) resume a cena; o destaque é opcional.
- hashtags: exatamente 5, sem '#', minúsculas."""


def write_script(post: dict, fix: str = "") -> ReelScript:
    data = {k: post[k] for k in ("pilar", "tema", "capa_titulo", "capa_subtitulo", "slides", "cta_titulo", "fontes")}
    prompt = f"{RULES}\n\nPOST:\n{json.dumps(data, ensure_ascii=False, indent=1)}"
    if fix:
        prompt += f"\n\nUm verificador reprovou a versão anterior. Corrige TODOS estes pontos:\n{fix}"
    if os.environ.get("CLAUDE_CODE_OAUTH_TOKEN") or os.environ.get("USE_CLAUDE_CLI") == "1":
        try:
            return brain._parse_cli(prompt, ReelScript)
        except Exception as e:  # noqa: BLE001
            if not os.environ.get("ANTHROPIC_API_KEY"):
                raise
            print(f"[reel] CLI falhou ({e}); a usar API")
    return brain._parse_api(prompt, ReelScript)


# ---------------- áudio ----------------

def _tts(text: str, out: Path) -> None:
    import edge_tts
    asyncio.run(edge_tts.Communicate(text, VOICE, rate="+8%").save(str(out)))


def _dur(f: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


# ---------------- imagens ----------------

SCENE_CSS = """<style>
  .scene { justify-content: center; }
  .scene .big { margin-top: 0; font-size: 210px; }
  .scene .big.small { font-size: 140px; }
  .scene h2 { font-size: 100px; margin-top: 36px; }
  .scene .chip { position: absolute !important; top: 250px; left: 88px; }
  .scene .sub-box { position: absolute !important; left: 64px; right: 64px; bottom: 380px;
    background: rgba(0,0,0,.55); border-radius: 24px; padding: 28px 36px;
    font: 600 44px/1.3 Inter, sans-serif; color: #fff; text-align: center; }
  .scene .tag { position: absolute !important; left: 0; right: 0; bottom: 300px; text-align: center;
    font: 600 30px/1 Inter, sans-serif; color: var(--muted); }
</style>"""


def _scene_html(c: Cena, pilar: str, first: bool) -> str:
    big = ""
    if c.destaque:
        cls = "big small" if len(c.destaque) > 6 else "big"
        big = f'<div class="{cls}">{escape(c.destaque)}</div>'
    chip = f'<div class="chip">{LABELS[pilar]}</div>' if first else ""
    return (f'<section class="slide story scene">{chip}{big}<h2>{escape(c.titulo)}</h2>'
            f'<div class="sub-box">{escape(c.fala)}</div><div class="tag">{escape(IG_HANDLE)}</div></section>')


def _render_scenes(script: ReelScript, pilar: str, out_dir: Path) -> list[Path]:
    from playwright.sync_api import sync_playwright

    sections = "\n".join(_scene_html(c, pilar, i == 0) for i, c in enumerate(script.cenas))
    tpl = (TEMPLATES / "carousel.html").read_text()
    html = tpl.replace("__ACCENT__", ACCENTS[pilar]).replace("</head>", STORY_CSS + SCENE_CSS + "</head>") \
              .replace("__SLIDES__", sections)
    f = out_dir / "_scenes.html"
    f.write_text(html)
    files = []
    with sync_playwright() as p:
        b = p.chromium.launch()
        page = b.new_page(viewport={"width": 1080, "height": 1920})
        page.goto(f.resolve().as_uri(), wait_until="networkidle")
        page.evaluate("document.fonts.ready")
        for i, el in enumerate(page.query_selector_all("section.slide"), start=1):
            img = out_dir / f"scene{i:02d}.png"
            el.screenshot(path=str(img))
            files.append(img)
        b.close()
    f.unlink()
    return files


# ---------------- vídeo ----------------

def build(post: dict, out_dir: Path) -> tuple[Path, ReelScript]:
    out_dir.mkdir(parents=True, exist_ok=True)
    work = out_dir / "_work"
    work.mkdir(exist_ok=True)
    script, fix = None, ""
    for _ in range(3):
        cand = write_script(post, fix)
        v = brain.verify(cand)
        if v.aprovado:
            script = cand
            print("[reel] guião aprovado")
            break
        print(f"[reel] guião reprovado: {v.problemas}")
        fix = "\n".join(f"- {p}" for p in v.problemas)
    if script is None:
        raise RuntimeError("Guião do Reel reprovado 3 vezes — sem Reel nesta ronda.")
    imgs = _render_scenes(script, post["pilar"], work)
    segs = []
    for i, (c, img) in enumerate(zip(script.cenas, imgs), start=1):
        audio = work / f"a{i:02d}.mp3"
        _tts(c.fala, audio)
        d = _dur(audio) + 0.35
        seg = work / f"seg{i:02d}.mp4"
        frames = int(d * FPS)
        # zoom lento (1.00 → 1.06) para dar movimento
        vf = (f"scale=1188:2112,zoompan=z='min(1+0.06*on/{frames},1.06)':x='iw/2-(iw/zoom/2)':y='ih/2-(ih/zoom/2)'"
              f":d={frames}:s=1080x1920:fps={FPS},format=yuv420p")
        subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-loop", "1", "-i", str(img), "-i", str(audio),
                        "-vf", vf, "-af", "apad", "-t", f"{d:.2f}", "-c:v", "libx264", "-preset", "medium",
                        "-crf", "20", "-c:a", "aac", "-b:a", "160k", "-ar", "44100", "-shortest", str(seg)], check=True)
        segs.append(seg)
    lst = work / "list.txt"
    lst.write_text("".join(f"file '{s.name}'\n" for s in segs))
    out = out_dir / "reel.mp4"
    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-f", "concat", "-safe", "0", "-i", str(lst),
                    "-c:v", "libx264", "-preset", "medium", "-crf", "21", "-pix_fmt", "yuv420p",
                    "-c:a", "aac", "-b:a", "160k", "-movflags", "+faststart", str(out)], check=True)
    (out_dir / "reel.json").write_text(script.model_dump_json(indent=2))
    for f in work.iterdir():
        f.unlink()
    work.rmdir()
    print(f"[reel] {out} ({_dur(out):.1f}s, {out.stat().st_size / 1e6:.1f} MB)")
    return out, script
