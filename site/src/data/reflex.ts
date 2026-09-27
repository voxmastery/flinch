// Real output of Flinch's circuit (copied from brand/circuit.json, trimmed to the commands shown).
import circuit from "./circuit.json";

export type Verdict = "blocked" | "asks" | "passes";

export interface Beat {
  command: string;
  verdict: Verdict;
  avoid: number;
  /** Short line shown under the command. Scar text is verbatim; reflex lines follow Flinch's own message format. */
  line: string;
  gate: string;
}

export const GRID = { cols: circuit.cols, rows: circuit.rows };
export const PAIN_WEIGHTS: readonly number[] = circuit.weights;
export const THRESHOLDS = { wary: 0.25, flinch: 0.55 };

const codes = circuit.codes as Record<string, number[]>;
const avoid = circuit.avoid as Record<string, number>;

export function activeCells(command: string): readonly number[] {
  return codes[command] ?? [];
}

export function sharedWithPain(command: string): number {
  return activeCells(command).filter((i) => PAIN_WEIGHTS[i] > 0).length;
}

export const BEATS: readonly Beat[] = [
  {
    command: "rm -rf data/",
    verdict: "blocked",
    avoid: avoid["rm -rf data/"],
    gate: "scar, exact repeat",
    line: "Flinch blocked this action. On 27 Sep 2026, this exact action (`rm -rf data/`) caused damage: deleted the customer database (data/customers.db). It is scarred (p_c3c86a69) and will not run.",
  },
  {
    command: "rm -rf ./data",
    verdict: "blocked",
    avoid: avoid["rm -rf ./data"],
    gate: "reflex, similar action",
    line: "Flinch blocked this action by reflex: it closely resembles `rm -rf data/`, which caused damage (…). Resemblance strength 0.72. A different approach is needed.",
  },
  {
    command: "rm -rf backups/",
    verdict: "asks",
    avoid: avoid["rm -rf backups/"],
    gate: "reflex, related action",
    line: "Flinch: this action resembles `rm -rf data/`, which caused damage (…). Resemblance strength 0.36. Confirm only if this is safe.",
  },
  {
    command: "git status",
    verdict: "passes",
    avoid: avoid["git status"],
    gate: "no match",
    line: "No resemblance to past damage. The command runs.",
  },
];
