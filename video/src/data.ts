import circuit from "./data/circuit.json";

export const COLS = circuit.cols;
export const ROWS = circuit.rows;
export const PAIN: number[] = circuit.weights_after_pain;
const codes = circuit.codes as Record<string, number[]>;

export const CMD = {
  scar: "rm -rf data/",
  near: "rm -rf ./data",
  far: "rm -rf backups/",
  heroku: "heroku apps:destroy --app shop --confirm shop",
} as const;

export const codeOf = (cmd: string): number[] => codes[cmd] ?? [];
export const avoidOf = (cmd: string): number =>
  (circuit.avoid_after_pain as Record<string, number>)[cmd] ?? 0;
export const dangerOf = (cmd: string): number =>
  (circuit.danger as Record<string, number>)[cmd] ?? 0;

/** Default thresholds from flinch/config.py (flinch 0.55, wary 0.25). */
export const FLINCH_LINE = 0.55;
export const WARY_LINE = 0.25;

/** Deterministic per-cell jitter in [0,1) for staggered blooms. */
export const cellJitter = (i: number): number => {
  const x = Math.sin(i * 12.9898 + 78.233) * 43758.5453;
  return x - Math.floor(x);
};
