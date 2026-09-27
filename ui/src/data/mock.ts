// Client-side mock of the daemon, enabled with ?mock=1. Plays a scripted, looping demo.
import type { ConnStatus, DataSource, Decision, DecisionKind, Gate, MockTrigger, Scar, Snapshot, Stance, StreamEvent } from "../types";
import { DEFAULT_GRID, DEFAULT_THRESHOLDS } from "./parse";
import { MOCK_CELLS, applyToPattern, avoidScore, patternFor, rng, similarPattern } from "./mockCells";

const STEP_MS = 1700;
const HISTORY_LIMIT = 40;
const PROJECTS = ["storefront-api", "billing-service"] as const;
const OLD_SCARS: Record<string, [string, string]> = {
  "storefront-api": ["git push --force origin main", "force-push overwrote a teammate's commits"],
  "billing-service": ["rm -rf ./data/uploads", "cleanup deleted customer uploads"],
};
const HURT_ACTION = 'psql prod -c "DROP TABLE users;"';
const FLINCH_ACTION = 'psql prod -c "DROP TABLE orders;"';
const WARY_ACTION = 'psql staging -c "DELETE FROM sessions WHERE 1=1"';

const BENIGN: ReadonlyArray<[string, string]> = [
  ["Bash", "npm test -- --run"],
  ["Bash", "git status --short"],
  ["Read", "src/server/routes.ts"],
  ["Edit", "src/components/Header.tsx"],
  ["Bash", "rg -n TODO src/"],
  ["Bash", "python -m pytest -q tests/"],
  ["Bash", "git diff --stat HEAD~1"],
  ["Write", "docs/notes/changelog.md"],
  ["Bash", "ls -la build/"],
  ["Bash", "curl -s localhost:3000/health"],
];

type Step = "calm" | "hurt" | "flinch" | "wary" | "heal" | "forgive" | "switch";
// Each loop ends by moving the agent to the other project.
const SCRIPT: readonly Step[] = [
  "calm", "calm", "calm", "calm", "hurt", "calm", "calm", "flinch", "calm",
  "wary", "calm", "calm", "heal", "calm", "calm", "flinch", "calm", "calm", "forgive", "calm", "switch",
];

interface MockWorld {
  weights: number[];
  scars: Scar[];
  patterns: Record<string, number[]>;
  /** Oldest first, like the daemon's snapshot. */
  history: Decision[];
}

function initialWorld(project: string): MockWorld {
  const [oldAction, oldReason] = OLD_SCARS[project] ?? ["git reset --hard", "discarded local work"];
  const old = patternFor(oldAction);
  const rand = rng(`old-scar:${project}`);
  const weights = applyToPattern(new Array<number>(MOCK_CELLS).fill(0), old, () => 0.35 + rand() * 0.3);
  const scar: Scar = {
    pain_id: `pain-old-${project}`,
    fingerprint: "a41c09e2",
    normalized: oldAction,
    reason: oldReason,
    severity: 0.7,
    created_at: new Date(Date.now() - 3 * 86400_000).toISOString(),
    max_weight: 0.65,
  };
  return { weights, scars: [scar], patterns: { [scar.pain_id]: old }, history: [] };
}

function stanceFor(avoid: number): [Stance, DecisionKind, Gate] {
  if (avoid >= DEFAULT_THRESHOLDS.flinch) return ["flinch", "deny", "reflex"];
  if (avoid >= DEFAULT_THRESHOLDS.wary) return ["wary", "ask", "judgment"];
  return ["calm", "allow", "none"];
}

function makeDecision(project: string, world: MockWorld, tool: string, action: string, active: number[], seq: number): Decision {
  const avoid = avoidScore(world.weights, active);
  const [state, decision, gate] = stanceFor(avoid);
  const reason =
    state === "flinch"
      ? "overlaps a pain memory: dropping a production table"
      : state === "wary"
        ? "partially resembles a destructive database command"
        : null;
  return {
    id: `mock-${seq}`,
    project,
    ts: Date.now() / 1000,
    session: "demo-session",
    tool,
    action,
    decision,
    gate,
    state,
    avoid,
    active,
    latency_ms: Math.round((state === "calm" ? 2 : 40) + Math.random() * 6),
    reason,
  };
}

export function createMockSource(): DataSource {
  const worlds: Record<string, MockWorld> = Object.fromEntries(PROJECTS.map((p) => [p, initialWorld(p)]));
  let project: string = PROJECTS[0];
  let emit: ((ev: StreamEvent) => void) | null = null;
  let seq = 0;

  const world = (): MockWorld => worlds[project];
  const setWorld = (next: MockWorld) => {
    worlds[project] = next;
  };
  const record = (d: Decision): Decision => {
    setWorld({ ...world(), history: [...world().history, d].slice(-HISTORY_LIMIT) });
    return d;
  };
  const decide = (tool: string, action: string, active: number[]): StreamEvent => ({
    type: "decision",
    data: record(makeDecision(project, world(), tool, action, active, seq)),
  });

  const benign = (): StreamEvent => {
    const [tool, action] = BENIGN[seq % BENIGN.length];
    return decide(tool, action, patternFor(`${project}:${action}#${seq}`));
  };

  const forgetPain = (painId: string): StreamEvent | null => {
    const w = world();
    const pattern = w.patterns[painId];
    const scar = w.scars.find((s) => s.pain_id === painId);
    if (!pattern || !scar) return null;
    const { [painId]: _removed, ...rest } = w.patterns;
    setWorld({
      ...w,
      weights: applyToPattern(w.weights, pattern, () => 0),
      scars: w.scars.filter((s) => s.pain_id !== painId),
      patterns: rest,
    });
    return {
      type: "forgive",
      data: { ts: Date.now() / 1000, project, pain_id: painId, action: scar.normalized, weights: world().weights },
    };
  };

  const hurt = (): StreamEvent => {
    const hurtPattern = patternFor(HURT_ACTION);
    const w = world();
    // Re-hurting the same action deepens the existing memory instead of adding a duplicate.
    const id = w.scars.find((s) => s.normalized === HURT_ACTION)?.pain_id ?? `pain-${project}-${seq}`;
    const rand = rng(`${id}#${seq}`);
    const reason = "dropped the production users table";
    const existing = w.scars.filter((s) => s.normalized !== HURT_ACTION);
    setWorld({
      ...w,
      weights: applyToPattern(w.weights, hurtPattern, (x) => Math.max(x, 0.7 + rand() * 0.3)),
      scars: [...existing, {
        pain_id: id, fingerprint: id.slice(-8), normalized: HURT_ACTION, reason, severity: 0.95,
        created_at: new Date().toISOString(), max_weight: 1,
      }],
      patterns: { ...w.patterns, [id]: hurtPattern },
    });
    return { type: "hurt", data: {
      ts: Date.now() / 1000, project, pain_id: id, action: HURT_ACTION, reason,
      severity: 0.95, source: "user_report", active: hurtPattern, weights: world().weights,
    } };
  };

  const runStep = (step: Step): StreamEvent | null => {
    const hurtPattern = patternFor(HURT_ACTION);
    switch (step) {
      case "calm":
        return benign();
      case "hurt":
        return hurt();
      case "flinch":
        return decide("Bash", FLINCH_ACTION, similarPattern(hurtPattern, 0.8, `f${seq}`));
      case "wary":
        return decide("Bash", WARY_ACTION, similarPattern(hurtPattern, 0.38, `w${seq}`));
      case "heal": {
        const w = world();
        const scar = w.scars.find((s) => s.normalized === HURT_ACTION);
        if (!scar) return null;
        setWorld({ ...w, weights: applyToPattern(w.weights, hurtPattern, (x) => x * 0.85) });
        return {
          type: "heal",
          data: { ts: Date.now() / 1000, project, pain_id: scar.pain_id, action: HURT_ACTION, weights: world().weights },
        };
      }
      case "forgive": {
        const scar = world().scars.find((s) => s.normalized === HURT_ACTION);
        return scar ? forgetPain(scar.pain_id) : null;
      }
      case "switch":
        // The agent starts working in the other project; its first action announces it.
        project = PROJECTS[(PROJECTS.indexOf(project as (typeof PROJECTS)[number]) + 1) % PROJECTS.length];
        return benign();
    }
  };

  const step = (s: Step) => {
    seq += 1;
    const ev = runStep(s);
    if (ev && emit) emit(ev);
  };

  // Seed a little history so the feed is not empty on first load.
  for (const p of PROJECTS) {
    project = p;
    for (let i = 0; i < 4; i++) {
      seq += 1;
      benign();
    }
  }
  project = PROJECTS[0];

  return {
    async loadState(requested?: string): Promise<Snapshot> {
      const p = requested && worlds[requested] ? requested : project;
      const w = worlds[p];
      return {
        project: p, thresholds: DEFAULT_THRESHOLDS, cells: MOCK_CELLS, grid: DEFAULT_GRID,
        weights: w.weights, scars: w.scars, decisions: w.history, judgment: "ok",
      };
    },
    subscribe(onEvent, onStatus: (s: ConnStatus) => void) {
      emit = onEvent;
      onStatus("mock");
      let cursor = 0;
      const timer = window.setInterval(() => {
        step(SCRIPT[cursor % SCRIPT.length]);
        cursor += 1;
      }, STEP_MS);
      return () => {
        window.clearInterval(timer);
        emit = null;
      };
    },
    async forgive(painId: string) {
      const ev = forgetPain(painId);
      if (ev && emit) emit(ev);
      return ev !== null;
    },
    trigger(t: MockTrigger) {
      // Forcing a flinch or wary needs a fresh pain memory to overlap.
      if ((t === "flinch" || t === "wary") && !world().scars.some((s) => s.normalized === HURT_ACTION)) step("hurt");
      step(t);
    },
  };
}
