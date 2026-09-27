import React from "react";
import { C, FONT } from "../theme";
import { FLINCH_LINE, WARY_LINE } from "../data";

interface Props { label: string; value: number; width: number; lines?: boolean; verdict?: string; verdictOpacity?: number; color?: string }

export const stateColor = (v: number) => (v >= FLINCH_LINE ? C.pain : v >= WARY_LINE ? C.wary : C.calm);

/** Horizontal meter with the real thresholds marked (asks at 0.25, flinch at 0.55). */
export const Meter: React.FC<Props> = ({ label, value, width, lines = true, verdict, verdictOpacity = 1, color }) => {
  const col = color ?? stateColor(value);
  const mark = (at: number, text: string) => (
    <div style={{ position: "absolute", left: at * width, top: -10, height: 58, borderLeft: `2px dashed ${C.muted}` }}>
      <div style={{ position: "absolute", top: 60, left: -80, width: 160, textAlign: "center",
        fontFamily: FONT.body, fontSize: 24, color: C.muted }}>{text}</div>
    </div>
  );
  return (
    <div style={{ width, fontFamily: FONT.body }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "baseline", marginBottom: 16 }}>
        <span style={{ fontSize: 30, color: C.muted }}>{label}</span>
        <span style={{ fontFamily: FONT.mono, fontSize: 44, fontWeight: 600, color: col }}>{value.toFixed(2)}</span>
      </div>
      <div style={{ position: "relative", height: 38, borderRadius: 19, background: C.cellDim }}>
        <div style={{ position: "absolute", left: 0, top: 0, bottom: 0, width: value * width, borderRadius: 19, background: col }} />
        {lines ? (<>{mark(WARY_LINE, "asks")}{mark(FLINCH_LINE, "flinch line")}</>) : null}
      </div>
      {verdict ? (
        <div style={{ marginTop: lines ? 64 : 22, fontFamily: FONT.display, fontWeight: 700, fontSize: 46,
          color: col, opacity: verdictOpacity, letterSpacing: "-0.01em" }}>{verdict}</div>
      ) : null}
    </div>
  );
};
