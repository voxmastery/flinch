import React from "react";
import { AbsoluteFill, interpolate, useCurrentFrame } from "remotion";
import { Scene } from "../components/Scene";
import { TitleCard } from "../components/TitleCard";
import { C, FONT } from "../theme";
import { cues } from "../timeline";

const Q = cues("cold");

export const ColdOpen: React.FC = () => {
  const frame = useCurrentFrame();
  const on = Math.floor(frame / 15) % 2 === 0;
  const cursorFade = interpolate(frame, [Q.title - 10, Q.title + 10], [1, 0.35], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <Scene fadeIn={false} backdrop={false} push={1.04}>
      <AbsoluteFill style={{ background: "#000", opacity: 0.55 }} />
      <div style={{ position: "absolute", left: 300, top: 360, fontFamily: FONT.mono, fontSize: 44, color: C.muted, opacity: cursorFade }}>
        $ <span style={{ color: C.text, opacity: on ? 1 : 0 }}>▍</span>
      </div>
      <TitleCard text="3:12 AM. Your agent is cleaning up." at={Q.title} size={76} weight={600} top={560} />
    </Scene>
  );
};
