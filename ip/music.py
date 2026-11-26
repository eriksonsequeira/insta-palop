"""Gera (uma vez) a biblioteca de faixas instrumentais dos Reels com o Suno (sunoapi.org) → assets/music/*.mp3."""
import os
import subprocess
import time
from pathlib import Path

import requests

from .config import ROOT

BASE = os.environ.get("SUNO_API_BASE", "https://api.sunoapi.org")
MODEL = os.environ.get("SUNO_MODEL", "V6")
OUT = ROOT / "assets" / "music"

# camas discretas, sem picos, para ficar por baixo da voz (método: trilha constante, sem drops nem risers)
STYLES = [
    ("Pulso", "minimal tech background bed, soft plucked synth arpeggio, warm sub pad, 105 bpm, curious and modern, "
              "consistent texture, no drops, no risers, no vocals"),
    ("Editorial", "light editorial explainer bed, felt piano and pizzicato strings, repeating curious motif, 100 bpm, "
                  "airy, no drums, no bass drops, no vocals"),
    ("Afro Tech", "subtle afrobeat-inspired background groove, soft shakers, muted guitar plucks, warm keys, 102 bpm, "
                  "understated, no vocals, no build-ups"),
    ("Lo-fi Founder", "lo-fi hip hop background, dusty keys, soft vinyl texture, gentle laid-back beat, 88 bpm, focused, "
                      "no vocals, steady"),
    ("Futuro", "cinematic minimal electronic bed, glassy plucks, slow evolving pad, light ticking percussion, 110 bpm, "
               "optimistic tech, no drops, no vocals"),
]


def _h() -> dict:
    return {"Authorization": f"Bearer {os.environ['SUNO_API_KEY']}", "Content-Type": "application/json"}


def generate_all() -> None:
    OUT.mkdir(parents=True, exist_ok=True)
    for title, style in STYLES:
        slug = title.lower().replace(" ", "-")
        if list(OUT.glob(f"{slug}-*.mp3")):
            print(f"[música] {title}: já existe")
            continue
        body = {"customMode": True, "instrumental": True, "model": MODEL, "title": title, "style": style,
                "negativeTags": "vocals, singing, lyrics, heavy drops, loud risers, distortion",
                "callBackUrl": "https://example.com/suno-callback"}
        j = requests.post(f"{BASE}/api/v1/generate", json=body, headers=_h(), timeout=60).json()
        if j.get("code") != 200:
            raise RuntimeError(f"Suno recusou: {j}")
        task = j["data"]["taskId"]
        print(f"[música] {title}: tarefa {task}")
        for _ in range(60):
            time.sleep(20)
            d = requests.get(f"{BASE}/api/v1/generate/record-info", params={"taskId": task}, headers=_h(),
                             timeout=60).json().get("data") or {}
            st = d.get("status")
            if st == "SUCCESS":
                items = (d.get("response") or {}).get("sunoData") or []
                for k, it in enumerate(items, start=1):
                    url = it.get("audioUrl") or it.get("audio_url") or it.get("sourceAudioUrl")
                    if not url:
                        continue
                    raw = OUT / f"_{slug}-{k}.mp3"
                    raw.write_bytes(requests.get(url, timeout=300).content)
                    dst = OUT / f"{slug}-{k}.mp3"
                    # 75 s chegam para um Reel; normaliza e corta para ficar leve
                    subprocess.run(["ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-t", "75",
                                    "-af", "loudnorm=I=-20,afade=t=out:st=72:d=3", "-b:a", "160k", str(dst)], check=True)
                    raw.unlink()
                    print(f"[música] guardada {dst.name}")
                break
            if st and ("FAIL" in st or "ERROR" in st):
                raise RuntimeError(f"Suno falhou: {st} {d.get('errorMessage')}")
        else:
            raise TimeoutError(f"Suno não terminou: {title}")


if __name__ == "__main__":
    generate_all()
