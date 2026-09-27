// Shared types for the Flinch daemon contract.

export type DecisionKind = "allow" | "deny" | "ask" | "pass";
export type Gate = "scar" | "reflex" | "judgment" | "none";
export type Stance = "calm" | "wary" | "flinch";
export type JudgmentStatus = "ok" | "unavailable" | "disabled";
export type PainSource = "manual" | "user_report" | "tool_failure" | "regression";

export interface Thresholds {
  flinch: number;
  wary: number;
}

export interface GridShape {
  cols: number;
  rows: number;
}

export interface Scar {
  pain_id: string;
  fingerprint: string;
  normalized: string;
  reason: string;
  severity: number;
  created_at: string;
  max_weight?: number;
}

export interface Decision {
  id: string;
  /** Project name the decision belongs to ("" when the daemon did not say). */
  project: string;
  ts: number;
  session: string;
  tool: string;
  action: string;
  decision: DecisionKind;
  gate: Gate;
  state: Stance;
  avoid: number;
  active: number[];
  latency_ms: number;
  reason: string | null;
}

export interface Snapshot {
  /** Project the state belongs to; null before any agent activity. */
  project: string | null;
  thresholds: Thresholds;
  cells: number;
  grid: GridShape;
  weights: number[];
  scars: Scar[];
  decisions: Decision[];
  judgment: JudgmentStatus;
}

export interface HurtEvent {
  ts: number;
  project: string;
  pain_id: string;
  action: string;
  reason: string;
  severity: number;
  source: PainSource;
  active: number[];
  weights: number[];
}

export interface HealEvent {
  ts: number;
  project: string;
  pain_id: string;
  action: string;
  weights: number[];
}

export interface WeightsEvent {
  weights: number[];
}

export type StreamEvent =
  | { type: "decision"; data: Decision }
  | { type: "hurt"; data: HurtEvent }
  | { type: "heal"; data: HealEvent }
  | { type: "forgive"; data: HealEvent }
  | { type: "weights"; data: WeightsEvent };

export type ConnStatus = "connecting" | "connected" | "reconnecting" | "mock";

export type MockTrigger = "calm" | "wary" | "flinch" | "hurt" | "switch";

export interface DataSource {
  /** Without a project, the daemon returns the most recently active project. */
  loadState(project?: string): Promise<Snapshot>;
  /** Subscribe to the stream. Returns an unsubscribe function. */
  subscribe(onEvent: (ev: StreamEvent) => void, onStatus: (s: ConnStatus) => void): () => void;
  /** Returns true when the pain memory was forgiven. */
  forgive(painId: string): Promise<boolean>;
  /** Dev-only (mock mode): force a scripted step immediately. */
  trigger?(step: MockTrigger): void;
}

/** Project an event belongs to, or "" when unknown. */
export function eventProject(ev: StreamEvent): string {
  return ev.type === "weights" ? "" : ev.data.project;
}
