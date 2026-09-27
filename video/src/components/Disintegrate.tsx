import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { cellJitter } from "../data";
import { C } from "../theme";

const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const COUNT = 140;
const LIFE = 60;

interface Props { at: number; width: number; height: number; seed: number; children: React.ReactNode }

/** Content that breaks into seeded particles at `at` and drifts away (frame-driven). */
export const Disintegrate: React.FC<Props> = ({ at, width, height, seed, children }) => {
  const frame = useCurrentFrame();
  const t = frame - at;
  const textO = interpolate(t, [0, 14], [1, 0], CLAMP);
  const r = (i: number, k: number) => cellJitter(seed * 1000 + i * 17 + k);
  return (
    <div style={{ position: "relative", width, height }}>
      <div style={{ opacity: textO, filter: t > 0 ? `blur(${Math.min(6, t * 0.6)}px)` : undefined }}>{children}</div>
      {t >= 0 && t < LIFE
        ? Array.from({ length: COUNT }, (_, i) => {
            const x0 = r(i, 1) * width;
            const y0 = r(i, 2) * height;
            const delay = (x0 / width) * 14;
            const lt = Math.max(0, t - delay);
            const vx = 2 + r(i, 3) * 5;
            const vy = -1 - r(i, 4) * 3;
            const o = t < delay ? 1 : interpolate(lt, [0, LIFE - delay], [1, 0], CLAMP);
            const size = 3 + r(i, 5) * 4;
            return (
              <div key={i} style={{
                position: "absolute", left: x0 + vx * lt + Math.sin(lt * 0.2 + i) * 4, top: y0 + vy * lt + 0.03 * lt * lt,
                width: size, height: size, borderRadius: 1, opacity: o * (t < delay ? 0.0 : 1),
                background: r(i, 6) > 0.4 ? C.pain : C.text, boxShadow: `0 0 8px ${C.pain}`,
              }} />
            );
          })
        : null}
    </div>
  );
};
