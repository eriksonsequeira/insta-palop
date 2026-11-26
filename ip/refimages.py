"""Imagens de referência para os Reels: candidatas livres (Wikimedia Commons; Pixabay se houver chave)
e o Claude OLHA para elas e escolhe a que mostra mesmo aquilo de que a cena fala (ou nenhuma)."""
import io
import os
import re
from pathlib import Path

import requests
from PIL import Image
from pydantic import BaseModel

from . import brain

UA = {"User-Agent": "reel-builder/1.0 (automated; educational social media posts)"}
COMMONS = "https://commons.wikimedia.org/w/api.php"
OK_LICENSES = ("cc0", "public domain", "pd", "cc by", "cc-by", "cc by-sa", "cc-by-sa")


def _strip_html(s: str) -> str:
    return re.sub(r"<[^>]+>", "", s or "").strip()


def commons(query: str, limit: int = 4) -> list[dict]:
    params = {"action": "query", "format": "json", "generator": "search", "gsrnamespace": 6, "gsrlimit": 12,
              "gsrsearch": f"{query} filetype:bitmap", "prop": "imageinfo",
              "iiprop": "url|size|mime|extmetadata", "iiurlwidth": 1080}
    try:
        pages = requests.get(COMMONS, params=params, headers=UA, timeout=30).json().get("query", {}).get("pages", {})
    except Exception as e:  # noqa: BLE001
        print(f"[img] Commons falhou para '{query}': {e}")
        return []
    out = []
    for p in sorted(pages.values(), key=lambda p: p.get("index", 99)):
        ii = (p.get("imageinfo") or [{}])[0]
        meta = ii.get("extmetadata", {})
        lic = _strip_html(meta.get("LicenseShortName", {}).get("value", "")).lower()
        if ii.get("mime") not in ("image/jpeg", "image/png") or ii.get("width", 0) < 700:
            continue
        if not any(k in lic for k in OK_LICENSES):
            continue
        out.append({"url": ii.get("thumburl") or ii["url"], "fonte": "Wikimedia Commons",
                    "autor": _strip_html(meta.get("Artist", {}).get("value", ""))[:60] or "desconhecido",
                    "licenca": lic, "titulo": p.get("title", "")})
        if len(out) >= limit:
            break
    return out


def pixabay(query: str, limit: int = 3) -> list[dict]:
    key = os.environ.get("PIXABAY_API_KEY")
    if not key:
        return []
    try:
        hits = requests.get("https://pixabay.com/api/", params={"key": key, "q": query, "image_type": "photo",
                            "orientation": "all", "safesearch": "true", "per_page": 10}, timeout=30).json().get("hits", [])
    except Exception:  # noqa: BLE001
        return []
    return [{"url": h["largeImageURL"], "fonte": "Pixabay", "autor": h.get("user", ""), "licenca": "pixabay",
             "titulo": h.get("tags", "")} for h in hits[:limit]]


class Escolha(BaseModel):
    cena: int
    ficheiro: str | None


class Escolhas(BaseModel):
    escolhas: list[Escolha]


def pick(cenas: list, work: Path) -> dict[int, dict]:
    """Descarrega candidatas por cena e pede ao Claude (que vê as imagens) para escolher. Devolve {cena: info}."""
    d = work / "cand"
    d.mkdir(parents=True, exist_ok=True)
    cands: dict[str, dict] = {}
    lines = []
    for ci, c in enumerate(cenas):
        q = (c.imagem_busca or "").strip()
        if not q:
            continue
        files = []
        for k, cand in enumerate(commons(q) + pixabay(q)):
            try:
                raw = requests.get(cand["url"], headers=UA, timeout=60).content
                im = Image.open(io.BytesIO(raw)).convert("RGB")
                im.thumbnail((1400, 1400))
                f = d / f"c{ci}_{k}.jpg"
                im.save(f, quality=88)
                cands[f.name] = cand | {"path": f}
                files.append(f.name)
            except Exception:  # noqa: BLE001
                continue
        if files:
            lines.append(f"Cena {ci}: \"{c.fala}\" (procurei: {q}) → candidatas: {', '.join(files)}")
    if not lines:
        return {}
    prompt = (
        "És editor de vídeo. Para cada cena de um Reel, vê as imagens candidatas (usa a ferramenta Read para abrir "
        f"cada ficheiro na pasta atual) e escolhe a que MOSTRA MESMO aquilo de que a cena fala, com boa qualidade.\n"
        "Regras: rejeita imagens irrelevantes, de má qualidade, com texto ilegível dominante, mapas/diagramas confusos, "
        "pessoas em situação embaraçosa, conteúdo violento ou sexual, ou que possam induzir em erro sobre o assunto. "
        "Na dúvida, escolhe null (é melhor não ter imagem do que ter uma errada).\n\n" + "\n".join(lines)
        + "\n\nResponde com uma escolha por cena listada (ficheiro = nome exato, ou null)."
    )
    try:
        res = brain._parse_cli(prompt, Escolhas, tools="Read", cwd=str(d), system=False)
    except Exception as e:  # noqa: BLE001
        print(f"[img] escolha falhou ({e}); Reel sem imagens")
        return {}
    out = {}
    for e in res.escolhas:
        if e.ficheiro and e.ficheiro in cands:
            out[e.cena] = cands[e.ficheiro]
    print(f"[img] {len(out)}/{len(cenas)} cenas com imagem de referência")
    return out
