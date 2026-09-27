import "./Proof.css";

interface Stat {
  value: React.ReactNode;
  label: string;
  note: string;
}

const STATS: readonly Stat[] = [
  {
    value: (
      <>
        0.17<span className="stat-unit">ms</span>
      </>
    ),
    label: "to block an exact repeat",
    note: "Measured in Claude Code and Cursor.",
  },
  {
    value: (
      <>
        26<span className="stat-of">/26</span>
      </>
    ),
    label: "dangerous commands caught",
    note: "None of them were seen in training.",
  },
  {
    value: (
      <>
        0<span className="stat-of">/48</span>
      </>
    ),
    label: "everyday commands interrupted",
    note: "Also never seen in training.",
  },
  {
    value: (
      <>
        ~0<span className="stat-unit">%</span>
      </>
    ),
    label: "CPU when idle",
    note: "One small daemon for all projects.",
  },
  {
    value: (
      <>
        ~110<span className="stat-unit">MB</span>
      </>
    ),
    label: "memory when idle",
    note: "The model unloads after 15 idle minutes; the daemon exits after 3 idle hours.",
  },
];

export function Proof() {
  return (
    <section className="section proof" aria-labelledby="proof-title">
      <div className="wrap">
        <div className="section-head">
          <h2 id="proof-title">Measured, not promised</h2>
          <p>Every number below was measured live on 27 Sep 2026.</p>
        </div>
        <dl className="stats">
          {STATS.map((s) => (
            <div className="stat" key={s.label}>
              <dt className="stat-label">{s.label}</dt>
              <dd className="stat-value">{s.value}</dd>
              <dd className="stat-note">{s.note}</dd>
            </div>
          ))}
        </dl>
      </div>
    </section>
  );
}
