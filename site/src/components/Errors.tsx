import "./Errors.css";

interface Beat {
  who: string;
  text: React.ReactNode;
  tone?: "error" | "flinch" | "ok";
}

const FIRST: readonly Beat[] = [
  { who: "agent", text: <code>scripts/build.sh</code> },
  { who: "shell", text: "Error: config/app.json not found", tone: "error" },
  { who: "agent", text: <code>cp config/app.example.json config/app.json &amp;&amp; sh scripts/build.sh</code> },
  { who: "shell", text: "build ok", tone: "ok" },
  { who: "Flinch", text: "Stored the fix for this error.", tone: "flinch" },
];

const SECOND: readonly Beat[] = [
  {
    who: "Flinch",
    tone: "flinch",
    text: (
      <>
        <code>scripts/build.sh</code> failed with “Error: config/app.json not found”; it passed after{" "}
        <code>cp config/app.example.json config/app.json</code>.
      </>
    ),
  },
  { who: "agent", text: <code>cp config/app.example.json config/app.json &amp;&amp; bash scripts/build.sh</code> },
  { who: "shell", text: "build ok", tone: "ok" },
];

function Session({ title, beats }: { title: string; beats: readonly Beat[] }) {
  return (
    <figure className="err-session">
      <figcaption>{title}</figcaption>
      <ol className="err-beats">
        {beats.map((b, i) => (
          <li key={i} className={b.tone ? `is-${b.tone}` : undefined}>
            <span className="err-who">{b.who}</span>
            <span className="err-text">{b.text}</span>
          </li>
        ))}
      </ol>
    </figure>
  );
}

export function Errors() {
  return (
    <section className="section" id="errors" aria-labelledby="errors-title">
      <div className="wrap">
        <div className="section-head">
          <h2 id="errors-title">Errors teach it too</h2>
          <p>
            Not every mistake deletes something. When a command fails and later passes, Flinch keeps what fixed it.
            The next time that error shows up, in any session or tool, the agent is told the fix right away.
          </p>
        </div>
        <div className="err-sessions">
          <Session title="First chat: the build fails, the agent fixes it" beats={FIRST} />
          <Session title="A later, brand-new chat: the config is missing again" beats={SECOND} />
        </div>
        <p className="err-note">
          Recorded live in Cursor. In the second chat the agent read the lesson at the start and fixed the build before
          it ever failed.
        </p>
        <dl className="err-list">
          <div>
            <dt>Known errors come back with their fix</dt>
            <dd>Matched on the error itself, even when the agent runs the command differently or pipes it through <code>tail</code>.</dd>
          </div>
          <div>
            <dt>Stuck loops get noticed</dt>
            <dd>The same failing command run again with nothing changed is flagged, and the third try asks you first.</dd>
          </div>
          <div>
            <dt>Broken builds name the edit</dt>
            <dd>A test, build, lint or typecheck that passed and now fails says which edits came in between.</dd>
          </div>
        </dl>
        <div className="err-why">
          <h3>Why not just permission rules?</h3>
          <p>
            Claude Code and Cursor already let you write rules and approve commands. Those are rules you write in
            advance. Flinch writes its own from what actually went wrong in your project, applies them to similar
            actions, and remembers them across sessions and tools.
          </p>
        </div>
      </div>
    </section>
  );
}
