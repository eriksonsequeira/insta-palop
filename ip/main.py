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
    foco = brain.choose_foco(st["posts"])
    print(f"[post] pilar={pilar} formato={formato} foco={foco}")
    post = None
    for attempt in range(2):
        cand = brain.write_post(pilar, formato, st["posts"], hint, foco)
        v = brain.verify(cand)
        if v.aprovado:
            print("[verificação] aprovado")
            post = cand
            break
        print(f"[verificação] reprovado: {v.problemas}")
        hint = (hint + "\n" if hint else "") + "Um verificador reprovou a versão anterior por: " + "; ".join(v.problemas)
    if post is None:
        raise SystemExit("Post reprovado duas vezes na verificação — nada publicado nesta ronda.")
    post_id = datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    DRAFTS.mkdir(exist_ok=True)
    (DRAFTS / f"{post_id}.json").write_text(json.dumps(post.model_dump(), ensure_ascii=False, indent=2))
    files = render(post, MEDIA / post_id)
    try:
        from .render import render_story
        render_story(post, MEDIA / post_id)
    except Exception as e:  # noqa: BLE001 — o Story nunca bloqueia o post
        print(f"[story] falhou a gerar: {e}")
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

    import time
    import requests

    d = json.loads((DRAFTS / f"{post_id}.json").read_text())
    urls = [f"{MEDIA_BASE_URL}/{post_id}/{f}" for f in d["images"]]
    for u in urls:  # esperar que o CDN sirva as imagens (o Instagram vai buscá-las por URL)
        for _ in range(30):
            if requests.head(u, timeout=20).status_code == 200:
                break
            time.sleep(10)
    link = instagram.publish_carousel(urls, caption(d), d.get("alt_text", ""))
    print(f"[ig] publicado: {link}")
    story_url = f"{MEDIA_BASE_URL}/{post_id}/story.jpg"
    if os.environ.get("STORIES", "1") == "1" and requests.head(story_url, timeout=20).status_code == 200:
        try:
            instagram.publish_story(story_url)
            print("[ig] story publicado")
        except Exception as e:  # noqa: BLE001
            print(f"[ig] story falhou: {e}")
    st = state.load()
    state.record(st, post_id, d, "publicado", link)
    state.save(st)
    _out("permalink", link)
    return link


def create_pill(hint: str = "") -> str:
    from .render import render_pill

    st = state.load()
    stories = st.setdefault("stories", [])
    tipo, pilar = brain.choose_pill(stories)
    print(f"[story] tipo={tipo} pilar={pilar}")
    history = stories + st["posts"]
    pill = None
    for _ in range(2):
        cand = brain.write_pill(tipo, pilar, history, hint)
        cand.tipo = tipo
        v = brain.verify(cand)
        if v.aprovado:
            print("[verificação] aprovado")
            pill = cand
            break
        print(f"[verificação] reprovado: {v.problemas}")
        hint = "Um verificador reprovou a versão anterior por: " + "; ".join(v.problemas)
    if pill is None:
        raise SystemExit("Story reprovado duas vezes — nada publicado nesta ronda.")
    sid = "s" + datetime.now(timezone.utc).strftime("%Y%m%d-%H%M")
    render_pill(pill, MEDIA / "stories" / sid)
    (MEDIA / "stories" / sid / "story.json").write_text(pill.model_dump_json(indent=2))
    stories.append({"id": sid, "created": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                    "tipo": tipo, "pilar": pilar, "tema": pill.tema, "status": "rascunho"})
    state.save(st)
    print(f"[story] {sid}: {pill.tema}")
    _out("story_id", sid)
    return sid


def publish_pill(sid: str) -> None:
    import time

    import requests

    from . import instagram

    url = f"{MEDIA_BASE_URL}/stories/{sid}/story.jpg"
    for _ in range(30):
        if requests.head(url, timeout=20).status_code == 200:
            break
        time.sleep(10)
    instagram.publish_story(url)
    st = state.load()
    for s_ in st.get("stories", []):
        if s_["id"] == sid:
            s_["status"] = "publicado"
    state.save(st)
    print(f"[ig] story publicado: {sid}")


def create_reel(post_id: str | None = None) -> str:
    """Gera o Reel do último post publicado que ainda não tem Reel."""
    from . import reel

    st = state.load()
    if not post_id:
        cands = [p for p in st["posts"] if p["status"] == "publicado" and not p.get("reel")]
        if not cands:
            raise SystemExit("Nenhum post publicado sem Reel.")
        post_id = cands[-1]["id"]
    d = json.loads((DRAFTS / f"{post_id}.json").read_text())
    reel.build(d, MEDIA / post_id)
    for p in st["posts"]:
        if p["id"] == post_id:
            p["reel"] = "gerado"
    state.save(st)
    _out("post_id", post_id)
    return post_id


def publish_reel(post_id: str) -> str:
    import time

    import requests

    from . import instagram

    script = json.loads((MEDIA / post_id / "reel.json").read_text())
    url = f"{MEDIA_BASE_URL}/{post_id}/reel.mp4"
    for _ in range(30):
        if requests.head(url, timeout=20).status_code == 200:
            break
        time.sleep(10)
    tags = " ".join(f"#{h.lstrip('#').lower()}" for h in script["hashtags"][:5])
    cred_f = MEDIA / post_id / "credits.txt"
    cred = cred_f.read_text().strip() if cred_f.exists() else ""
    cred = f"\n\nImagens: {'; '.join(cred.splitlines())}" if cred else ""
    link = instagram.publish_reel(url, f"{script['legenda'].strip()}{cred}\n\n{tags}"[:2200])
    st = state.load()
    for p in st["posts"]:
        if p["id"] == post_id:
            p["reel"] = link
    state.save(st)
    print(f"[ig] reel publicado: {link}")
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
    elif cmd == "stats":
        from . import stats
        stats.collect()
    elif cmd == "reel":
        create_reel(argv[1] if len(argv) > 1 and argv[1] else None)
    elif cmd == "publish-reel":
        publish_reel(argv[1])
    elif cmd == "pill":
        create_pill(os.environ.get("HINT", ""))
    elif cmd == "publish-pill":
        publish_pill(argv[1])
    elif cmd == "story":
        from . import instagram
        instagram.publish_story(f"{MEDIA_BASE_URL}/{argv[1]}/story.jpg")
        print("[ig] story publicado")
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
