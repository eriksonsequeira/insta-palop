"""CLI:
  python -m ip.main create [--hint "..."]   gera um post (texto + imagens) e grava em drafts/ e media/
  python -m ip.main publish <id>            publica o post <id> no Instagram
  python -m ip.main refresh-token           imprime um token renovado
  python -m ip.main whoami                  verifica o token
"""
import json
import os
import sys
from datetime import datetime, timezone

from . import brain, state
from .config import DRAFTS, MEDIA, MEDIA_BASE_URL


def _out(key: str, value: str) -> None:
    """Passa valores para os passos seguintes do GitHub Actions."""
    if gh := os.environ.get("GITHUB_OUTPUT"):
        with open(gh, "a") as f:
            f.write(f"{key}={value}\n")


def caption(post: dict) -> str:
    tags = " ".join(f"#{h}" for h in post["hashtags"])
    return f"{post['legenda'].strip()}\n\n{tags}"[:2200]


def create(hint: str = "") -> str:
    from .render import render

    st = state.load()
    pilar, formato = brain.choose_angle(st["posts"])
    print(f"[post] pilar={pilar} formato={formato}")
    post = brain.write_post(pilar, formato, st["posts"], hint)
    post_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    DRAFTS.mkdir(exist_ok=True)
    (DRAFTS / f"{post_id}.json").write_text(json.dumps(post.model_dump(), ensure_ascii=False, indent=2))
    files = render(post, MEDIA / post_id)
    data = post.model_dump() | {"id": post_id, "images": [f.name for f in files]}
    (DRAFTS / f"{post_id}.json").write_text(json.dumps(data, ensure_ascii=False, indent=2))
    (DRAFTS / f"{post_id}.md").write_text(review_md(data))
    state.record(st, post_id, data, "rascunho")
    state.save(st)
    print(f"[post] {post_id}: {post.tema}")
    _out("post_id", post_id)
    return post_id


def review_md(d: dict) -> str:
    imgs = "\n".join(f'<img src="{MEDIA_BASE_URL}/{d["id"]}/{f}" width="270">' for f in d["images"])
    fontes = "\n".join(f"- {u}" for u in d["fontes"])
    return (
        f"**{d['tema']}** · pilar `{d['pilar']}` · formato `{d['formato']}`\n\n{imgs}\n\n"
        f"### Legenda\n\n```\n{caption(d)}\n```\n\n### Fontes verificadas\n{fontes}\n\n---\n"
        "Comenta **ok** para publicar · **não** para descartar."
    )


def publish(post_id: str) -> str:
    from . import instagram

    d = json.loads((DRAFTS / f"{post_id}.json").read_text())
    urls = [f"{MEDIA_BASE_URL}/{post_id}/{f}" for f in d["images"]]
    link = instagram.publish_carousel(urls, caption(d), d.get("alt_text", ""))
    st = state.load()
    state.record(st, post_id, d, "publicado", link)
    state.save(st)
    print(f"[ig] publicado: {link}")
    _out("permalink", link)
    return link


def discard(post_id: str) -> None:
    st = state.load()
    d = json.loads((DRAFTS / f"{post_id}.json").read_text())
    state.record(st, post_id, d, "descartado")
    state.save(st)


def main(argv: list[str]) -> None:
    cmd = argv[0] if argv else "create"
    if cmd == "create":
        hint = argv[argv.index("--hint") + 1] if "--hint" in argv else os.environ.get("HINT", "")
        create(hint)
    elif cmd == "publish":
        publish(argv[1])
    elif cmd == "discard":
        discard(argv[1])
    elif cmd == "refresh-token":
        from . import instagram
        print(instagram.refresh_token())
    elif cmd == "whoami":
        from . import instagram
        print(instagram.me())
    else:
        sys.exit(__doc__)


if __name__ == "__main__":
    main(sys.argv[1:])
