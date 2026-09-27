import "./Prompts.css";

const COMMAND = "git push --force origin main";
const REASON =
  "Flinch: this action looks destructive and hard to undo (force push or remote delete). Confirm only if it is intended.";

function ClaudeCodePrompt() {
  return (
    <figure className="prompt">
      <div className="mock mock-cc" role="img" aria-label={`Claude Code permission prompt for ${COMMAND}. ${REASON} Do you want to proceed?`}>
        <div className="cc-box">
          <p className="cc-head">Bash command</p>
          <p className="cc-cmd mono">{COMMAND}</p>
          <p className="cc-reason">{REASON}</p>
          <p className="cc-ask">Do you want to proceed?</p>
          <ul className="cc-opts mono">
            <li className="is-sel">
              <span aria-hidden="true">❯</span> 1. Yes
            </li>
            <li>
              <span aria-hidden="true"> </span> 2. No
            </li>
          </ul>
        </div>
      </div>
      <figcaption>Claude Code</figcaption>
    </figure>
  );
}

function CursorPrompt() {
  return (
    <figure className="prompt">
      <div className="mock mock-cursor" role="img" aria-label={`Cursor approval for ${COMMAND}. Run this command? Hook requested approval: ${REASON}`}>
        <p className="cu-cmd mono">
          <span aria-hidden="true">$</span> {COMMAND}
        </p>
        <div className="cu-body">
          <p className="cu-q">Run this command?</p>
          <p className="cu-reason">
            Hook requested approval: Flinch: this action looks destructive and hard to undo …
          </p>
          <ul className="cc-opts mono" aria-hidden="true">
            <li className="is-sel">
              <span>→</span> Run (once) (y)
            </li>
            <li>
              <span> </span> Run Everything (shift+tab)
            </li>
            <li>
              <span> </span> Skip &amp; tell the agent what to do instead (esc or n)
            </li>
          </ul>
        </div>
      </div>
      <figcaption>Cursor (cursor-agent)</figcaption>
    </figure>
  );
}

export function Prompts() {
  return (
    <section className="section" id="prompts" aria-labelledby="prompts-title">
      <div className="wrap">
        <div className="section-head">
          <h2 id="prompts-title">It asks in the tools you already use</h2>
          <p>
            Flinch’s built-in danger sense asks before destructive commands, even ones that never caused damage here.
            It works fully offline. This is the real prompt text for <code>{COMMAND}</code>.
          </p>
        </div>
        <div className="prompts">
          <ClaudeCodePrompt />
          <CursorPrompt />
        </div>
      </div>
    </section>
  );
}
