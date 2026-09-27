import { useEffect, useState } from "react";
import type { FaceCue } from "../store";

export type Mood = "calm" | "wary" | "flinch" | "hurt" | "mending" | "healing";

/** Each cue plays a timed sequence of moods, then settles back to calm. */
const SEQUENCES: Record<FaceCue, ReadonlyArray<[Mood, number]>> = {
  calm: [],
  wary: [["wary", 3000]],
  flinch: [["flinch", 600], ["wary", 3000]],
  hurt: [["hurt", 1200], ["mending", 4000]],
  healing: [["healing", 1800]],
};

export function useFaceMood(cue: { seq: number; kind: FaceCue }): Mood {
  const [mood, setMood] = useState<Mood>("calm");

  useEffect(() => {
    const steps = SEQUENCES[cue.kind];
    const timers: number[] = [];
    let at = 0;
    steps.forEach(([m, ms]) => {
      timers.push(window.setTimeout(() => setMood(m), at));
      at += ms;
    });
    timers.push(window.setTimeout(() => setMood("calm"), at));
    return () => timers.forEach((t) => window.clearTimeout(t));
  }, [cue.seq, cue.kind]);

  return mood;
}

export const MOOD_CAPTION: Record<Mood, string> = {
  calm: "calm",
  wary: "wary",
  flinch: "flinch!",
  hurt: "hurt",
  mending: "healing",
  healing: "healing",
};
