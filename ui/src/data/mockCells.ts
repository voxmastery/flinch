// Deterministic cell-pattern helpers used by the mock stream.

export const MOCK_CELLS = 4000;
export const ACTIVE_PER_ACTION = 200;

function hashString(s: string): number {
  let h = 2166136261;
  for (let i = 0; i < s.length; i++) {
    h ^= s.charCodeAt(i);
    h = Math.imul(h, 16777619);
  }
  return h >>> 0;
}

/** Small seeded PRNG (mulberry32). */
export function rng(seed: string): () => number {
  let a = hashString(seed);
  return () => {
    a = (a + 0x6d2b79f5) >>> 0;
    let t = a;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function fill(start: number[], seed: string, count: number): number[] {
  const rand = rng(seed);
  const picked = new Set(start);
  while (picked.size < count) picked.add(Math.floor(rand() * MOCK_CELLS));
  return [...picked];
}

/** The 200 active cells an action "lights up". Same action, same cells. */
export function patternFor(action: string): number[] {
  return fill([], action, ACTIVE_PER_ACTION);
}

/** A pattern sharing `overlap` (0..1) of its cells with `base`. */
export function similarPattern(base: number[], overlap: number, seed: string): number[] {
  const keep = base.slice(0, Math.round(base.length * overlap));
  return fill(keep, seed, ACTIVE_PER_ACTION);
}

/** Mean pain over the active cells, lightly amplified, clamped to 0..1. */
export function avoidScore(weights: readonly number[], active: readonly number[]): number {
  if (active.length === 0) return 0;
  const sum = active.reduce((acc, i) => acc + (weights[i] ?? 0), 0);
  return Math.min(1, (sum / active.length) * 1.15);
}

/** Returns a new weight array with the pattern's cells set by `fn`. */
export function applyToPattern(
  weights: readonly number[],
  pattern: readonly number[],
  fn: (old: number, i: number) => number,
): number[] {
  const next = [...weights];
  pattern.forEach((cell, i) => {
    next[cell] = Math.min(1, Math.max(0, fn(next[cell] ?? 0, i)));
  });
  return next;
}
