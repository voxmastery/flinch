import { memo, useState } from "react";
import type { Decision, Gate } from "../types";
import { clock } from "./format";

const GATE_LABEL: Record<Gate, string> = {
  scar: "scar",
  reflex: "reflex",
  judgment: "danger sense",
  none: "none",
};

interface FeedRowProps {
  d: Decision;
  fresh: boolean;
}

function FeedRowImpl({ d, fresh }: FeedRowProps) {
  const [open, setOpen] = useState(false);
  const hasReason = Boolean(d.reason);
  return (
    <li className={`feed-row dec-${d.decision}${fresh ? " fresh" : ""}`}>
      <div className="feed-main">
        <span className="feed-time mono">{clock(d.ts)}</span>
        <span className="feed-tool">{d.tool}</span>
        <span className={`badge badge-${d.decision}`}>{d.decision}</span>
      </div>
      <div className="feed-action mono" title={d.action}>
        {d.action}
      </div>
      <div className="feed-meta mono">
        <span title="gate">{GATE_LABEL[d.gate]}</span>
        <span title="avoid score" className={`feed-avoid st-${d.state}`}>
          avoid {d.avoid.toFixed(2)}
        </span>
        <span title="latency">{d.latency_ms.toFixed(0)} ms</span>
        {hasReason && (
          <button type="button" className="feed-why" aria-expanded={open} onClick={() => setOpen((o) => !o)}>
            {open ? "hide" : "why"}
          </button>
        )}
      </div>
      {open && hasReason && <div className="feed-reason">{d.reason}</div>}
    </li>
  );
}

export const FeedRow = memo(FeedRowImpl);
