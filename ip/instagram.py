"""Publicação via API oficial do Instagram (Content Publishing)."""
import time

import requests

from .config import IG_ACCESS_TOKEN, IG_API_VERSION, IG_GRAPH_HOST, IG_USER_ID

BASE = f"{IG_GRAPH_HOST}/{IG_API_VERSION}"


def _req(method: str, path: str, **params) -> dict:
    if not IG_ACCESS_TOKEN:
        raise RuntimeError("Falta IG_ACCESS_TOKEN")
    params["access_token"] = IG_ACCESS_TOKEN
    r = requests.request(method, f"{BASE}/{path}", params=params if method == "GET" else None,
                         data=params if method != "GET" else None, timeout=60)
    data = r.json() if r.content else {}
    if r.status_code >= 400 or "error" in data:
        raise RuntimeError(f"Instagram API {path}: {data.get('error', r.text)}")
    return data


def me() -> dict:
    d = _req("GET", IG_USER_ID, fields="id,username,media_count,followers_count")
    return d | {"user_id": d["id"]}


def _wait(container_id: str, timeout: int = 300) -> None:
    t0 = time.time()
    while time.time() - t0 < timeout:
        st = _req("GET", container_id, fields="status_code,status").get("status_code")
        if st == "FINISHED":
            return
        if st in ("ERROR", "EXPIRED"):
            raise RuntimeError(f"Contentor {container_id} falhou: {st}")
        time.sleep(5)
    raise TimeoutError(f"Contentor {container_id} não ficou pronto")


def publish_carousel(image_urls: list[str], caption: str, alt_text: str = "") -> str:
    """Publica um carrossel e devolve o permalink."""
    uid = me()["user_id"]
    children = []
    for url in image_urls:
        params = {"image_url": url, "is_carousel_item": "true"}
        if alt_text:
            params["alt_text"] = alt_text
        children.append(_req("POST", f"{uid}/media", **params)["id"])
    for c in children:
        _wait(c)
    parent = _req("POST", f"{uid}/media", media_type="CAROUSEL", children=",".join(children), caption=caption)["id"]
    _wait(parent)
    media_id = _req("POST", f"{uid}/media_publish", creation_id=parent)["id"]
    return _req("GET", media_id, fields="permalink").get("permalink", "")


def publish_story(image_url: str) -> str:
    """Publica um Story de imagem e devolve o id."""
    uid = me()["user_id"]
    c = _req("POST", f"{uid}/media", image_url=image_url, media_type="STORIES")["id"]
    _wait(c)
    return _req("POST", f"{uid}/media_publish", creation_id=c)["id"]


def publish_reel(video_url: str, caption: str) -> str:
    """Publica um Reel (também aparece no feed) e devolve o permalink."""
    uid = me()["user_id"]
    c = _req("POST", f"{uid}/media", media_type="REELS", video_url=video_url, caption=caption,
             share_to_feed="true")["id"]
    _wait(c, timeout=900)
    media_id = _req("POST", f"{uid}/media_publish", creation_id=c)["id"]
    return _req("GET", media_id, fields="permalink").get("permalink", "")


def recent_captions(limit: int = 30) -> list[str]:
    uid = me()["user_id"]
    data = _req("GET", f"{uid}/media", fields="caption,media_type,timestamp,like_count,comments_count", limit=limit)
    return [m for m in data.get("data", [])]


def refresh_token() -> str:
    """Renova o token de longa duração (válido 60 dias). Devolve o novo token."""
    r = requests.get(f"{IG_GRAPH_HOST}/refresh_access_token",
                     params={"grant_type": "ig_refresh_token", "access_token": IG_ACCESS_TOKEN}, timeout=60)
    data = r.json()
    if "access_token" not in data:
        raise RuntimeError(f"Falha ao renovar token: {data}")
    return data["access_token"]
