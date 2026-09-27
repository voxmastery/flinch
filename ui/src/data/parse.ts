// Defensive parsing of daemon payloads. External data is never trusted blindly.
import type {
  Decision,
  DecisionKind,
  Gate,
  HealEvent,
  HurtEvent,
  JudgmentStatus,
  PainSource,
  Scar,
  Snapshot,
  Stance,
  StreamEvent,
} from "../types";

type Obj = Record<string, unknown>;

export const DEFAULT_CELLS = 4000;
export const DEFAULT_GRID = { cols: 80, rows: 50 };
export const DEFAULT_THRESHOLDS = { flinch: 0.55, wary: 0.25 };

function isObj(v: unknown): v is Obj {
  return typeof v === "object" && v !== null && !Array.isArray(v);
}

function num(v: unknown, fallback = 0): number {
  return typeof v === "number" && Number.isFinite(v) ? v : fallback;
}

function str(v: unknown, fallback = ""): string {
  return typeof v === "string" ? v : fallback;
}

function oneOf<T extends string>(v: unknown, allowed: readonly T[], fallback: T): T {
  return typeof v === "string" && (allowed as readonly string[]).includes(v) ? (v as T) : fallback;
}

function numArray(v: unknown): number[] {
  return Array.isArray(v) ? v.filter((x): x is number => typeof x === "number" && Number.isFinite(x)) : [];
}

function cellIndices(v: unknown, cells: number): number[] {
  return numArray(v).filter((i) => Number.isInteger(i) && i >= 0 && i < cells);
}

function weights(v: unknown, cells: number): number[] {
  const arr = numArray(v).map((w) => Math.min(1, Math.max(0, w)));
  return arr.length >= cells ? arr.slice(0, cells) : [...arr, ...new Array<number>(cells - arr.length).fill(0)];
}

const DECISIONS: readonly DecisionKind[] = ["allow", "deny", "ask", "pass"];
const GATES: readonly Gate[] = ["scar", "reflex", "judgment", "none"];
const STANCES: readonly Stance[] = ["calm", "wary", "flinch"];
const JUDGMENT: readonly JudgmentStatus[] = ["ok", "unavailable", "disabled"];
const SOURCES: readonly PainSource[] = ["manual", "user_report", "tool_failure", "regression"];

export function parseDecision(v: unknown, cells = DEFAULT_CELLS): Decision | null {
  if (!isObj(v)) return null;
  return {
    id: str(v.id, `d-${num(v.ts)}-${Math.random().toString(36).slice(2, 8)}`),
    project: str(v.project),
    ts: num(v.ts, Date.now() / 1000),
    session: str(v.session),
    tool: str(v.tool, "?"),
    action: str(v.action),
    decision: oneOf(v.decision, DECISIONS, "pass"),
    gate: oneOf(v.gate, GATES, "none"),
    state: oneOf(v.state, STANCES, "calm"),
    avoid: Math.min(1, Math.max(0, num(v.avoid))),
    active: cellIndices(v.active, cells),
    latency_ms: num(v.latency_ms),
    reason: typeof v.reason === "string" ? v.reason : null,
  };
}

export function parseScar(v: unknown): Scar | null {
  if (!isObj(v) || typeof v.pain_id !== "string") return null;
  return {
    pain_id: v.pain_id,
    fingerprint: str(v.fingerprint),
    normalized: str(v.normalized),
    reason: str(v.reason),
    severity: num(v.severity),
    created_at: str(v.created_at),
    max_weight: typeof v.max_weight === "number" ? v.max_weight : undefined,
  };
}

export function parseSnapshot(v: unknown): Snapshot {
  if (!isObj(v)) throw new Error("state payload is not an object");
  const cells = num(v.cells, DEFAULT_CELLS);
  const grid = isObj(v.grid) ? { cols: num(v.grid.cols, 80), rows: num(v.grid.rows, 50) } : DEFAULT_GRID;
  const th = isObj(v.thresholds)
    ? { flinch: num(v.thresholds.flinch, 0.55), wary: num(v.thresholds.wary, 0.25) }
    : DEFAULT_THRESHOLDS;
  const scars = Array.isArray(v.scars) ? v.scars.map(parseScar).filter((s): s is Scar => s !== null) : [];
  const decisions = Array.isArray(v.decisions)
    ? v.decisions.map((d) => parseDecision(d, cells)).filter((d): d is Decision => d !== null)
    : [];
  return {
    project: typeof v.project === "string" && v.project !== "" ? v.project : null,
    thresholds: th,
    cells,
    grid,
    weights: weights(v.weights, cells),
    scars,
    decisions,
    // Wire key for the judgment-layer status, as defined by the daemon contract.
    judgment: oneOf(v.judgment, JUDGMENT, "unavailable"),
  };
}

function parseHeal(v: Obj, cells: number): HealEvent {
  return { ts: num(v.ts, Date.now() / 1000), project: str(v.project), pain_id: str(v.pain_id), action: str(v.action), weights: weights(v.weights, cells) };
}

function parseHurt(v: Obj, cells: number): HurtEvent {
  return {
    ...parseHeal(v, cells),
    reason: str(v.reason),
    severity: num(v.severity),
    source: oneOf(v.source, SOURCES, "manual"),
    active: cellIndices(v.active, cells),
  };
}

/** Parse one named SSE event. Returns null for unknown or malformed events. */
export function parseStreamEvent(type: string, raw: unknown, cells = DEFAULT_CELLS): StreamEvent | null {
  if (!isObj(raw)) return null;
  switch (type) {
    case "decision": {
      const d = parseDecision(raw, cells);
      return d ? { type, data: d } : null;
    }
    case "hurt":
      return { type, data: parseHurt(raw, cells) };
    case "heal":
    case "forgive":
      return { type, data: parseHeal(raw, cells) };
    case "weights":
      return { type, data: { weights: weights(raw.weights, cells) } };
    default:
      return null;
  }
}
