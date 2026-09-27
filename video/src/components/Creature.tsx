import React from "react";
import { useCurrentFrame } from "remotion";
import { C } from "../theme";
import { poseAt, type Cue, type Mood } from "./creatureMotion";

const BODY =
  "M200 78 C 286 74, 346 132, 350 206 C 354 276, 292 318, 200 320 C 108 322, 50 280, 50 206 C 50 134, 114 82, 200 78 Z";

const MOUTH: Record<Mood, string> = {
  calm: "M182 244 Q200 258 218 244",
  healing: "M178 242 Q200 262 222 242",
  wary: "M184 250 Q200 246 216 250",
  flinch: "M188 248 Q200 234 212 248 Q200 262 188 248 Z",
  hurt: "M176 252 Q184 243 192 251 Q200 259 208 251 Q216 243 224 252",
  mending: "M184 252 Q200 244 216 252",
  scarred: "M184 252 Q200 246 216 252",
  forgiven: "M178 242 Q200 262 222 242",
};

const Eye: React.FC<{ cx: number; scaleY: number; shut: boolean }> = ({ cx, scaleY, shut }) => {
  const dir = cx < 200 ? 1 : -1;
  const tip = cx + dir * 14;
  const back = cx - dir * 12;
  if (shut) {
    return (
      <path d={`M${back} 184 L${tip} 196 L${back} 208`} fill="none" stroke={C.ink}
        strokeWidth={7} strokeLinecap="round" strokeLinejoin="round" />
    );
  }
  return (
    <g transform={`translate(${cx} 196) scale(1 ${scaleY}) translate(${-cx} -196)`}>
      <ellipse cx={cx} cy={196} rx={15} ry={21} fill={C.ink} />
      <circle cx={cx + 5} cy={188} r={5} fill="#fff" opacity={0.9} />
    </g>
  );
};

interface Props { cues: Cue[]; size: number; frameOffset?: number }

/** The Flinch creature. Every pixel is a pure function of the current frame. */
export const Creature: React.FC<Props> = ({ cues, size, frameOffset = 0 }) => {
  const frame = useCurrentFrame() + frameOffset;
  const p = poseAt(frame, cues);
  const mouthKey: Mood = p.mood === "flinch" && !p.eyesShut ? "wary" : p.mood;
  const idSuffix = Math.round(size);
  const bSx = 1 + 0.018 * p.breath;
  const bSy = 1 - 0.018 * p.breath;
  const fig = `translate(${p.tx} ${p.ty}) translate(200 320) rotate(${p.rot}) scale(${p.sx} ${p.sy}) translate(-200 -320)`;
  const breath = `translate(200 320) scale(${bSx} ${bSy}) translate(-200 -320)`;
  const halo = `translate(200 200) scale(${p.haloScale}) translate(-200 -200)`;

  return (
    <svg width={size} height={size * 0.9} viewBox="0 0 400 360" style={{ overflow: "visible" }}>
      <defs>
        <radialGradient id={`sheen-${idSuffix}`} cx="0.35" cy="0.28" r="0.75">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.55" />
          <stop offset="0.45" stopColor="#ffffff" stopOpacity="0.08" />
          <stop offset="1" stopColor="#000000" stopOpacity="0.22" />
        </radialGradient>
        <filter id={`blur-${idSuffix}`} x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="22" />
        </filter>
      </defs>
      <ellipse cx="200" cy="338" rx={120 * (1 + 0.03 * p.breath)} ry="12" fill="#000" opacity={0.45} />
      <g transform={fig}>
        <g transform={breath}>
          <ellipse cx="200" cy="200" rx="165" ry="135" fill={p.halo} opacity={p.haloOpacity}
            filter={`url(#blur-${idSuffix})`} transform={halo} />
          <g transform={`rotate(${p.sprout} 206 84)`}>
            <path d="M206 82 C 206 56, 222 40, 242 38" fill="none" stroke={p.body} strokeWidth={9} strokeLinecap="round" />
            <circle cx="244" cy="38" r="8" fill={p.body} />
          </g>
          <path d={BODY} fill={p.body} />
          <path d={BODY} fill={`url(#sheen-${idSuffix})`} />
          <g opacity={p.crack > 0 ? 1 : 0}>
            <path d="M272 104 L258 134 L276 156 L254 186 L266 210" fill="none" stroke="#5a0f1c" strokeWidth={5}
              strokeLinecap="round" strokeLinejoin="round" strokeDasharray={160} strokeDashoffset={160 * (1 - p.crack)} />
            <path d="M276 156 L298 166" fill="none" stroke="#5a0f1c" strokeWidth={5} strokeLinecap="round"
              opacity={p.crack} />
          </g>
          <ellipse cx="118" cy="236" rx="20" ry="10" fill="#ff8fa3" opacity={p.cheek} />
          <ellipse cx="282" cy="236" rx="20" ry="10" fill="#ff8fa3" opacity={p.cheek} />
          <Eye cx={150} scaleY={p.eyeScaleY} shut={p.eyesShut} />
          <Eye cx={250} scaleY={p.eyeScaleY} shut={p.eyesShut} />
          <path d={MOUTH[mouthKey]} fill={mouthKey === "flinch" ? C.ink : "none"} stroke={C.ink} strokeWidth={6}
            strokeLinecap="round" strokeLinejoin="round" />
        </g>
      </g>
    </svg>
  );
};
