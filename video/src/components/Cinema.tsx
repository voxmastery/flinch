import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { cellJitter } from "../data";

const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** Animated film grain: seeded turbulence, reseeded every frame, very low opacity. */
export const FilmGrain: React.FC<{ opacity?: number }> = ({ opacity = 0.07 }) => {
  const frame = useCurrentFrame();
  return (
    <AbsoluteFill style={{ pointerEvents: "none", mixBlendMode: "overlay", opacity }}>
      <svg width="100%" height="100%">
        <filter id="grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.85" numOctaves={2} seed={frame % 61} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#grain)" />
      </svg>
    </AbsoluteFill>
  );
};

export const Vignette: React.FC<{ strength?: number }> = ({ strength = 0.7 }) => (
  <AbsoluteFill style={{
    pointerEvents: "none",
    background: `radial-gradient(ellipse 75% 70% at 50% 48%, rgba(0,0,0,0) 55%, rgba(4,5,14,${strength}) 100%)`,
  }} />
);

/** Short light-leak flash centred on each cut (6-10 frames). */
export const LightLeaks: React.FC<{ cuts: number[] }> = ({ cuts }) => {
  const frame = useCurrentFrame();
  const amt = Math.max(0, ...cuts.map((c) => interpolate(frame, [c - 4, c, c + 6], [0, 1, 0], CLAMP)));
  if (amt <= 0) return null;
  const x = 30 + 40 * cellJitter(Math.round(frame / 20));
  return (
    <AbsoluteFill style={{
      pointerEvents: "none", mixBlendMode: "screen", opacity: 0.55 * amt,
      background: `radial-gradient(ellipse 60% 80% at ${x}% 40%, rgba(255,244,230,0.95), rgba(232,234,246,0.35) 45%, rgba(0,0,0,0) 75%)`,
    }} />
  );
};

/** Seeded shake offset for a glitch that started `since` frames ago. */
export const shake = (since: number, len = 12, px = 14) => {
  if (since < 0 || since >= len) return { x: 0, y: 0 };
  const k = 1 - since / len;
  return { x: (cellJitter(since * 7 + 1) - 0.5) * 2 * px * k, y: (cellJitter(since * 13 + 5) - 0.5) * 2 * px * k };
};

/** Chromatic split + shake for ~12 frames after `at` (frame-driven). */
export const Glitch: React.FC<{ at: number; len?: number; px?: number; children: React.ReactNode; id: string }> = ({
  at, len = 12, px = 14, children, id,
}) => {
  const frame = useCurrentFrame();
  const since = frame - at;
  const active = since >= 0 && since < len;
  const k = active ? 1 - since / len : 0;
  const d = 10 * k * (since % 2 === 0 ? 1 : -0.7);
  const { x, y } = shake(since, len, px);
  const channel = (row: string, dx: number, name: string) => (
    <>
      <feColorMatrix in="SourceGraphic" type="matrix" values={row} result={`${name}0`} />
      <feOffset in={`${name}0`} dx={dx} dy={0} result={name} />
    </>
  );
  return (
    <AbsoluteFill style={{ transform: `translate(${x}px, ${y}px)`, filter: active ? `url(#${id})` : undefined }}>
      {active ? (
        <svg width={0} height={0} style={{ position: "absolute" }}>
          <filter id={id} x="-5%" y="-5%" width="110%" height="110%" colorInterpolationFilters="sRGB">
            {channel("1 0 0 0 0  0 0 0 0 0  0 0 0 0 0  0 0 0 1 0", d, "r")}
            {channel("0 0 0 0 0  0 1 0 0 0  0 0 0 0 0  0 0 0 1 0", 0, "g")}
            {channel("0 0 0 0 0  0 0 0 0 0  0 0 1 0 0  0 0 0 1 0", -d, "b")}
            <feBlend in="r" in2="g" mode="screen" result="rg" />
            <feBlend in="rg" in2="b" mode="screen" />
          </filter>
        </svg>
      ) : null}
      {children}
    </AbsoluteFill>
  );
};

/** A red wash that flashes briefly (used on the delete). */
export const RedFlash: React.FC<{ at: number }> = ({ at }) => {
  const frame = useCurrentFrame();
  const o = interpolate(frame, [at, at + 2, at + 10], [0, 0.35, 0], CLAMP);
  if (o <= 0) return null;
  return <AbsoluteFill style={{ background: "#FF4D5E", mixBlendMode: "screen", opacity: o, pointerEvents: "none" }} />;
};
