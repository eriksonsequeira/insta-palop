import React from "react";
import {
  AbsoluteFill,
  Audio,
  Img,
  Easing,
  Sequence,
  interpolate,
  spring,
  staticFile,
  useCurrentFrame,
  useVideoConfig,
} from "remotion";
import { loadFont as loadDisplay } from "@remotion/google-fonts/SpaceGrotesk";
import { loadFont as loadBody } from "@remotion/google-fonts/Inter";
import { measureText } from "@remotion/layout-utils";

const { fontFamily: DISPLAY } = loadDisplay("normal", { weights: ["500", "700"], subsets: ["latin", "latin-ext"] });
const { fontFamily: BODY } = loadBody("normal", { weights: ["600", "800"], subsets: ["latin", "latin-ext"] });

export type Word = { text: string; start: number; end: number; key?: boolean };
export type Sentence = {
  start: number;
  end: number;
  words: Word[];
  destaque: string | null;
  first?: boolean;
  image?: string;
  layout?: "full" | "card";
};
export type ReelProps = {
  fps: number;
  duration: number;
  audio: string | null;
  music: string | null;
  accent: string;
  label: string;
  handle: string;
  sentences: Sentence[];
  outro?: number; // segundos do cartão final
};

/* zonas seguras do Instagram no telemóvel (1080x1920):
   direita = coluna de botões; baixo = nome + legenda; cima = cabeçalho dos Reels. A câmara mexe ~6%: margem extra. */
const SAFE = { left: 80, right: 200, top: 260, bottom: 480 };
const TEXT_W = 1080 - SAFE.left - SAFE.right - 50; // 750 px úteis

function wordW(text: string, size: number): number {
  return measureText({ text, fontFamily: DISPLAY, fontWeight: "700", fontSize: size, letterSpacing: `${-0.03 * size}px` }).width;
}

/** maior tamanho (≤ max) em que cada palavra cabe na largura e o bloco cabe na altura */
function fitWords(words: { text: string; key?: boolean }[], max: number, height: number): number {
  for (let size = max; size >= 52; size -= 4) {
    let lines = 1;
    let x = 0;
    let fits = true;
    for (const w of words) {
      const ww = wordW(w.text, w.key ? size * 1.28 : size);
      if (ww > TEXT_W) {
        fits = false;
        break;
      }
      const gap = size * 0.24;
      if (x > 0 && x + gap + ww > TEXT_W) {
        lines += 1;
        x = ww;
      } else {
        x += (x > 0 ? gap : 0) + ww;
      }
    }
    if (fits && lines * size * 1.2 <= height) return size;
  }
  return 52;
}

function fitOneLine(text: string, max: number, min = 60): number {
  for (let size = max; size >= min; size -= 4) if (wordW(text, size) <= TEXT_W) return size;
  return min;
}

const INK = "#F4F1EA";
const MUTED = "#8F96AA";
const BG = "#07090F";

/* ---------- fundo vivo ---------- */
const Background: React.FC<{ accent: string }> = ({ accent }) => {
  const f = useCurrentFrame();
  const x1 = 25 + 18 * Math.sin(f / 70);
  const y1 = 18 + 12 * Math.cos(f / 90);
  const x2 = 75 + 15 * Math.cos(f / 85);
  const y2 = 85 + 8 * Math.sin(f / 60);
  return (
    <AbsoluteFill style={{ background: BG }}>
      <AbsoluteFill
        style={{
          background: `radial-gradient(circle at ${x1}% ${y1}%, ${accent}40 0%, transparent 42%),
                       radial-gradient(circle at ${x2}% ${y2}%, ${accent}26 0%, transparent 38%)`,
          filter: "blur(50px)",
        }}
      />
      <AbsoluteFill
        style={{
          backgroundImage:
            "linear-gradient(rgba(244,241,234,.05) 1px, transparent 1px), linear-gradient(90deg, rgba(244,241,234,.05) 1px, transparent 1px)",
          backgroundSize: "90px 90px",
          maskImage: "radial-gradient(ellipse at 50% 40%, #000 0%, transparent 72%)",
        }}
      />
      <AbsoluteFill style={{ opacity: 0.08, mixBlendMode: "overlay" }}>
        <svg width="100%" height="100%">
          <filter id="g">
            <feTurbulence type="fractalNoise" baseFrequency="0.85" seed={f % 6} />
          </filter>
          <rect width="100%" height="100%" filter="url(#g)" />
        </svg>
      </AbsoluteFill>
      {/* vinheta */}
      <AbsoluteFill style={{ background: "radial-gradient(ellipse at 50% 45%, transparent 55%, rgba(0,0,0,.55) 100%)" }} />
    </AbsoluteFill>
  );
};

/* ---------- número que conta ---------- */
const CountUp: React.FC<{ text: string; accent: string; frame: number; fps: number }> = ({ text, accent, frame, fps }) => {
  const m = text.match(/^(\D*?)(\d+(?:[.,]\d+)?)(.*)$/);
  const pop = spring({ frame, fps, config: { damping: 10, stiffness: 170 } });
  let shown = text;
  const val = m ? parseFloat(m[2].replace(/\s/g, "").replace(",", ".")) : 0;
  const isYear = !!m && /^(19|20)\d\d$/.test(m[2]);
  if (m && val >= 10 && !isYear && !/^\s\d/.test(m[3])) {
    const [, pre, num, post] = m;
    const dec = /[.,]/.test(num) ? num.split(/[.,]/)[1].length : 0;
    const target = parseFloat(num.replace(",", "."));
    const k = interpolate(frame, [0, 0.8 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
    let s = (target * k).toFixed(dec);
    if (num.includes(",")) s = s.replace(".", ",");
    shown = `${pre}${s}${post}`;
  }
  const size = fitOneLine(text, text.length > 6 ? 190 : 240);
  return (
    <div
      style={{
        fontFamily: DISPLAY,
        fontWeight: 700,
        fontSize: size,
        lineHeight: 0.95,
        letterSpacing: "-0.05em",
        color: accent,
        opacity: frame < 0 ? 0 : 1,
        transform: `scale(${0.7 + 0.3 * pop})`,
        transformOrigin: "left bottom",
        textShadow: `0 0 80px ${accent}55`,
        marginBottom: 28,
      }}
    >
      {shown}
    </div>
  );
};

/* ---------- frase que se escreve à medida que é dita ---------- */
const SentenceView: React.FC<{ s: Sentence; accent: string; label: string }> = ({ s, accent, label }) => {
  const frame = useCurrentFrame(); // relativo ao início da cena
  const { fps } = useVideoConfig();
  const t = s.start + frame / fps; // tempo absoluto
  const dur = Math.max(2, (s.end - s.start) * fps);
  // câmara: deriva lenta, direção alterna por cena
  const dir = Math.round(s.start * 10) % 2 === 0 ? 1 : -1;
  const scale = interpolate(frame, [0, dur], [1.0, 1.06], { extrapolateRight: "clamp" });
  const dx = interpolate(frame, [0, dur], [0, 18 * dir], { extrapolateRight: "clamp" });
  const n = s.words.length;
  const card = !!s.image && s.layout === "card";
  const reserved = (s.first ? 110 : 0) + (s.destaque ? 230 : 0);
  const height = (card ? 1920 - 950 - SAFE.bottom : 1920 - SAFE.top - SAFE.bottom) - reserved;
  const size = React.useMemo(() => fitWords(s.words, n <= 3 ? 150 : n <= 6 ? 124 : 104, height), [s.words, n, height]);
  const numberAt = s.destaque ? (s.words.find((w) => /\d/.test(w.text))?.start ?? s.words[0]?.start ?? s.start) : 0;
  return (
    <AbsoluteFill style={{ transform: `translateX(${dx}px) scale(${scale})` }}>
      {s.image && s.layout === "full" && (
        <AbsoluteFill>
          <Img src={staticFile(s.image)} style={{ width: "100%", height: "100%", objectFit: "cover", filter: "brightness(.42) saturate(.9) contrast(1.05)", transform: `scale(${1.04 + 0.04 * (frame / Math.max(1, dur))})` }} />
          <AbsoluteFill style={{ background: "linear-gradient(180deg, rgba(7,9,15,.55) 0%, rgba(7,9,15,.15) 35%, rgba(7,9,15,.75) 100%)" }} />
        </AbsoluteFill>
      )}
      {s.image && s.layout === "card" && (
        <div
          style={{
            position: "absolute",
            top: SAFE.top,
            left: SAFE.left,
            right: SAFE.left,
            height: 640,
            borderRadius: 36,
            overflow: "hidden",
            boxShadow: `0 30px 80px rgba(0,0,0,.6), 0 0 0 2px ${accent}55`,
            transform: `translateY(${interpolate(frame, [0, 8], [40, 0], { extrapolateRight: "clamp" })}px)`,
            opacity: interpolate(frame, [0, 5], [0, 1], { extrapolateRight: "clamp" }),
          }}
        >
          <Img src={staticFile(s.image)} style={{ width: "100%", height: "100%", objectFit: "cover", transform: `scale(${1.02 + 0.06 * (frame / Math.max(1, dur))})` }} />
        </div>
      )}
      <AbsoluteFill
        style={{
          padding: card
            ? `950px ${SAFE.right}px ${SAFE.bottom}px ${SAFE.left}px`
            : `${SAFE.top}px ${SAFE.right}px ${SAFE.bottom}px ${SAFE.left}px`,
          display: "flex",
          flexDirection: "column",
          justifyContent: card ? "flex-start" : "center",
        }}
      >
        {s.first && (
          <div
            style={{
              alignSelf: "flex-start",
              fontFamily: BODY,
              fontWeight: 800,
              fontSize: 30,
              letterSpacing: "0.14em",
              textTransform: "uppercase",
              color: accent,
              border: `3px solid ${accent}`,
              borderRadius: 999,
              padding: "14px 28px",
              marginBottom: 44,
            }}
          >
            {label}
          </div>
        )}
        {s.destaque && <CountUp text={s.destaque} accent={accent} frame={(t - numberAt) * fps} fps={fps} />}
        <div style={{ fontFamily: DISPLAY, fontWeight: 700, fontSize: size, lineHeight: 1.08, letterSpacing: "-0.03em" }}>
          {s.words.map((w, i) => {
            const local = (t - w.start) * fps;
            // a frase inteira entra logo (lê-se de uma vez); cada palavra acende quando é dita
            const p = spring({ frame: frame - i * 1.2, fps, config: { damping: 16, stiffness: 220 } });
            const spoken = t >= w.start - 0.02;
            const speaking = t >= w.start && t < w.end + 0.08;
            return (
              <span
                key={i}
                style={{
                  position: "relative",
                  display: "inline-block",
                  marginRight: "0.24em",
                  opacity: p * (spoken ? 1 : 0.38),
                  transform: `translateY(${(1 - p) * 26}px) scale(${w.key ? 1 + 0.06 * (speaking ? 1 : 0) : 1})`,
                  color: w.key ? accent : speaking ? INK : "rgba(244,241,234,.92)",
                  fontSize: w.key ? "1.28em" : "1em",
                  textShadow: w.key ? `0 0 40px ${accent}66` : "none",
                }}
              >
                {w.text}
                {w.key && (
                  <span
                    style={{
                      position: "absolute",
                      left: 0,
                      right: 0,
                      bottom: "0.02em",
                      height: "0.09em",
                      borderRadius: 8,
                      background: accent,
                      transformOrigin: "left",
                      transform: `scaleX(${interpolate(local, [2, 9], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })})`,
                    }}
                  />
                )}
              </span>
            );
          })}
        </div>
      </AbsoluteFill>
    </AbsoluteFill>
  );
};

/* ---------- cartão final ---------- */
const EndCard: React.FC<{ accent: string; handle: string; label: string }> = ({ accent, handle, label }) => {
  const f = useCurrentFrame();
  const { fps } = useVideoConfig();
  const a = (d: number) => spring({ frame: f - d, fps, config: { damping: 16, stiffness: 180 } });
  const item = (d: number): React.CSSProperties => ({ opacity: a(d), transform: `translateY(${(1 - a(d)) * 30}px)` });
  return (
    <AbsoluteFill
      style={{
        padding: `${SAFE.top}px ${SAFE.right}px ${SAFE.bottom}px ${SAFE.left}px`,
        display: "flex",
        flexDirection: "column",
        justifyContent: "center",
        opacity: interpolate(f, [0, 6], [0, 1], { extrapolateRight: "clamp" }),
      }}
    >
      <div style={{ ...item(0), fontFamily: BODY, fontWeight: 800, fontSize: 30, letterSpacing: "0.14em", textTransform: "uppercase", color: accent, marginBottom: 36 }}>
        {label}
      </div>
      <div style={{ ...item(4), fontFamily: DISPLAY, fontWeight: 700, fontSize: Math.min(104, fitOneLine(handle, 104)), lineHeight: 1.02, letterSpacing: "-0.04em", color: INK }}>
        {handle}
      </div>
      <div style={{ ...item(9), height: 8, width: 180, borderRadius: 8, background: accent, margin: "40px 0" }} />
      {["Guarda para rever", "Partilha com quem precisa", "Segue para mais"].map((t, i) => (
        <div key={t} style={{ ...item(13 + i * 4), fontFamily: BODY, fontWeight: 600, fontSize: 46, color: "rgba(244,241,234,.9)", marginBottom: 22, display: "flex", alignItems: "center", gap: 22 }}>
          <span style={{ width: 16, height: 16, borderRadius: 99, background: accent, display: "inline-block" }} />
          {t}
        </div>
      ))}
    </AbsoluteFill>
  );
};

/* ---------- composição ---------- */
export const Reel: React.FC<ReelProps> = (p) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const S = p.sentences;
  const outroF = Math.round((p.outro ?? 0) * fps);
  const contentEnd = durationInFrames - outroF;
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Background accent={p.accent} />
      {S.map((s, i) => {
        const from = Math.round(s.start * fps);
        const to = i === S.length - 1 ? contentEnd : Math.round(S[i + 1].start * fps);
        return (
          <Sequence key={i} from={from} durationInFrames={Math.max(1, to - from)}>
            <SentenceView s={s} accent={p.accent} label={p.label} />
          </Sequence>
        );
      })}
      {outroF > 0 && (
        <Sequence from={contentEnd} durationInFrames={outroF}>
          <EndCard accent={p.accent} handle={p.handle} label={p.label} />
        </Sequence>
      )}
      {/* efeitos sonoros: impacto no 1.º quadro, clique em cada corte, pop nos números */}
      <Sequence from={0} durationInFrames={20}>
        <Audio src={staticFile("impacto.wav")} volume={0.9} />
      </Sequence>
      {S.slice(1).map((s, i) => (
        <Sequence key={`c${i}`} from={Math.round(s.start * fps)} durationInFrames={6}>
          <Audio src={staticFile("clique.wav")} volume={0.35} />
        </Sequence>
      ))}
      {S.filter((s) => s.destaque).map((s, i) => {
        const at = s.words.find((w) => /\d/.test(w.text))?.start ?? s.start;
        return (
          <Sequence key={`p${i}`} from={Math.round(at * fps)} durationInFrames={6}>
            <Audio src={staticFile("pop.wav")} volume={0.5} />
          </Sequence>
        );
      })}
      {/* barra de progresso + assinatura (fora da zona dos botões, à direita/baixo) */}
      <div style={{ position: "absolute", top: 0, left: 0, height: 10, width: `${(f / durationInFrames) * 100}%`, background: p.accent }} />
      {p.audio && <Audio src={staticFile(p.audio)} />}
      {p.music && (
        <Audio
          src={staticFile(p.music)}
          volume={(fr) =>
            // por baixo da voz a 22%; sobe no cartão final e desvanece no fim
            interpolate(fr, [0, 10, contentEnd - 10, contentEnd + 8, durationInFrames - 20, durationInFrames], [0, 0.22, 0.22, 0.4, 0.4, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
          }
        />
      )}
    </AbsoluteFill>
  );
};
