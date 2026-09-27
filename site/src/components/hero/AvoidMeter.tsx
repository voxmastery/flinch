import { THRESHOLDS } from "../../data/reflex";

export type Level = "calm" | "wary" | "flinch";

export function levelOf(avoid: number): Level {
  if (avoid >= THRESHOLDS.flinch) return "flinch";
  if (avoid >= THRESHOLDS.wary) return "wary";
  return "calm";
}

interface AvoidMeterProps {
  value: number | null;
}

export function AvoidMeter({ value }: AvoidMeterProps) {
  const v = value ?? 0;
  const level = value === null ? "idle" : levelOf(v);
  return (
    <div className={`meter meter-${level}`}>
      <span className="meter-label">avoid</span>
      <div
        className="meter-track"
        role="meter"
        aria-valuemin={0}
        aria-valuemax={1}
        aria-valuenow={v}
        aria-label="Avoid score for the current command"
      >
        <div className="meter-fill" style={{ transform: `scaleX(${v})` }} />
        <span className="meter-tick" style={{ left: `${THRESHOLDS.wary * 100}%` }}>
          <span>wary {THRESHOLDS.wary}</span>
        </span>
        <span className="meter-tick" style={{ left: `${THRESHOLDS.flinch * 100}%` }}>
          <span>flinch {THRESHOLDS.flinch}</span>
        </span>
      </div>
      <span className="meter-value mono">{value === null ? "--" : v.toFixed(2)}</span>
    </div>
  );
}
