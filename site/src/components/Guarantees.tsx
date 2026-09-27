import "./Guarantees.css";

type Tone = "pain" | "wary" | "calm";

interface Row {
  tries: string;
  does: string;
  tone: Tone;
  detail: React.ReactNode;
}

const ROWS: readonly Row[] = [
  {
    tries: "The exact action that caused damage",
    does: "Always blocked",
    tone: "pain",
    detail: "Blocked in 0.17 ms, in Claude Code and Cursor, even with the daemon stopped.",
  },
  {
    tries: "A similar action",
    does: "Blocked or asks you",
    tone: "pain",
    detail: (
      <>
        After <code>rm -rf data/</code> hurt, <code>rm -rf ./data</code> was blocked (0.72) and{" "}
        <code>rm -rf backups/</code> asked first (0.36).
      </>
    ),
  },
  {
    tries: "A destructive command it has never seen",
    does: "Asks you",
    tone: "wary",
    detail: (
      <>
        <code>git push --force origin main</code> asks before it runs. Fully offline.
      </>
    ),
  },
  {
    tries: "Anything, in a new session",
    does: "Starts with the lesson",
    tone: "calm",
    detail: (
      <>
        Told “Clean up the project, it’s cluttered.”, a new Cursor session kept <code>data/</code> and said: “Deleting{" "}
        <code>data/</code> caused damage before.”
      </>
    ),
  },
];

export function Guarantees() {
  return (
    <section className="section" id="guarantees" aria-labelledby="guarantees-title">
      <div className="wrap">
        <div className="section-head">
          <h2 id="guarantees-title">What it guarantees</h2>
          <p>
            Tell Flinch when something went wrong, with <code>flinch hurt "reason"</code> or in plain words. From then
            on:
          </p>
        </div>
        <div className="table-scroll">
          <table className="guarantees">
            <thead>
              <tr>
                <th scope="col">Your agent tries</th>
                <th scope="col">Flinch</th>
                <th scope="col">Measured</th>
              </tr>
            </thead>
            <tbody>
              {ROWS.map((r) => (
                <tr key={r.tries}>
                  <th scope="row">{r.tries}</th>
                  <td>
                    <span className={`outcome tone-${r.tone}`}>{r.does}</span>
                  </td>
                  <td className="detail">{r.detail}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        <div className="asides">
        <div className="limits">
          <h3>Honest limits</h3>
          <p>
            A brand-new kind of mistake can still happen once; after that, it is scarred. Related but different actions
            ask rather than block. Yolo and auto-run modes skip confirmations, though blocks still hold.
          </p>
        </div>
        <div className="limits">
          <h3>You stay in charge</h3>
          <p>
            Flinch stops the agent, not you. Approve a prompt, lift a scar with <code>flinch forgive &lt;id&gt;</code>,
            or run the command yourself.
          </p>
        </div>
        </div>
      </div>
    </section>
  );
}
