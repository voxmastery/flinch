import { useState, type CSSProperties } from "react";
import type { Scar } from "../types";
import { shortDate } from "./format";
import "./Scars.css";

interface ScarsProps {
  scars: Scar[];
  onForgive: (painId: string) => Promise<void>;
}

function ScarItem({ scar, onForgive }: { scar: Scar; onForgive: (id: string) => Promise<void> }) {
  const [busy, setBusy] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const forgive = async () => {
    setBusy(true);
    setError(null);
    try {
      await onForgive(scar.pain_id);
    } catch (err) {
      setError(err instanceof Error ? err.message : "could not forgive");
      setBusy(false);
    }
  };

  const sev = Math.max(0, Math.min(1, scar.severity));
  return (
    <li className="scar">
      <div className="scar-top">
        <span className="scar-sev" style={{ "--sev": sev } as CSSProperties} title={`severity ${scar.severity}`}>
          {scar.severity.toFixed(2)}
        </span>
        <span className="scar-date">{shortDate(scar.created_at)}</span>
        <button type="button" className="scar-forgive" disabled={busy} onClick={forgive}>
          {busy ? "…" : "forgive"}
        </button>
      </div>
      <div className="scar-action mono" title={scar.normalized}>
        {scar.normalized}
      </div>
      {scar.reason && <div className="scar-reason">{scar.reason}</div>}
      {error && <div className="scar-error" role="alert">{error}</div>}
    </li>
  );
}

export function Scars({ scars, onForgive }: ScarsProps) {
  const sorted = [...scars].sort((a, b) => b.created_at.localeCompare(a.created_at));
  return (
    <section className="panel scars" aria-label="scars and pain memories">
      <header className="panel-head">
        <h2>scars &amp; pain memory</h2>
        <span className="panel-count mono">{scars.length}</span>
      </header>
      {sorted.length === 0 ? (
        <p className="empty">No scars. Nothing has hurt yet.</p>
      ) : (
        <ul className="scar-list">
          {sorted.map((s) => (
            <ScarItem key={s.pain_id} scar={s} onForgive={onForgive} />
          ))}
        </ul>
      )}
    </section>
  );
}
