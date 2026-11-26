"""Configuração central — tudo vem de variáveis de ambiente (GitHub Secrets/Variables)."""
import os
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
MEDIA = ROOT / "media"          # imagens publicadas (servidas por URL pública para a API do Instagram)
DRAFTS = ROOT / "drafts"        # posts gerados à espera de aprovação
TEMPLATES = ROOT / "templates"
STATE_FILE = ROOT / "state.json"


def env(name: str, default: str | None = None) -> str | None:
    v = os.environ.get(name)
    return v if v not in (None, "") else default


IG_HANDLE = env("IG_HANDLE", "@erikson_sequeira")
BRAND_NAME = env("BRAND_NAME", "")

# --- Claude ---
CLAUDE_MODEL = env("CLAUDE_MODEL", "claude-opus-5-5")

# --- Instagram (Instagram API com login do Instagram; não precisa de Página do Facebook) ---
IG_ACCESS_TOKEN = env("IG_ACCESS_TOKEN")
IG_GRAPH_HOST = env("IG_GRAPH_HOST", "https://graph.instagram.com")  # ou https://graph.facebook.com
IG_API_VERSION = env("IG_API_VERSION", "v23.0")

# 1 = publica logo; 0 = abre uma Issue no GitHub para aprovares (comenta "ok" para publicar)
AUTO_PUBLISH = env("AUTO_PUBLISH", "0") == "1"

# URL pública base onde ficam as imagens (por omissão: raw do próprio repositório público)
GITHUB_REPOSITORY = env("GITHUB_REPOSITORY", "")
MEDIA_BASE_URL = env(
    "MEDIA_BASE_URL",
    f"https://raw.githubusercontent.com/{GITHUB_REPOSITORY}/main/media" if GITHUB_REPOSITORY else "",
)
