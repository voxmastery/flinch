import { useCallback, useEffect, useMemo, useReducer, useRef } from "react";
import type { ConnStatus, DataSource, MockTrigger } from "./types";
import { liveSource } from "./data/live";
import { createMockSource } from "./data/mock";
import { initialState, reducer, type Action } from "./store";
import { Header } from "./components/Header";
import { Face } from "./components/Face";
import { Feed } from "./components/Feed";
import { ReflexGrid } from "./components/ReflexGrid";
import { AvoidMeter } from "./components/AvoidMeter";
import { Scars } from "./components/Scars";

function pickSource(): DataSource {
  const params = new URLSearchParams(window.location.search);
  return params.get("mock") === "1" ? createMockSource() : liveSource;
}

const MOCK_KEYS: Record<string, MockTrigger> = { c: "calm", w: "wary", f: "flinch", h: "hurt", p: "switch" };

/** Dev-only: in mock mode, c/w/f/h/p force calm/wary/flinch/hurt/project switch. */
function useMockKeys(source: DataSource, dispatch: (a: Action) => void): void {
  useEffect(() => {
    const trigger = source.trigger?.bind(source);
    if (!trigger) return;
    const onKey = (e: KeyboardEvent) => {
      if (e.ctrlKey || e.metaKey || e.altKey || e.repeat) return;
      const step = MOCK_KEYS[e.key.toLowerCase()];
      if (!step) return;
      trigger(step);
      if (step === "calm") dispatch({ type: "forceCue", kind: "calm" });
    };
    window.addEventListener("keydown", onKey);
    return () => window.removeEventListener("keydown", onKey);
  }, [source, dispatch]);
}

function message(err: unknown): string {
  return err instanceof Error ? err.message : "unexpected error";
}

export function App() {
  const source = useMemo(pickSource, []);
  const [state, dispatch] = useReducer(reducer, initialState);
  const prevConn = useRef<ConnStatus>("connecting");
  const loadTicket = useRef(0);

  // No project param: the daemon answers with the most recently active project.
  const load = useCallback(async () => {
    const ticket = ++loadTicket.current;
    try {
      const snapshot = await source.loadState();
      if (ticket === loadTicket.current) dispatch({ type: "snapshot", snapshot });
    } catch (err) {
      console.error("flinch: failed to load state", err);
      if (ticket === loadTicket.current) dispatch({ type: "loadError", message: message(err) });
    }
  }, [source]);

  // An event for another project reset the view; pull that project's full state.
  useEffect(() => {
    if (state.reloadSeq > 0) void load();
  }, [state.reloadSeq, load]);

  useMockKeys(source, dispatch);

  useEffect(() => {
    void load();
    return source.subscribe(
      (event) => dispatch({ type: "event", event }),
      (status) => {
        // Resync after a reconnect so nothing missed while offline is lost.
        if (status === "connected" && prevConn.current === "reconnecting") void load();
        prevConn.current = status;
        dispatch({ type: "conn", status });
      },
    );
  }, [source, load]);

  const forgive = useCallback(
    async (painId: string) => {
      const ok = await source.forgive(painId);
      if (!ok) throw new Error("pain memory not found");
      dispatch({ type: "scarRemoved", painId });
    },
    [source],
  );

  return (
    <div className="app">
      <Header
        conn={state.conn}
        judgment={state.judgment}
        loadError={state.loadError}
        project={state.project}
        loaded={state.loaded}
      />
      <main className="layout">
        <Scars scars={state.scars} onForgive={forgive} />
        <section className="center" aria-label="flinch">
          <div className="face-area">
            <Face cue={state.cue} action={state.latestAction} />
          </div>
          <div className="panel grid-panel">
            <header className="panel-head">
              <h2>reflex grid — 4,000 cells, 5% active per action</h2>
              <span className="legend">
                <i className="sw sw-active" /> active <i className="sw sw-pain" /> pain <i className="sw sw-hot" /> overlap
              </span>
            </header>
            <ReflexGrid
              key={state.project ?? "no-project"}
              cols={state.cols}
              rows={state.rows}
              weights={state.weights}
              activation={state.activation}
              bloom={state.bloom}
            />
            <AvoidMeter latest={state.latest} thresholds={state.thresholds} />
          </div>
        </section>
        <Feed items={state.feed} idle={state.loaded && state.project === null} />
      </main>
    </div>
  );
}
