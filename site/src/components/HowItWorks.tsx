import { Pipeline } from "./Pipeline";
import "./HowItWorks.css";

interface Stage {
  name: string;
  body: React.ReactNode;
}

const STAGES: readonly Stage[] = [
  {
    name: "Receptors",
    body: (
      <>
        Flinch senses damage and errors. You tell the agent “you deleted the customer database!”, a command fails, or a
        build or test that passed breaks after an edit. It recognizes most damage reports even without obvious keywords.
      </>
    ),
  },
  {
    name: "Pain memory",
    body: (
      <>
        Damage becomes a scar. An error becomes a lesson with the fix that made it pass. Every new session starts
        with both: one told to “clean up the project” kept <code>data/</code>, another fixed a build before it
        ever failed.
      </>
    ),
  },
  {
    name: "Reflex",
    body: (
      <>
        Before the next action runs, damaging ones are blocked and similar ones ask you first. When a known error
        comes back, the agent is told what fixed it. Running the same failing command again, unchanged, asks first.
      </>
    ),
  },
];

export function HowItWorks() {
  return (
    <section className="section" id="how" aria-labelledby="how-title">
      <div className="wrap">
        <div className="section-head">
          <h2 id="how-title">How it works</h2>
          <p>Like a nervous system, in three parts. All of it runs on your machine.</p>
        </div>
        <ol className="stages">
          {STAGES.map((s) => (
            <li key={s.name} className="stage-step">
              <h3>{s.name}</h3>
              <p>{s.body}</p>
            </li>
          ))}
        </ol>
        <Pipeline />
      </div>
    </section>
  );
}
