// Live data source: talks to the local daemon over HTTP + Server-Sent Events.
import type { ConnStatus, DataSource, Snapshot, StreamEvent } from "../types";
import { parseSnapshot, parseStreamEvent } from "./parse";

const EVENT_NAMES = ["decision", "hurt", "heal", "forgive", "weights"] as const;
const BACKOFF_START_MS = 1000;
const BACKOFF_MAX_MS = 15000;

async function loadState(project?: string): Promise<Snapshot> {
  const url = project ? `/api/state?project=${encodeURIComponent(project)}` : "/api/state";
  const res = await fetch(url, { headers: { accept: "application/json" } });
  if (!res.ok) throw new Error(`GET /api/state failed: ${res.status}`);
  return parseSnapshot(await res.json());
}

async function forgive(painId: string): Promise<boolean> {
  const res = await fetch("/api/forgive", {
    method: "POST",
    headers: { "content-type": "application/json" },
    body: JSON.stringify({ id: painId }),
  });
  if (res.status === 404) return false;
  if (!res.ok) throw new Error(`POST /api/forgive failed: ${res.status}`);
  return true;
}

function subscribe(onEvent: (ev: StreamEvent) => void, onStatus: (s: ConnStatus) => void): () => void {
  let source: EventSource | null = null;
  let timer: number | undefined;
  let delay = BACKOFF_START_MS;
  let closed = false;

  const handle = (name: string) => (msg: MessageEvent<string>) => {
    try {
      const ev = parseStreamEvent(name, JSON.parse(msg.data));
      if (ev) onEvent(ev);
    } catch (err) {
      console.warn(`flinch: dropped malformed "${name}" event`, err);
    }
  };

  const connect = () => {
    if (closed) return;
    const es = new EventSource("/events");
    source = es;
    es.onopen = () => {
      delay = BACKOFF_START_MS;
      onStatus("connected");
    };
    es.onerror = () => {
      // Manage reconnection ourselves so we can apply exponential backoff.
      es.close();
      if (closed) return;
      onStatus("reconnecting");
      timer = window.setTimeout(connect, delay);
      delay = Math.min(delay * 2, BACKOFF_MAX_MS);
    };
    for (const name of EVENT_NAMES) es.addEventListener(name, handle(name));
  };

  onStatus("connecting");
  connect();

  return () => {
    closed = true;
    window.clearTimeout(timer);
    source?.close();
  };
}

export const liveSource: DataSource = { loadState, subscribe, forgive };
