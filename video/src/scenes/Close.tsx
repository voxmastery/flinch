import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Scene, focusIn } from "../components/Scene";
import { Creature } from "../components/Creature";
import { C, FONT } from "../theme";
import { cues } from "../timeline";

const Q = cues("close");
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const BigLine: React.FC<{ text: string; at: number; size?: number; color?: string; weight?: number }> = ({ text, at, size = 128, color = C.text, weight = 800 }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ fontFamily: FONT.display, fontWeight: weight, fontSize: size, letterSpacing: "-0.04em", lineHeight: 1.02,
      color, ...focusIn(frame, at, 14) }}>{text}</div>
  );
};

const Install: React.FC<{ text: string }> = ({ text }) => (
  <div style={{ fontFamily: FONT.mono, fontSize: 30, background: C.raised, border: `2px solid ${C.line}`, borderRadius: 14, padding: "12px 26px" }}>
    <span style={{ color: C.muted }}>$ </span>{text}
  </div>
);

export const Close: React.FC = () => {
  const frame = useCurrentFrame();
  const out = interpolate(frame, [Q.wordmark - 14, Q.wordmark - 2], [1, 0], CLAMP);
  const mark = interpolate(frame, [Q.wordmark, Q.wordmark + 18], [0, 1], CLAMP);
  return (
    <Scene fadeOut={false} push={1.03}>
      <div style={{ position: "absolute", left: 220, top: 200, opacity: out }}>
        <BigLine text="Claude Code." at={Q.line1} />
        <BigLine text="Cursor." at={Q.line2} />
        <BigLine text="Any agent." at={Q.line3} />
        <div style={{ height: 36 }} />
        <BigLine text="Offline. No API keys." at={Q.line4} size={60} weight={600} color={C.muted} />
      </div>
      <div style={{ position: "absolute", inset: 0, opacity: mark }}>
        <div style={{ position: "absolute", left: 0, right: 0, top: 230, display: "flex", justifyContent: "center", alignItems: "center", gap: 44,
          transform: `scale(${0.96 + 0.04 * mark})` }}>
          <Creature size={250} cues={[{ at: Q.wordmark, mood: "healing" }]} />
          <div style={{ fontFamily: FONT.display, fontWeight: 800, fontSize: 230, letterSpacing: "-0.05em", lineHeight: 1,
            marginTop: -24, textShadow: "0 0 60px rgba(232,234,246,0.18)" }}>flinch</div>
        </div>
        <div style={{ position: "absolute", left: 0, right: 0, top: 560, textAlign: "center" }}>
          <BigLine text="Pain receptors for AI agents." at={Q.receptors} size={72} weight={700} />
          <div style={{ marginTop: 16, fontFamily: FONT.body, fontSize: 44, color: C.muted, ...focusIn(frame, Q.tagline) }}>
            It never makes the same mistake twice.
          </div>
        </div>
        <div style={{ position: "absolute", left: 0, right: 0, top: 850, display: "flex", justifyContent: "center", gap: 28,
          ...focusIn(frame, Q.install) }}>
          <Install text="claude plugin install flinch@flinch-local" />
          <Install text="flinch cursor install" />
        </div>
      </div>
    </Scene>
  );
};
