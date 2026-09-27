import type { Decision } from "../types";
import { FeedRow } from "./FeedRow";
import "./Feed.css";

interface FeedProps {
  items: Decision[];
  /** True when the daemon has no project activity yet. */
  idle: boolean;
}

export function Feed({ items, idle }: FeedProps) {
  return (
    <section className="panel feed" aria-label="live feed">
      <header className="panel-head">
        <h2>live feed</h2>
        <span className="panel-count mono">{items.length}</span>
      </header>
      {items.length === 0 ? (
        <p className="empty">
          {idle
            ? "Waiting for the first agent action. Decisions stream in here as your agent works."
            : "No actions yet. Decisions stream in here as your agent works."}
        </p>
      ) : (
        <ol className="feed-list">
          {items.map((d, i) => (
            <FeedRow key={d.id} d={d} fresh={i === 0} />
          ))}
        </ol>
      )}
    </section>
  );
}
