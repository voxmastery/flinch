import { interpolate, interpolateColors } from "remotion";
import { C } from "../theme";

export type Mood = "calm" | "wary" | "flinch" | "hurt" | "mending" | "healing" | "scarred" | "forgiven";
export interface Cue { at: number; mood: Mood }

const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
export const RECOIL_FRAMES = 18; // ~600 ms at 30 fps
const BLINK_EVERY = 120;
const BLINK_LEN = 5;

export interface Pose {
  mood: Mood;
  tx: number; ty: number; rot: number; sx: number; sy: number;
  body: string; halo: string; haloOpacity: number; haloScale: number;
  eyeScaleY: number; eyesShut: boolean; sprout: number; cheek: number;
  crack: number; breath: number;
}

export function activeCue(frame: number, cues: Cue[]): { mood: Mood; since: number } {
  let cur: Cue = { at: 0, mood: "calm" };
  for (const c of cues) if (c.at <= frame) cur = c;
  return { mood: cur.mood, since: frame - cur.at };
}

// Recoil keyframes adapted from Face.css @keyframes recoil (percent -> frames).
const RK = [0, 0.12, 0.24, 0.36, 0.48, 0.62, 0.8, 1].map((p) => p * RECOIL_FRAMES);
const recoil = (f: number) => ({
  tx: interpolate(f, RK, [0, -10, 12, -9, 7, -4, 2, 6], CLAMP),
  ty: interpolate(f, RK, [0, 16, 10, 8, 4, 2, -2, -6], CLAMP),
  sx: interpolate(f, RK, [1, 0.84, 0.88, 0.9, 0.93, 0.96, 0.98, 0.97], CLAMP),
  sy: interpolate(f, RK, [1, 0.8, 0.88, 0.9, 0.93, 0.96, 0.98, 0.97], CLAMP),
  rot: interpolate(f, [RK[6], RK[7]], [0, -5], CLAMP),
});

const WK = [0, 0.15, 0.35, 0.6, 1].map((p) => p * 21);
const wince = (f: number) => ({
  tx: interpolate(f, WK, [0, -6, 5, -2, 0], CLAMP),
  ty: interpolate(f, WK, [0, 8, 4, 2, 2], CLAMP),
  rot: interpolate(f, WK, [0, 4, -3, 1, 0], CLAMP),
  sx: interpolate(f, WK, [1, 0.9, 0.95, 0.97, 0.98], CLAMP),
  sy: interpolate(f, WK, [1, 0.86, 0.95, 0.97, 0.98], CLAMP),
});

const HURT_BODY = "#f08a86";
const WARY_BODY = "#a6cfc6";
const FLINCH_BODY = "#d9e6e2";

export function poseAt(frame: number, cues: Cue[]): Pose {
  const { mood, since } = activeCue(frame, cues);
  const breath = Math.sin((frame / (5 * 30)) * Math.PI * 2);
  const blinking = frame % BLINK_EVERY < BLINK_LEN && (mood === "calm" || mood === "healing");
  const base: Pose = {
    mood, tx: 0, ty: 0, rot: 0, sx: 1, sy: 1,
    body: C.calm, halo: C.calm, haloOpacity: 0.18, haloScale: 1,
    eyeScaleY: blinking ? 0.08 : 1, eyesShut: false, sprout: 0, cheek: 0.35,
    crack: 0, breath,
  };
  const ease = (n: number) => interpolate(since, [0, n], [0, 1], CLAMP);

  if (mood === "wary") {
    const k = ease(12);
    return { ...base, tx: 6 * k, ty: -6 * k, rot: -5 * k, sx: 1 - 0.03 * k, sy: 1 - 0.03 * k,
      body: interpolateColors(k, [0, 1], [C.calm, WARY_BODY]), halo: C.wary, haloOpacity: 0.18 + 0.1 * k,
      eyeScaleY: 1 - 0.58 * k, sprout: -28 * k, cheek: 0.35 * (1 - k) };
  }
  if (mood === "flinch") {
    const r = recoil(since);
    const shut = since < RECOIL_FRAMES + 6;
    const settle = interpolate(since, [RECOIL_FRAMES + 6, RECOIL_FRAMES + 30], [0, 1], CLAMP);
    return { ...base, ...r,
      body: interpolateColors(settle, [0, 1], [FLINCH_BODY, WARY_BODY]),
      halo: C.pain, haloOpacity: interpolate(since, [0, 3, 60], [0.2, 0.55, 0.3], CLAMP),
      haloScale: interpolate(since, [0, 4, 18], [1, 1.12, 1.02], CLAMP),
      eyesShut: shut, eyeScaleY: shut ? 1 : 0.42, sprout: shut ? 22 : -28, cheek: 0 };
  }
  if (mood === "hurt") {
    const k = ease(8);
    return { ...base, ...wince(since),
      body: interpolateColors(k, [0, 1], [C.calm, HURT_BODY]), halo: C.pain, haloOpacity: 0.18 + 0.24 * k,
      eyesShut: true, sprout: -60 * k, cheek: 0, crack: interpolate(since, [2, 12], [0, 1], CLAMP) };
  }
  if (mood === "mending") {
    const k = interpolate(since, [0, 150], [1, 0], CLAMP);
    return { ...base, ty: 2 * k,
      body: interpolateColors(k, [0, 1], [C.calm, HURT_BODY]),
      halo: interpolateColors(k, [0, 1], [C.calm, C.pain]), haloOpacity: 0.18 + 0.15 * k,
      eyeScaleY: 0.7 + 0.3 * (1 - k), sprout: -20 * k, cheek: 0.35 * (1 - k), crack: k };
  }
  if (mood === "scarred") {
    return { ...base, body: interpolateColors(0.35, [0, 1], [C.calm, HURT_BODY]), halo: C.pain, haloOpacity: 0.16,
      eyeScaleY: 0.8, sprout: -18, cheek: 0.1, crack: 1 };
  }
  if (mood === "forgiven") {
    const k = interpolate(since, [0, 45], [1, 0], CLAMP);
    const g = interpolate(since, [0, 20, 70], [0, 1, 0.25], CLAMP);
    return { ...base, body: interpolateColors(0.35 * k, [0, 1], [C.calm, HURT_BODY]),
      halo: "#9fffe4", haloOpacity: 0.18 + 0.45 * g, haloScale: 1 + 0.1 * g,
      eyeScaleY: blinking ? 0.08 : 0.8 + 0.2 * (1 - k), sprout: -18 * k, cheek: 0.1 + 0.5 * (1 - k), crack: k };
  }
  if (mood === "healing") {
    const g = interpolate(since, [0, 22, 54], [0, 1, 0], CLAMP);
    return { ...base, halo: "#9fffe4", haloOpacity: 0.18 + 0.42 * g, haloScale: 1 + 0.08 * g, cheek: 0.6 };
  }
  return base;
}
