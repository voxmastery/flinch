import React from "react";
import { interpolate } from "remotion";
import { C } from "../theme";
import { COLS, ROWS, PAIN, cellJitter } from "../data";

const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const PAIN_CELLS = PAIN.map((w, i) => ({ i, w })).filter((c) => c.w > 0);
const PAIN_SET = new Set(PAIN_CELLS.map((c) => c.i));

export interface GridProps {
  width: number;
  /** 0..1: how far the pain memory has bloomed in (lower it again to cool the scar). */
  painAmt: number;
  active?: number[];
  activeAmt?: number;
  /** 0..1 extra white-hot pulse on overlapping cells. */
  hot?: number;
  /** 0..1 dims the non-overlapping pain cells so the overlap reads. */
  dimPain?: number;
  /** 0..1 glow strength around lit cells. */
  bloom?: number;
  /** "ground" = base + pain, "active" = only the command's cells (for a raised 3D layer). */
  only?: "ground" | "active";
  idKey?: string;
}

const stagger = (amt: number, i: number) =>
  interpolate(amt, [cellJitter(i) * 0.6, cellJitter(i) * 0.6 + 0.4], [0, 1], CLAMP);

/** The real 80x50 reflex grid. Pain cells red, active cells pale, overlap white-hot. */
export const ReflexGrid: React.FC<GridProps> = ({
  width, painAmt, active = [], activeAmt = 0, hot = 0, dimPain = 0, bloom = 0, only, idKey = "g",
}) => {
  const pitch = width / COLS;
  const cell = pitch * 0.74;
  const off = (pitch - cell) / 2;
  const height = pitch * ROWS;
  const xy = (i: number) => ({ x: (i % COLS) * pitch + off, y: Math.floor(i / COLS) * pitch + off });
  const activeSet = new Set(active);
  const overlap = active.filter((i) => PAIN_SET.has(i));
  const activeOnly = active.filter((i) => !PAIN_SET.has(i));
  const showGround = only !== "active";
  const showActive = only !== "ground";
  const r = cell * 0.25;

  const painRects = PAIN_CELLS.map(({ i, w }) => {
    const { x, y } = xy(i);
    const lit = activeSet.has(i) && activeAmt > 0;
    const o = w * stagger(painAmt, i) * (lit ? 1 : 1 - 0.35 * dimPain);
    return <rect key={`p${i}`} x={x} y={y} width={cell} height={cell} rx={r} fill={C.pain} opacity={o} />;
  });
  const activeRects = activeOnly.map((i) => {
    const { x, y } = xy(i);
    return <rect key={`a${i}`} x={x} y={y} width={cell} height={cell} rx={r} fill={C.muted}
      opacity={0.9 * stagger(activeAmt, i)} />;
  });
  const hotRects = overlap.map((i) => {
    const { x, y } = xy(i);
    return <rect key={`o${i}`} x={x} y={y} width={cell} height={cell} rx={r} fill="#ffffff"
      opacity={stagger(activeAmt, i) * (0.75 + 0.25 * hot)} />;
  });

  return (
    <svg width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ overflow: "visible", display: "block" }}>
      <defs>
        <pattern id={`cells-${idKey}`} width={pitch} height={pitch} patternUnits="userSpaceOnUse">
          <rect x={off} y={off} width={cell} height={cell} rx={r} fill={C.cellDim} />
        </pattern>
        <filter id={`bloom-${idKey}`} x="-20%" y="-20%" width="140%" height="140%">
          <feGaussianBlur stdDeviation={pitch * 0.9} />
        </filter>
      </defs>
      {showGround ? (
        <>
          <rect width={width} height={height} fill={`url(#cells-${idKey})`} />
          {bloom > 0 ? <g filter={`url(#bloom-${idKey})`} opacity={bloom}>{painRects}</g> : null}
          {painRects}
        </>
      ) : null}
      {showActive ? (
        <>
          {bloom + hot > 0 ? (
            <g filter={`url(#bloom-${idKey})`} opacity={Math.min(1, 0.4 * bloom + 0.9 * hot)}>{hotRects}</g>
          ) : null}
          {activeRects}
          {hotRects}
        </>
      ) : null}
    </svg>
  );
};

export const gridHeight = (width: number) => (width / COLS) * ROWS;
