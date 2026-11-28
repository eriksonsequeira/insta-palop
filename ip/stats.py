"""Estatísticas: recolhe métricas de cada publicação e da conta, guarda em stats.json e gera aprendizagens semanais."""
import json
from datetime import datetime, timezone

from . import instagram
from .config import IG_USER_ID, ROOT

STATS = ROOT / "stats.json"
LEARN = ROOT / "aprendizagens.md"
METRICS = {
    "REELS": ["reach", "views", "saved", "shares", "total_interactions", "ig_reels_avg_watch_time"],
    "FEED": ["reach", "views", "saved", "shares", "total_interactions", "follows", "profile_visits"],
    "STORY": ["reach", "views", "replies", "navigation", "follows", "profile_visits"],
}


def _insights(media_id: str, kind: str) -> dict:
    out = {}
    for m in METRICS.get(kind, METRICS["FEED"]):
        try:  # pedir uma a uma: se uma métrica não existir para este tipo, as outras continuam
            d = instagram._req("GET", f"{media_id}/insights", metric=m)
            vals = d.get("data", [{}])[0].get("values", [{}])
            out[m] = vals[0].get("value") if vals else d.get("data", [{}])[0].get("total_value", {}).get("value")
        except Exception as e:  # noqa: BLE001
            out.setdefault("_erros", []).append(f"{m}: {str(e)[:80]}")
    return out


def collect() -> dict:
    data = json.loads(STATS.read_text()) if STATS.exists() else {"media": {}, "conta": []}
    me = instagram._req("GET", IG_USER_ID, fields="followers_count,media_count")
    data["conta"].append({"data": datetime.now(timezone.utc).isoformat(timespec="minutes"),
                          "seguidores": me.get("followers_count"), "publicacoes": me.get("media_count")})
    try:  # onde estão os seguidores (países e cidades) — orienta a escolha dos temas
        pub = {}
        for bd, key in (("country", "paises"), ("city", "cidades"), ("age", "idades")):
            d = instagram._req("GET", f"{IG_USER_ID}/insights", metric="follower_demographics", period="lifetime",
                               metric_type="total_value", breakdown=bd)
            res = d["data"][0]["total_value"]["breakdowns"][0]["results"]
            pub[key] = dict(sorted(((r["dimension_values"][0], r["value"]) for r in res), key=lambda kv: -kv[1])[:15])
        pub["atualizado"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
        data["publico"] = pub
        print(f"[stats] público: {list(pub['paises'].items())[:5]}")
    except Exception as e:  # noqa: BLE001
        print(f"[stats] público indisponível: {str(e)[:120]}")
    media = instagram._req("GET", f"{IG_USER_ID}/media", limit=40,
                           fields="id,permalink,timestamp,media_type,media_product_type,caption,like_count,comments_count")
    items = media.get("data", [])
    try:
        stories = instagram._req("GET", f"{IG_USER_ID}/stories", fields="id,timestamp,media_type,media_product_type")
        items += stories.get("data", [])
    except Exception:  # noqa: BLE001
        pass
    for it in items:
        kind = it.get("media_product_type", "FEED")
        rec = data["media"].setdefault(it["id"], {})
        rec.update({k: it.get(k) for k in ("permalink", "timestamp", "media_type", "like_count", "comments_count")})
        rec["tipo"] = kind
        rec["legenda_inicio"] = (it.get("caption") or "")[:120]
        rec["metricas"] = _insights(it["id"], kind)
        rec["atualizado"] = datetime.now(timezone.utc).isoformat(timespec="minutes")
    STATS.write_text(json.dumps(data, ensure_ascii=False, indent=1))
    ok = sum(1 for r in data["media"].values() if r.get("metricas") and "reach" in r["metricas"])
    print(f"[stats] {len(items)} publicações; {ok} com métricas de alcance; seguidores: {me.get('followers_count')}")
    errs = {e for r in data["media"].values() for e in r.get("metricas", {}).get("_erros", [])}
    if errs:
        print("[stats] métricas indisponíveis (exemplos):", list(errs)[:4])
    return data
