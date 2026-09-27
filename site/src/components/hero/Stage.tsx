import { useEffect, useRef, useState } from "react";
import { BEATS, sharedWithPain, type Verdict } from "../../data/reflex";
import { AvoidMeter } from "./AvoidMeter";
import { Creature, type Mood } from "./Creature";
import { ReflexCanvas } from "./ReflexCanvas";
import { STILL_BEAT, useReducedMotion, useStageLoop } from "./useStageLoop";
import { InlineCode } from "../InlineCode";
import "./Stage.css";

const MOOD: Record<Verdict, Mood> = { blocked: "flinch", asks: "wary", passes: "calm" };
const LABEL: Record<Verdict, string> = { blocked: "Blocked", asks: "Asks you first", passes: "Runs" };

function useOnScreen(ref: React.RefObject<HTMLElement | null>): boolean {
  const [visible, setVisible] = useState(true);
  useEffect(() => {
    const el = ref.current;
    if (!el) return;
    const io = new IntersectionObserver(([entry]) => setVisible(entry.isIntersecting), { threshold: 0.1 });
    io.observe(el);
    return () => io.disconnect();
  }, [ref]);
  return visible;
}

export function Stage() {
  const rootRef = useRef<HTMLDivElement>(null);
  const reduced = useReducedMotion();
  const onScreen = useOnScreen(rootRef);
  const [paused, setPaused] = useState(false);
  const { state, show } = useStageLoop(onScreen && !paused, reduced);

  const frame = reduced && !paused && !state.revealed ? { index: STILL_BEAT, typed: 99, revealed: true } : state;
  const beat = BEATS[frame.index];
  const typed = beat.command.slice(0, frame.typed);
  const mood: Mood = frame.revealed ? MOOD[beat.verdict] : "calm";
  const still = reduced || paused;

  const pick = (i: number) => {
    setPaused(true);
    show(i);
  };

  return (
    <div
      ref={rootRef}
      role="figure"
      aria-label="Live loop: an agent types four commands. Flinch blocks rm -rf data/ and rm -rf ./data, asks before rm -rf backups/, and lets git status run. Behind it, the reflex grid lights each command's cells over the red pain memory."
      className={`stage verdict-${frame.revealed ? beat.verdict : "none"}${still ? " is-paused" : ""}`}
    >
      <div className="stage-visual">
      <div className="stage-grid">
        <ReflexCanvas command={frame.revealed ? beat.command : null} instant={reduced} />
      </div>

      <div className="stage-term" aria-live={paused ? "polite" : "off"} aria-atomic="true">
        <div className="term-line mono">
          <span className="term-prompt" aria-hidden="true">agent $</span>
          <span className="term-cmd">{typed}</span>
          {!frame.revealed && <span className="term-caret" aria-hidden="true" />}
        </div>
        <p className={`term-verdict${frame.revealed ? " is-on" : ""}`}>
          {frame.revealed && (
            <>
              <strong>{LABEL[beat.verdict]}</strong> <span className="term-gate">by {beat.gate}.</span>{" "}
              <span className="term-msg">
                <InlineCode text={beat.line} />
              </span>
            </>
          )}
        </p>
      </div>

      <div className="stage-creature">
        <Creature mood={mood} beat={frame.index} />
      </div>
      </div>

      <div className="stage-foot">
        <AvoidMeter value={frame.revealed ? beat.avoid : null} />
        <p className="stage-shared">
          {frame.revealed ? (
            <>
              <strong>{sharedWithPain(beat.command)}</strong> of 200 active cells overlap the pain memory
            </>
          ) : (
            "Red cells: pain memory from rm -rf data/"
          )}
        </p>
        <div className="stage-controls">
          <button type="button" className="stage-btn" onClick={() => setPaused((p) => !p)} aria-pressed={paused}>
            {paused ? "Play loop" : "Pause loop"}
          </button>
          <div className="stage-picks" role="group" aria-label="Show a command">
            {BEATS.map((b, i) => (
              <button
                key={b.command}
                type="button"
                className="stage-pick mono"
                aria-current={frame.index === i && frame.revealed ? "true" : undefined}
                onClick={() => pick(i)}
              >
                {b.command}
              </button>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
