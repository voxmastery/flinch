import { useEffect, useState } from "react";
import { BEATS } from "../../data/reflex";

const TYPE_MS = 55;
const THINK_MS = 320;
const HOLD_MS = 3200;
const CLEAR_MS = 650;
/** Beat shown as a still frame (reduced motion): a similar command lighting the scar's cells. */
export const STILL_BEAT = 1;

export interface StageState {
  index: number;
  typed: number;
  revealed: boolean;
}

function prefersReducedMotion(): boolean {
  return typeof window !== "undefined" && window.matchMedia("(prefers-reduced-motion: reduce)").matches;
}

export function useReducedMotion(): boolean {
  const [reduced, setReduced] = useState(prefersReducedMotion);
  useEffect(() => {
    const mq = window.matchMedia("(prefers-reduced-motion: reduce)");
    const on = () => setReduced(mq.matches);
    mq.addEventListener("change", on);
    return () => mq.removeEventListener("change", on);
  }, []);
  return reduced;
}

function fullFrame(index: number): StageState {
  return { index, typed: BEATS[index].command.length, revealed: true };
}

/** Drives the hero loop: type a command, reveal the verdict, hold, clear, next. */
export function useStageLoop(running: boolean, reduced: boolean) {
  const [state, setState] = useState<StageState>(() => (reduced ? fullFrame(STILL_BEAT) : { index: 0, typed: 0, revealed: false }));

  useEffect(() => {
    if (!running || reduced) return;
    const { index, typed, revealed } = state;
    const cmd = BEATS[index].command;
    let next: StageState;
    let wait: number;
    if (revealed) {
      next = { index: (index + 1) % BEATS.length, typed: 0, revealed: false };
      wait = HOLD_MS;
    } else if (typed < cmd.length) {
      next = { index, typed: typed + 1, revealed: false };
      wait = typed === 0 ? CLEAR_MS : TYPE_MS;
    } else {
      next = { index, typed, revealed: true };
      wait = THINK_MS;
    }
    const id = window.setTimeout(() => setState(next), wait);
    return () => window.clearTimeout(id);
  }, [state, running, reduced]);

  const show = (index: number) => setState(fullFrame(index));
  return { state, show };
}
