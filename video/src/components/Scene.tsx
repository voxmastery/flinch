import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame, useVideoConfig } from "remotion";
import { C, FONT } from "../theme";

const FADE = 8;
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

/** Faint far-away grid behind the UI: slower motion (parallax) and blurred (depth of field). */
const Backdrop: React.FC = () => {
  const frame = useCurrentFrame();
  const pitch = 34;
  return (
    <AbsoluteFill style={{
      transform: `translate(${-frame * 0.12}px, ${-frame * 0.2}px) scale(1.15)`, filter: "blur(3px)", opacity: 0.35,
    }}>
      <svg width="130%" height="130%" style={{ position: "absolute", left: "-10%", top: "-10%" }}>
        <pattern id="bgcells" width={pitch} height={pitch} patternUnits="userSpaceOnUse">
          <rect x={6} y={6} width={pitch - 12} height={pitch - 12} rx={5} fill={C.cellDim} />
        </pattern>
        <rect width="100%" height="100%" fill="url(#bgcells)" />
      </svg>
    </AbsoluteFill>
  );
};

interface SceneProps {
  children: React.ReactNode;
  fadeIn?: boolean;
  fadeOut?: boolean;
  backdrop?: boolean;
  /** Camera push-in over the whole scene, e.g. 1.06. */
  push?: number;
  background?: string;
}

/** Scene shell: background, parallax backdrop, slow push-in and short crossfades. */
export const Scene: React.FC<SceneProps> = ({
  children, fadeIn = true, fadeOut = true, backdrop = true, push = 1.06, background = C.ground,
}) => {
  const frame = useCurrentFrame();
  const { durationInFrames } = useVideoConfig();
  const a = fadeIn ? interpolate(frame, [0, FADE], [0, 1], CLAMP) : 1;
  const b = fadeOut ? interpolate(frame, [durationInFrames - FADE, durationInFrames], [1, 0], CLAMP) : 1;
  const scale = interpolate(frame, [0, durationInFrames], [1, push]);
  return (
    <AbsoluteFill style={{ backgroundColor: background, opacity: Math.min(a, b), fontFamily: FONT.body, color: C.text }}>
      {backdrop ? <Backdrop /> : null}
      <AbsoluteFill style={{ transform: `scale(${scale})` }}>{children}</AbsoluteFill>
    </AbsoluteFill>
  );
};

export const fadeUp = (frame: number, at: number, len = 12) => {
  const k = interpolate(frame, [at, at + len], [0, 1], CLAMP);
  return { opacity: k, transform: `translateY(${(1 - k) * 14}px)` };
};

/** Focus pull: blurred and faint before `at`, sharp after (depth-of-field feel). */
export const focusIn = (frame: number, at: number, len = 16) => {
  const k = interpolate(frame, [at, at + len], [0, 1], CLAMP);
  return { opacity: k, filter: `blur(${(1 - k) * 10}px)`, transform: `translateY(${(1 - k) * 18}px)` };
};

/** Small quiet label such as "Next session". */
export const Chip: React.FC<{ text: string; at?: number; style?: React.CSSProperties }> = ({ text, at = 0, style }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{
      position: "absolute", fontFamily: FONT.body, fontSize: 30, color: C.muted,
      border: `2px solid ${C.line}`, borderRadius: 999, padding: "8px 24px", ...fadeUp(frame, at), ...style,
    }}>{text}</div>
  );
};
