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
};

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
  if (m) {
    const [, pre, num, post] = m;
    const dec = /[.,]/.test(num) ? num.split(/[.,]/)[1].length : 0;
    const target = parseFloat(num.replace(",", "."));
    const k = interpolate(frame, [0, 0.8 * fps], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp", easing: Easing.out(Easing.cubic) });
    let s = (target * k).toFixed(dec);
    if (num.includes(",")) s = s.replace(".", ",");
    shown = `${pre}${s}${post}`;
  }
  const size = text.length > 9 ? 140 : text.length > 6 ? 180 : 240;
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
  const size = n <= 3 ? 150 : n <= 6 ? 120 : n <= 9 ? 98 : 82;
  const keyWord = s.words.find((w) => w.key)?.text.replace(/[.,!?;:]/g, "");
  const ghostX = interpolate(frame, [0, dur], [40, -60], { extrapolateRight: "clamp" });
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
            top: 250,
            left: 80,
            right: 80,
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
      <div
        style={{
          position: "absolute",
          width: 760,
          height: 760,
          borderRadius: "50%",
          border: `2px solid ${accent}33`,
          boxShadow: `inset 0 0 120px ${accent}14`,
          left: dir > 0 ? 520 : -200,
          top: 180,
          transform: `rotate(${frame * 0.6}deg) scale(${interpolate(frame, [0, 10], [0.92, 1], { extrapolateRight: "clamp" })})`,
          borderTopColor: accent,
        }}
      />
      {keyWord && (
        <div
          style={{
            position: "absolute",
            top: 1270,
            left: ghostX,
            whiteSpace: "nowrap",
            fontFamily: DISPLAY,
            fontWeight: 700,
            fontSize: 330,
            letterSpacing: "-0.05em",
            color: accent,
            opacity: 0.07,
            textTransform: "uppercase",
          }}
        >
          {keyWord}
        </div>
      )}
      <AbsoluteFill
        style={{
          padding: s.image && s.layout === "card" ? "960px 80px 330px 80px" : "340px 80px 380px 80px",
          display: "flex",
          flexDirection: "column",
          justifyContent: s.image && s.layout === "card" ? "flex-start" : "center",
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
            const p = spring({ frame: local, fps, config: { damping: 15, stiffness: 260 } });
            const spoken = t >= w.start - 0.02;
            const speaking = t >= w.start && t < w.end + 0.08;
            return (
              <span
                key={i}
                style={{
                  position: "relative",
                  display: "inline-block",
                  marginRight: "0.24em",
                  opacity: spoken ? p : 0,
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

/* ---------- composição ---------- */
export const Reel: React.FC<ReelProps> = (p) => {
  const f = useCurrentFrame();
  const { fps, durationInFrames } = useVideoConfig();
  const S = p.sentences;
  return (
    <AbsoluteFill style={{ background: BG }}>
      <Background accent={p.accent} />
      {S.map((s, i) => {
        const from = Math.round(s.start * fps);
        const to = i === S.length - 1 ? durationInFrames : Math.round(S[i + 1].start * fps);
        return (
          <Sequence key={i} from={from} durationInFrames={Math.max(1, to - from)}>
            <SentenceView s={s} accent={p.accent} label={p.label} />
          </Sequence>
        );
      })}
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
      <div style={{ position: "absolute", top: 120, left: 80, fontFamily: BODY, fontWeight: 600, fontSize: 30, color: MUTED }}>{p.handle}</div>
      {p.audio && <Audio src={staticFile(p.audio)} />}
      {p.music && (
        <Audio
          src={staticFile(p.music)}
          volume={(fr) =>
            0.07 * interpolate(fr, [0, 10, durationInFrames - 25, durationInFrames], [0, 1, 1, 0], { extrapolateLeft: "clamp", extrapolateRight: "clamp" })
          }
        />
      )}
    </AbsoluteFill>
  );
};
