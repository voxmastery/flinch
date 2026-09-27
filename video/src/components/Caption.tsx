import React from "react";
import { useCurrentFrame } from "remotion";
import { C, FONT } from "../theme";
import { fadeUp } from "./Scene";

interface Props { text: string; at?: number; sub?: string; bottom?: number; size?: number }

/** One idea per scene: a large display line centred near the bottom. */
export const Caption: React.FC<Props> = ({ text, at = 0, sub, bottom = 70, size = 60 }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{
      position: "absolute", left: 120, right: 120, bottom, textAlign: "center", ...fadeUp(frame, at, 14),
    }}>
      <div style={{
        fontFamily: FONT.display, fontWeight: 700, fontSize: size, letterSpacing: "-0.02em",
        lineHeight: 1.1, color: C.text,
      }}>{text}</div>
      {sub ? (
        <div style={{ marginTop: 14, fontFamily: FONT.body, fontSize: 44, color: C.muted }}>{sub}</div>
      ) : null}
    </div>
  );
};
