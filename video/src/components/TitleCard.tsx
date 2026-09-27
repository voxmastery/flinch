import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { C, FONT } from "../theme";
import { focusIn } from "./Scene";

interface Props { text: string; at: number; size?: number; weight?: number; top?: number; color?: string; out?: number }

/** Big display title that racks into focus. */
export const TitleCard: React.FC<Props> = ({ text, at, size = 104, weight = 800, top, color = C.text, out }) => {
  const frame = useCurrentFrame();
  const f = focusIn(frame, at, 18);
  const gone = out === undefined ? 0 : interpolate(frame, [out, out + 12], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <div style={{
      position: "absolute", left: 100, right: 100, textAlign: "center",
      ...(top === undefined ? { top: "50%", marginTop: -size * 0.6 } : { top }),
      fontFamily: FONT.display, fontWeight: weight, fontSize: size, letterSpacing: "-0.035em", lineHeight: 1.05,
      color, ...f, opacity: f.opacity * (1 - gone),
      textShadow: "0 0 40px rgba(232,234,246,0.18)",
    }}>{text}</div>
  );
};
