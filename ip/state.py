"""Histórico de posts (para não repetir temas e alternar pilares/formatos)."""
import json
from datetime import datetime, timezone

from .config import STATE_FILE


def load() -> dict:
    if STATE_FILE.exists():
        return json.loads(STATE_FILE.read_text())
    return {"posts": []}


def save(state: dict) -> None:
    STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2) + "\n")


def record(state: dict, post_id: str, post: dict, status: str, permalink: str | None = None) -> None:
    for p in state["posts"]:
        if p["id"] == post_id:
            p.update(status=status, permalink=permalink or p.get("permalink"))
            return
    state["posts"].append({
        "id": post_id,
        "created": datetime.now(timezone.utc).isoformat(timespec="minutes"),
        "pilar": post["pilar"],
        "formato": post["formato"],
        "tema": post["tema"],
        "status": status,
        "permalink": permalink,
    })


def recent(state: dict, n: int = 40) -> list[dict]:
    return state["posts"][-n:]
