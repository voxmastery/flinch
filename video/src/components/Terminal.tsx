import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { C, FONT } from "../theme";

export type LineKind = "cmd" | "out" | "ok" | "deny" | "ask" | "user" | "agent";
export interface Line { at: number; text: string; kind: LineKind; label?: string }

import { CHARS_PER_FRAME } from "../timeline";
const TYPED: LineKind[] = ["cmd", "user"];

const COLOR: Record<LineKind, string> = {
  cmd: C.text, out: C.muted, ok: C.calm, deny: C.pain, ask: C.wary, user: C.text, agent: C.text,
};

const LineView: React.FC<{ line: Line; frame: number; isLast: boolean }> = ({ line, frame, isLast }) => {
  const since = frame - line.at;
  const typed = TYPED.includes(line.kind);
  const shown = typed ? line.text.slice(0, Math.max(0, Math.floor(since * CHARS_PER_FRAME))) : line.text;
  const done = !typed || shown.length >= line.text.length;
  const caret = isLast && Math.floor(frame / 15) % 2 === 0;
  const opacity = typed ? 1 : interpolate(since, [0, 8], [0, 1], { extrapolateRight: "clamp" });
  const prose = line.kind === "user" || line.kind === "agent";
  const boxed = line.kind === "deny" || line.kind === "ask";
  return (
    <div style={{
      opacity, color: COLOR[line.kind], whiteSpace: "pre-wrap", wordBreak: "break-word",
      fontFamily: prose ? FONT.body : FONT.mono, fontSize: prose ? 34 : 28, lineHeight: 1.45,
      ...(boxed ? { borderLeft: `4px solid ${COLOR[line.kind]}`, paddingLeft: 18, margin: "6px 0" } : {}),
    }}>
      {line.label ? (
        <span style={{ color: C.muted, fontFamily: FONT.body, fontSize: 26, display: "block" }}>{line.label}</span>
      ) : null}
      {line.kind === "cmd" ? <span style={{ color: C.muted }}>$ </span> : null}
      {shown}
      {!done || (isLast && typed) ? (
        <span style={{ opacity: caret || !done ? 1 : 0, color: C.calm }}>▍</span>
      ) : null}
    </div>
  );
};

interface Props { title: string; lines: Line[]; width: number; height: number; style?: React.CSSProperties }

/** A calm terminal pane. Lines appear at their frame; commands type out. */
export const Terminal: React.FC<Props> = ({ title, lines, width, height, style }) => {
  const frame = useCurrentFrame();
  const visible = lines.filter((l) => l.at <= frame);
  return (
    <div style={{
      position: "absolute", width, height, background: C.raised, border: `2px solid ${C.line}`,
      borderRadius: 20, overflow: "hidden", ...style,
    }}>
      <div style={{
        height: 58, borderBottom: `2px solid ${C.line}`, display: "flex", alignItems: "center",
        padding: "0 26px", fontFamily: FONT.body, fontSize: 26, color: C.muted,
      }}>{title}</div>
      <div style={{ padding: "22px 30px", display: "flex", flexDirection: "column", gap: 10 }}>
        {visible.map((l, i) => (
          <LineView key={i} line={l} frame={frame} isLast={i === visible.length - 1} />
        ))}
      </div>
    </div>
  );
};
