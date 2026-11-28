"""Reels "a página que se escreve sozinha":
guião (Claude, verificado) → voz (Gemini TTS; edge-tts só como recurso) → ritmo (pausas naturais, ~150 ppm, nunca acelerado)
→ tempos de cada palavra (Whisper) → cenas de ~2 s → Remotion (tipografia cinética, números a contar, SFX, música).
"""
import base64
import difflib
import json
import os
import random
import re
import shutil
import subprocess
import time
import unicodedata
from pathlib import Path

import requests
from pydantic import BaseModel, Field

from . import brain
from .config import IG_HANDLE, ROOT
from .render import ACCENTS, LABELS

STUDIO = ROOT / "reel-studio"
MUSIC_DIR = ROOT / "assets" / "music"
GEMINI_MODELS = [m for m in (os.environ.get("GEMINI_TTS_MODEL"), "gemini-3.8-flash-tts",
                             "gemini-3.1-flash-tts-preview", "gemini-2.5-flash-preview-tts") if m]
GEMINI_VOICE = os.environ.get("GEMINI_TTS_VOICE", "Puck")
# instrução CURTA: textos de estilo longos às vezes são lidos em voz alta (a proteção _fix_lead corta-os se acontecer)
GEMINI_STYLE = ("Diz em português de Lisboa, tom confiante e próximo, ritmo calmo e claro, com pausa entre frases:\n\n")
OUTRO = 3.2  # segundos do cartão final (conta + convite para seguir, para dar tempo de ler)
TARGET_WPM = 150  # ritmo confortável para PT-PT; a voz nunca é acelerada, só abrandada se preciso


class Cena(BaseModel):
    fala: str = Field(description="1–2 frases curtas, máx. 20 palavras, PT-PT falado; números em algarismos (ex.: 3,79 mil milhões)")
    palavra_chave: str = Field(description="UMA palavra que aparece literalmente na fala e é a mais importante da cena")
    destaque: str | None = Field(default=None, description="número curto (máx. 12 caracteres) que aparece ESCRITO "
                                 "IGUAL na fala desta cena (ex.: fala '75,8 mil milhões' → '75,8 mil M$'); null se não houver")
    imagem_busca: str = Field(default="", description="2–4 palavras EM INGLÊS para procurar uma FOTO REAL do que a cena "
                              "mostra no Wikimedia Commons (ex.: 'Take-Two Interactive headquarters', 'video game "
                              "controller', 'Luanda skyline'); vazio se não houver nada concreto para mostrar")


class Pronuncia(BaseModel):
    escrito: str = Field(description="como aparece na fala (ex.: 'GTA VI', 'IA', 'CEO', 'M$')")
    dito: str = Field(description="como deve ser lido em voz alta em PT-PT (ex.: 'GTA seis', 'i-á', 'cê-é-ó')")


class ReelScript(BaseModel):
    cenas: list[Cena] = Field(description="6 a 8 cenas, total 80–105 palavras (35–45 s)")
    pronuncias: list[Pronuncia] = Field(default_factory=list, description="siglas, numerais romanos, marcas e "
                                        "símbolos que um leitor automático leria mal")
    convite_falado: str = Field(default="", description="convite ÚNICO para seguir a página, dito no fim do Reel "
                                "depois da pergunta: máx. 16 palavras, ligado ao tema, sem '@' (diz 'segue a página')")
    convite_seguir: str = Field(default="", description="versão ESCRITA do convite para a legenda, com o @ da página, "
                                "máx. 120 caracteres")
    legenda: str = Field(description="legenda do Reel, 300–900 caracteres, termina com pergunta; sem hashtags")
    hashtags: list[str]


RULES = """Transforma este post de Instagram (já verificado) num guião de REEL narrado, vertical, de 35 a 45 segundos.
Estrutura (método de reels de alta retenção):
- Cena 1 (0–3 s): o assunto na PRIMEIRA palavra e um gancho contraintuitivo ou o dado mais chocante. Nada de "Olá".
- Depois: prova/autoridade → virada → mecanismo em blocos curtos → "sobe a aposta" → veredito.
- Uma palavra de virada a cada 8–12 s ("Só que", "Mas", "Agora,", "E o melhor:").
- Última cena: termina numa PERGUNTA para os comentários. Depois dela vem o convite_falado (não o ponhas nas cenas).
- Frases curtas e fechadas. Linguagem falada de Portugal (tu). Números em algarismos como se escrevem normalmente.
- Escreve para ser OUVIDO: uma ideia por frase, sem parênteses nem listas, no máximo 2 números por cena.
- O gancho da cena 1 tem de dizer em voz alta o mesmo número que aparece no ecrã (nada de "21%" escrito e "1 em cada 5" dito).
- Usa SÓ os factos do post (não acrescentes factos novos).
- pronuncias: lista TODAS as siglas, numerais romanos (VI → seis), símbolos e nomes estrangeiros da fala, com a leitura
  correta em português de Portugal (ex.: "GTA VI" → "GTA seis", "IA" → "i-á", "CEO" → "cê-é-ó", "Take-Two" → "teik-tu").
- imagem_busca: pensa no que o espectador deve VER em cada cena (pessoa, lugar, objeto, empresa, produto real).
- hashtags: exatamente 5, sem '#', minúsculas."""


def write_script(post: dict, fix: str = "") -> ReelScript:
    from . import convite, state
    data = {k: post[k] for k in ("pilar", "tema", "capa_titulo", "capa_subtitulo", "slides", "cta_titulo", "fontes")}
    prompt = (f"{RULES}\n\n{convite.RULES}\nO convite_falado é dito em voz alta: frase falada, natural, sem '@'.\n"
              f"{convite.avoid_block(state.load())}\nPOST:\n{json.dumps(data, ensure_ascii=False, indent=1)}")
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


def approved_script(post: dict) -> ReelScript:
    fix = ""
    for _ in range(3):
        cand = write_script(post, fix)
        v = brain.verify(cand)
        if v.aprovado:
            print("[reel] guião aprovado")
            return cand
        print(f"[reel] guião reprovado: {v.problemas}")
        fix = "\n".join(f"- {p}" for p in v.problemas)
    raise RuntimeError("Guião do Reel reprovado 3 vezes — sem Reel nesta ronda.")


# ---------------- voz ----------------

def _run(*cmd: str) -> None:
    subprocess.run(list(cmd), check=True)


def _dur(f: Path) -> float:
    r = subprocess.run(["ffprobe", "-v", "error", "-show_entries", "format=duration", "-of", "csv=p=0", str(f)],
                       capture_output=True, text=True, check=True)
    return float(r.stdout.strip())


def _gemini_tts(text: str, out_wav: Path) -> None:
    key = os.environ["GEMINI_API_KEY"]
    body = {"contents": [{"parts": [{"text": GEMINI_STYLE + text}]}],
            "generationConfig": {"responseModalities": ["AUDIO"], "speechConfig": {
                "voiceConfig": {"prebuiltVoiceConfig": {"voiceName": GEMINI_VOICE}}}}}
    last = ""
    for model in dict.fromkeys(GEMINI_MODELS):
        for attempt in range(3):
            r = requests.post(f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent",
                              headers={"x-goog-api-key": key}, json=body, timeout=600)
            if r.status_code == 200:
                try:
                    part = r.json()["candidates"][0]["content"]["parts"][0]["inlineData"]
                except (KeyError, IndexError):
                    last = r.text[:300]
                    continue
                pcm = out_wav.with_suffix(".pcm")
                pcm.write_bytes(base64.b64decode(part["data"]))
                rate = re.search(r"rate=(\d+)", part.get("mimeType", ""))
                _run("ffmpeg", "-y", "-loglevel", "error", "-f", "s16le", "-ar", rate.group(1) if rate else "24000",
                     "-ac", "1", "-i", str(pcm), str(out_wav))
                pcm.unlink()
                print(f"[reel] voz Gemini ({model}, {GEMINI_VOICE})")
                return
            last = f"{r.status_code} {r.text[:200]}"
            if r.status_code in (429, 500, 503):
                time.sleep(15 * (attempt + 1))
            else:
                break
    raise RuntimeError(f"Gemini TTS falhou: {last}")


def _edge_tts(text: str, out_wav: Path) -> None:
    import asyncio

    import edge_tts
    mp3 = out_wav.with_suffix(".mp3")
    asyncio.run(edge_tts.Communicate(text, "pt-PT-DuarteNeural", rate="+0%").save(str(mp3)))
    _run("ffmpeg", "-y", "-loglevel", "error", "-i", str(mp3), str(out_wav))
    mp3.unlink()
    print("[reel] voz edge-tts (recurso)")


def spoken_tokens(tokens: list[str], prons: list) -> tuple[list[str], list[int]]:
    """Troca siglas/números pela leitura correta. Devolve (tokens ditos, índice do token escrito de cada um)."""
    rules = sorted(((_norm_seq(p.escrito), p.dito.split()) for p in prons if p.escrito.strip() and p.dito.strip()),
                   key=lambda r: -len(r[0]))
    norm = [_norm(t) for t in tokens]
    out, idx, i = [], [], 0
    while i < len(tokens):
        for src, dst in rules:
            n = len(src)
            if n and norm[i:i + n] == src:
                tail = re.search(r"[.,!?;:]+$", tokens[i + n - 1])
                for k, w in enumerate(dst):
                    out.append(w + (tail.group(0) if tail and k == len(dst) - 1 else ""))
                    idx.append(i + min(k * n // max(1, len(dst)), n - 1))
                i += n
                break
        else:
            out.append(tokens[i])
            idx.append(i)
            i += 1
    return out, idx


def _norm_seq(s: str) -> list[str]:
    return [_norm(t) for t in s.split() if _norm(t)]


def narrate(text: str, work: Path) -> Path:
    raw = work / "raw.wav"
    if os.environ.get("GEMINI_API_KEY"):
        _gemini_tts(text, raw)
    elif os.environ.get("ALLOW_EDGE_TTS") == "1":
        _edge_tts(text, raw)
    else:
        raise RuntimeError("Falta GEMINI_API_KEY para a voz do Reel")
    # pausas naturais (máx. ~0,55 s) e ritmo alvo sem mudar o tom (só abranda, nunca acelera)
    tight = work / "tight.wav"
    _run("ffmpeg", "-y", "-loglevel", "error", "-i", str(raw), "-af",
         "silenceremove=start_periods=1:start_threshold=-45dB:stop_periods=-1:stop_duration=0.55:stop_threshold=-45dB",
         "-ar", "44100", "-ac", "1", str(tight))
    words = len(text.split())
    wpm = words / (_dur(tight) / 60)
    tempo = max(0.87, min(1.0, TARGET_WPM / wpm))  # abaixo de 0,87 a voz fica arrastada
    out = work / "narration.wav"
    _run("ffmpeg", "-y", "-loglevel", "error", "-i", str(tight), "-af",
         f"atempo={tempo:.3f},loudnorm=I=-16:TP=-1.5:LRA=11", "-ar", "44100", "-ac", "2", str(out))
    print(f"[reel] ritmo {wpm:.0f} → {wpm * tempo:.0f} palavras/min")
    return out


# ---------------- tempos de cada palavra ----------------

def _norm(w: str) -> str:
    w = unicodedata.normalize("NFKD", w.lower())
    w = "".join(c for c in w if not unicodedata.combining(c))
    return re.sub(r"[^\w]", "", w)


def align(audio: Path, tokens: list[str]) -> list[tuple[float, float]]:
    """Tempos (início, fim) para cada token do guião, a partir da transcrição com tempos do Whisper."""
    from faster_whisper import WhisperModel

    import numpy as np

    pcm = subprocess.run(["ffmpeg", "-loglevel", "error", "-i", str(audio), "-f", "s16le", "-ac", "1", "-ar", "16000", "-"],
                         capture_output=True, check=True).stdout
    samples = np.frombuffer(pcm, np.int16).astype(np.float32) / 32768.0
    model = WhisperModel(os.environ.get("WHISPER_MODEL", "medium"), device="cpu", compute_type="int8")
    # sem initial_prompt: com o guião como pista o Whisper "adivinha" o texto e os tempos ficam desfasados
    segs, _ = model.transcribe(samples, language="pt", word_timestamps=True, vad_filter=False,
                               condition_on_previous_text=False)
    hw = [(w.word.strip(), w.start, w.end) for s in segs for w in (s.words or [])]
    a = [_norm(t) for t in tokens]
    b = [_norm(w[0]) for w in hw]
    times: list = [None] * len(tokens)
    for blk in difflib.SequenceMatcher(None, a, b, autojunk=False).get_matching_blocks():
        for k in range(blk.size):
            times[blk.a + k] = (hw[blk.b + k][1], hw[blk.b + k][2])
    total = _dur(audio)
    known = [i for i, t in enumerate(times) if t]
    print(f"[reel] alinhamento: {len(known)}/{len(tokens)} palavras com tempo do Whisper")
    if not known:
        step = total / max(1, len(tokens))
        return [(i * step, (i + 1) * step) for i in range(len(tokens))]
    for i in range(len(tokens)):  # tokens sem par: interpolar entre vizinhos
        if times[i]:
            continue
        prev = max((k for k in known if k < i), default=None)
        nxt = min((k for k in known if k > i), default=None)
        t0 = times[prev][1] if prev is not None else 0.0
        t1 = times[nxt][0] if nxt is not None else total
        lo = prev if prev is not None else -1
        hi = nxt if nxt is not None else len(tokens)
        n = hi - lo - 1
        pos = i - lo
        times[i] = (t0 + (t1 - t0) * (pos - 1) / n, t0 + (t1 - t0) * pos / n)
    return times


def _fix_lead(audio: Path, stimes: list, n_words: int, work: Path) -> tuple[Path, list]:
    """Proteção: às vezes o Gemini lê em voz alta as instruções de estilo antes do guião (ex.: 15 s de "Lê em
    português europeu…" com o ecrã parado na 1.ª frase). Corta tudo o que vem antes da 1.ª palavra do guião e
    depois da última, e volta a acertar o ritmo com a duração real."""
    lead, last = stimes[0][0], stimes[-1][1]
    dur = _dur(audio)
    if lead <= 1.0 and dur - last <= 2.0:
        return audio, stimes
    start, end = max(0.0, lead - 0.12), min(dur, last + 0.35)
    print(f"[reel] AVISO: {lead:.1f}s antes do guião e {dur - last:.1f}s depois (instruções lidas?) — cortado")
    out = work / "narration_fix.wav"
    _run("ffmpeg", "-y", "-loglevel", "error", "-i", str(audio), "-af", f"atrim={start:.3f}:{end:.3f},asetpts=PTS-STARTPTS",
         "-ar", "44100", "-ac", "2", str(out))
    st = [(a - start, b - start) for a, b in stimes]
    wpm = n_words / ((end - start) / 60)
    tempo = max(0.87, min(1.0, TARGET_WPM / wpm))
    if tempo < 0.995:
        slow = work / "narration_fix2.wav"
        _run("ffmpeg", "-y", "-loglevel", "error", "-i", str(out), "-af", f"atempo={tempo:.3f}", str(slow))
        out, st = slow, [(a / tempo, b / tempo) for a, b in st]
    print(f"[reel] ritmo real {wpm:.0f} → {wpm * tempo:.0f} palavras/min")
    return out, st


# ---------------- cenas ----------------

# palavras que nunca devem ficar sozinhas no fim de um bloco de legenda ("Segundo a", "IA para", "da probabilidade de")
WEAK = {"a", "o", "as", "os", "um", "uma", "uns", "umas", "de", "do", "da", "dos", "das", "em", "no", "na", "nos", "nas",
        "por", "pelo", "pela", "para", "com", "sem", "e", "ou", "que", "se", "mas", "ao", "aos", "num", "numa",
        "seu", "sua", "meu", "minha", "teu", "tua", "este", "esta", "esse", "essa", "mais", "menos", "muito", "ja",
        "nao", "quem", "como", "quando", "onde", "sao", "foi", "vai", "vao", "ha", "ser", "estar", "ter", "tem",
        "pode", "podem", "deve", "estao", "esta", "the"}  # já sem acentos (comparado com _norm)


def _weak(w: str) -> bool:
    return _norm(w) in WEAK or re.fullmatch(r"\d+([.,]\d+)?", w) is not None


def _destaque_ok(dest: str, fala: str) -> bool:
    """O número em destaque tem de ser o que se ouve (nada de "21%" no ecrã enquanto a voz diz "1 em cada 5")."""
    nums = re.findall(r"\d+(?:[.,]\d+)?", dest)
    if nums:
        return all(n in fala for n in nums)
    key = _norm(dest)
    return bool(key) and key in _norm(fala)


def build_sentences(script: ReelScript, times: list, total: float) -> list[dict]:
    toks = [(ci, w) for ci, c in enumerate(script.cenas) for w in c.fala.split()]
    chunks, cur = [], []
    for i, (ci, w) in enumerate(toks):
        cur.append(i)
        end_cena = i + 1 == len(toks) or toks[i + 1][0] != ci
        hard = end_cena or re.search(r"[.!?:;]$", w)
        soft = len(cur) >= 5 or (w.endswith(",") and len(cur) >= 3)
        # um bloco só fecha num ponto natural: nunca a meio de "a Salesforce" ou "1 em cada 5"
        # palavras até ao próximo fim de frase: não deixar 1–2 palavras órfãs ("claras.", "em órbita.")
        rest = 0
        for _, nw in toks[i + 1:i + 4]:
            rest += 1
            if re.search(r"[.!?:;]$", nw):
                break
        else:
            rest = 99
        orphan = 0 < rest <= 2 and len(cur) + rest <= 9
        if hard or (soft and not _weak(w) and not orphan) or len(cur) >= 8:
            chunks.append(cur)
            cur = []
    merged = []  # juntar blocos curtos demais (< 1,2 s) ao anterior da mesma cena
    for ch in chunks:
        if merged:
            prev = merged[-1]
            d = times[ch[-1]][1] - times[prev[0]][0]
            if (times[prev[-1]][1] - times[prev[0]][0]) < 1.2 and toks[prev[0]][0] == toks[ch[0]][0] \
                    and not re.search(r"[.!?]$", toks[prev[-1]][1]) \
                    and len(prev) + len(ch) <= 9 and d < 3.5:
                prev.extend(ch)
                continue
        merged.append(ch)
    out, seen = [], set()
    for ch in merged:
        ci = toks[ch[0]][0]
        cena = script.cenas[ci]
        kw = _norm(cena.palavra_chave)
        words = [{"text": toks[i][1], "start": round(times[i][0], 3), "end": round(times[i][1], 3),
                  "key": bool(kw) and _norm(toks[i][1]) == kw} for i in ch]
        dest = None
        # o destaque aparece no bloco em que o número é dito (não antes)
        if cena.destaque and ci not in seen and _destaque_ok(cena.destaque, " ".join(toks[i][1] for i in ch)):
            dest = cena.destaque
            seen.add(ci)
        out.append({"start": max(0.0, round(words[0]["start"] - 0.1, 3)), "words": words, "destaque": dest, "cena": ci})
    out[0]["start"] = 0.0
    out[0]["first"] = True
    for i in range(1, len(out)):
        out[i]["start"] = round(max(out[i]["start"], out[i - 1]["start"] + 0.35), 3)
    for i, s in enumerate(out):
        s["end"] = out[i + 1]["start"] if i + 1 < len(out) else total
    return out


# ---------------- montagem ----------------

def render(post: dict, script: ReelScript, out_dir: Path) -> Path:
    work = out_dir / "_work"
    work.mkdir(parents=True, exist_ok=True)
    if script.convite_falado.strip():  # o convite para seguir é a última coisa que se ouve
        words = script.convite_falado.split()
        key = next((w for w in words if _norm(w).startswith("segue")), words[0])
        script = script.model_copy(update={"cenas": [*script.cenas, Cena(fala=script.convite_falado.strip(),
                                                                         palavra_chave=key)]})
    text = "\n\n".join(c.fala for c in script.cenas)
    tokens = text.split()
    said, idx = spoken_tokens(tokens, script.pronuncias)
    audio = narrate(" ".join(said), work)
    stimes = align(audio, said)
    audio, stimes = _fix_lead(audio, stimes, len(said), work)
    times: list = [None] * len(tokens)
    for (st, en), j in zip(stimes, idx):
        times[j] = (st, en) if times[j] is None else (min(times[j][0], st), max(times[j][1], en))
    for j in range(len(times)):  # (segurança) tokens sem tempo herdam o anterior
        if times[j] is None:
            times[j] = times[j - 1] if j else (0.0, 0.2)
    total = round(_dur(audio) + 0.6, 2)  # fim da voz (o cartão final vem depois)
    sentences = build_sentences(script, times, total)
    pub = STUDIO / "public"
    from . import refimages
    imgs = refimages.pick(script.cenas, work)
    (pub / "img").mkdir(exist_ok=True)
    credits = []
    used = set()
    for s_ in sentences:
        ci = s_.pop("cena")
        if ci in imgs:
            name = f"c{ci}.jpg"
            if ci not in used:
                shutil.copy(imgs[ci]["path"], pub / "img" / name)
                used.add(ci)
                credits.append(f"{imgs[ci]['autor']} ({imgs[ci]['fonte']}, {imgs[ci]['licenca'].upper()})")
            s_["image"] = f"img/{name}"
            s_["layout"] = "full" if ci % 2 == 0 else "card"
    (out_dir / "credits.txt").write_text("\n".join(dict.fromkeys(credits)))
    shutil.copy(audio, pub / "narration.wav")
    music = None
    tracks = sorted(MUSIC_DIR.glob("*.mp3")) if MUSIC_DIR.exists() else []
    if tracks:
        shutil.copy(random.choice(tracks), pub / "music.mp3")
        music = "music.mp3"
    props = {"fps": 30, "duration": round(total + OUTRO, 2), "outro": OUTRO, "audio": "narration.wav", "music": music,
             "accent": ACCENTS[post["pilar"]], "label": LABELS[post["pilar"]], "handle": IG_HANDLE,
             "convite": script.convite_seguir.strip() or None,
             "sentences": sentences}
    (pub / "props.json").write_text(json.dumps(props, ensure_ascii=False))
    out = (out_dir / "reel.mp4").resolve()
    subprocess.run(["npx", "remotion", "render", "src/index.ts", "Reel", str(out), "--props=public/props.json",
                    "--log=error", "--crf=20"], cwd=STUDIO, check=True)
    shutil.rmtree(work, ignore_errors=True)
    for f in ("narration.wav", "music.mp3", "props.json"):
        (pub / f).unlink(missing_ok=True)
    shutil.rmtree(pub / "img", ignore_errors=True)
    durs = sorted(round(s["end"] - s["start"], 1) for s in sentences)
    print(f"[reel] {out} ({_dur(out):.1f}s, {out.stat().st_size / 1e6:.1f} MB, {len(sentences)} cenas, "
          f"mediana {durs[len(durs) // 2]}s)")
    return out


def build(post: dict, out_dir: Path) -> tuple[Path, ReelScript]:
    out_dir.mkdir(parents=True, exist_ok=True)
    script = approved_script(post)
    (out_dir / "reel.json").write_text(script.model_dump_json(indent=2))
    return render(post, script, out_dir), script
