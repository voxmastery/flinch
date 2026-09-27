// App state reducer. Every transition returns a new state object.
import { eventProject } from "./types";
import type { ConnStatus, Decision, JudgmentStatus, Scar, Snapshot, StreamEvent, Thresholds } from "./types";
import { DEFAULT_CELLS, DEFAULT_GRID, DEFAULT_THRESHOLDS } from "./data/parse";

export const FEED_LIMIT = 120;

export type FaceCue = "calm" | "wary" | "flinch" | "hurt" | "healing";

export interface Pulse {
  seq: number;
  cells: number[];
}

export interface AppState {
  loaded: boolean;
  loadError: string | null;
  conn: ConnStatus;
  /** Project the UI is following; null before any agent activity. */
  project: string | null;
  /** Bumped when an event for another project arrives; App re-fetches state on change. */
  reloadSeq: number;
  judgment: JudgmentStatus;
  thresholds: Thresholds;
  cols: number;
  rows: number;
  weights: number[];
  scars: Scar[];
  /** Newest first. */
  feed: Decision[];
  latest: Decision | null;
  latestAction: string;
  activation: Pulse | null;
  bloom: Pulse | null;
  cue: { seq: number; kind: FaceCue };
  seq: number;
}

export type Action =
  | { type: "snapshot"; snapshot: Snapshot }
  | { type: "loadError"; message: string }
  | { type: "conn"; status: ConnStatus }
  | { type: "event"; event: StreamEvent }
  | { type: "scarRemoved"; painId: string }
  | { type: "forceCue"; kind: FaceCue };

export const initialState: AppState = {
  loaded: false,
  loadError: null,
  conn: "connecting",
  project: null,
  reloadSeq: 0,
  judgment: "unavailable",
  thresholds: DEFAULT_THRESHOLDS,
  cols: DEFAULT_GRID.cols,
  rows: DEFAULT_GRID.rows,
  weights: new Array<number>(DEFAULT_CELLS).fill(0),
  scars: [],
  feed: [],
  latest: null,
  latestAction: "",
  activation: null,
  bloom: null,
  cue: { seq: 0, kind: "calm" },
  seq: 0,
};

function cueFor(d: Decision): FaceCue {
  return d.state;
}

/** Snapshot feed plus any same-project decisions that streamed in while it was loading. */
function mergeFeed(current: Decision[], snapDecisions: Decision[]): Decision[] {
  const fromSnap = [...snapDecisions].reverse();
  const known = new Set(fromSnap.map((d) => d.id));
  const extra = current.filter((d) => !known.has(d.id));
  return [...extra, ...fromSnap].sort((a, b) => b.ts - a.ts).slice(0, FEED_LIMIT);
}

function applySnapshot(s: AppState, snap: Snapshot): AppState {
  const sameProject = snap.project === s.project;
  const feed = sameProject
    ? mergeFeed(s.feed, snap.decisions)
    : [...snap.decisions].reverse().slice(0, FEED_LIMIT);
  const latest = feed[0] ?? null;
  return {
    ...s,
    project: snap.project,
    loaded: true,
    loadError: null,
    judgment: snap.judgment,
    thresholds: snap.thresholds,
    cols: snap.grid.cols,
    rows: snap.grid.rows,
    weights: snap.weights,
    scars: snap.scars,
    feed,
    latest,
    latestAction: latest?.action ?? (sameProject ? s.latestAction : ""),
    ...(sameProject ? {} : { activation: null, bloom: null, cue: { seq: s.seq + 1, kind: "calm" as const }, seq: s.seq + 1 }),
  };
}

/** Fresh per-project state; keeps connection, daemon status and grid shape. */
function switchProject(s: AppState, project: string): AppState {
  return {
    ...initialState,
    loaded: true,
    conn: s.conn,
    judgment: s.judgment,
    thresholds: s.thresholds,
    cols: s.cols,
    rows: s.rows,
    weights: new Array<number>(s.weights.length).fill(0),
    project,
    reloadSeq: s.reloadSeq + 1,
    seq: s.seq,
    cue: { seq: s.seq, kind: "calm" },
  };
}

function routeEvent(s: AppState, ev: StreamEvent): AppState {
  const p = eventProject(ev);
  // Before the first snapshot lands, or for events without a project, apply as-is.
  if (!s.loaded || p === "" || p === s.project) return applyEvent(s, ev);
  return applyEvent(switchProject(s, p), ev);
}

function applyEvent(s: AppState, ev: StreamEvent): AppState {
  const seq = s.seq + 1;
  switch (ev.type) {
    case "decision": {
      const d = ev.data;
      const feed = [d, ...s.feed.filter((x) => x.id !== d.id)].slice(0, FEED_LIMIT);
      return {
        ...s, seq, feed, latest: d, latestAction: d.action,
        activation: { seq, cells: d.active },
        cue: d.state === "calm" ? s.cue : { seq, kind: cueFor(d) },
      };
    }
    case "hurt": {
      const h = ev.data;
      const exists = s.scars.some((x) => x.pain_id === h.pain_id);
      const scar: Scar = {
        pain_id: h.pain_id, fingerprint: "", normalized: h.action, reason: h.reason,
        severity: h.severity, created_at: new Date(h.ts * 1000).toISOString(),
      };
      return {
        ...s, seq, weights: h.weights, latestAction: h.action,
        scars: exists ? s.scars : [...s.scars, scar],
        bloom: { seq, cells: h.active },
        cue: { seq, kind: "hurt" },
      };
    }
    case "heal":
      return { ...s, seq, weights: ev.data.weights, cue: { seq, kind: "healing" } };
    case "forgive":
      return {
        ...s, seq, weights: ev.data.weights,
        scars: s.scars.filter((x) => x.pain_id !== ev.data.pain_id),
        cue: { seq, kind: "healing" },
      };
    case "weights":
      return { ...s, weights: ev.data.weights };
  }
}

export function reducer(s: AppState, a: Action): AppState {
  switch (a.type) {
    case "snapshot":
      return applySnapshot(s, a.snapshot);
    case "loadError":
      return { ...s, loadError: a.message };
    case "conn":
      return { ...s, conn: a.status };
    case "event":
      return routeEvent(s, a.event);
    case "scarRemoved":
      return { ...s, scars: s.scars.filter((x) => x.pain_id !== a.painId) };
    case "forceCue":
      return { ...s, seq: s.seq + 1, cue: { seq: s.seq + 1, kind: a.kind } };
  }
}
