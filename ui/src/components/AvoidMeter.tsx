import type { Decision, Thresholds } from "../types";
import "./AvoidMeter.css";

interface AvoidMeterProps {
  latest: Decision | null;
  thresholds: Thresholds;
}

function level(avoid: number, t: Thresholds): "calm" | "wary" | "flinch" {
  if (avoid >= t.flinch) return "flinch";
  if (avoid >= t.wary) return "wary";
  return "calm";
}

export function AvoidMeter({ latest, thresholds }: AvoidMeterProps) {
  const avoid = Math.min(1, Math.max(0, latest?.avoid ?? 0));
  // Width follows the same rounding as the label, so "0.07" draws exactly 7%.
  const shown = Math.round(avoid * 100) / 100;
  const pct = `${Math.round(avoid * 100)}%`;
  return (
    <div className={`avoid avoid-${level(avoid, thresholds)}`}>
      <span className="avoid-label">avoid</span>
      <div
        className="avoid-track"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={avoid}
        aria-label="avoid score of the latest action"
      >
        <div className="avoid-fill" style={{ width: pct }} />
        <div className="avoid-tick" style={{ left: `${thresholds.wary * 100}%` }} title={`wary ≥ ${thresholds.wary}`}>
          <span>wary</span>
        </div>
        <div className="avoid-tick" style={{ left: `${thresholds.flinch * 100}%` }} title={`flinch ≥ ${thresholds.flinch}`}>
          <span>flinch</span>
        </div>
      </div>
      <span className="avoid-value mono">{shown.toFixed(2)}</span>
    </div>
  );
}
