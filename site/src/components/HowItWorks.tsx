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
        Flinch senses damage. You tell the agent “you deleted the customer database!”, a test that passed before an
        edit fails after it, or you run <code>flinch hurt "reason"</code>. It recognizes most reports even without obvious keywords.
      </>
    ),
  },
  {
    name: "Pain memory",
    body: (
      <>
        The action that caused it becomes a scar, and a lesson every new session starts with. A new session told to
        “clean up the project” kept <code>data/</code> because of it.
      </>
    ),
  },
  {
    name: "Reflex",
    body: (
      <>
        Before the next action runs, the same action is blocked, similar ones are blocked or ask you first, and
        destructive commands it has never seen ask you first.
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
