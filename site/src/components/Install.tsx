import { useRef, useState, type KeyboardEvent } from "react";
import { CopyButton } from "./CopyButton";
import "./Install.css";

interface Cmd {
  line: string;
  note?: string;
}

interface Tab {
  id: string;
  name: string;
  intro: string;
  cmds: readonly Cmd[];
}

const INSTALL_FLINCH: Cmd = { line: "uv tool install flinch-agent", note: "or: pipx install flinch-agent" };

const TABS: readonly Tab[] = [
  {
    id: "claude-code",
    name: "Claude Code",
    intro: "Add the plugin. It sets itself up in the background on the first session.",
    cmds: [
      { line: "claude plugin marketplace add voxmastery/flinch" },
      { line: "claude plugin install flinch@flinch" },
    ],
  },
  {
    id: "cursor",
    name: "Cursor",
    intro: "Install Flinch, then add its hooks to Cursor.",
    cmds: [INSTALL_FLINCH, { line: "flinch cursor install" }],
  },
  {
    id: "source",
    name: "From source",
    intro: "Clone the repo, install the command, and add the plugin from your clone.",
    cmds: [
      { line: "git clone https://github.com/voxmastery/flinch && cd flinch" },
      { line: "uv tool install ." },
      { line: "claude plugin marketplace add ./" },
      { line: "claude plugin install flinch@flinch" },
      { line: "flinch cursor install", note: "optional, for Cursor" },
    ],
  },
  {
    id: "any",
    name: "Any agent",
    intro: "Any agent or script: run commands through Flinch, or check them first. Exit code 2 means blocked, 3 means ask a human.",
    cmds: [INSTALL_FLINCH, { line: "flinch run -- <command>" }, { line: "flinch check -- <command>" }],
  },
];

const CLI: readonly [string, string][] = [
  ['flinch hurt "reason"', "Record damage, in your own words."],
  ["flinch scars", "List the scars for this project."],
  ["flinch forgive <id>", "Lift one scar."],
  ["flinch status", "Show what Flinch is doing."],
  ["flinch reset --yes", "Forget all scars, reflexes and memories for this project."],
];

function CommandBlock({ cmds }: { cmds: readonly Cmd[] }) {
  return (
    <ol className="cmds">
      {cmds.map((c) => (
        <li key={c.line} className="cmd">
          <div className="cmd-text">
            <code>{c.line}</code>
            {c.note && <span className="cmd-note">{c.note}</span>}
          </div>
          <CopyButton text={c.line} label={`Copy: ${c.line}`} />
        </li>
      ))}
    </ol>
  );
}

export function Install() {
  const [active, setActive] = useState(0);
  const tabRefs = useRef<Array<HTMLButtonElement | null>>([]);

  const focusTab = (i: number) => {
    const next = (i + TABS.length) % TABS.length;
    setActive(next);
    tabRefs.current[next]?.focus();
  };

  const onKey = (e: KeyboardEvent<HTMLButtonElement>) => {
    const moves: Record<string, number> = { ArrowRight: active + 1, ArrowLeft: active - 1, Home: 0, End: TABS.length - 1 };
    if (!(e.key in moves)) return;
    e.preventDefault();
    focusTab(moves[e.key]);
  };

  return (
    <section className="section" id="install" aria-labelledby="install-title">
      <div className="wrap install-grid">
        <div className="section-head">
          <h2 id="install-title">Works with Claude Code and Cursor</h2>
          <p>
            Claude Code and Cursor today, plus any agent or script through a generic check command. One small daemon
            serves all your projects. It runs locally and offline, with no API keys.
          </p>
        </div>

        <div className="install-panel">
          <div className="tabs" role="tablist" aria-label="Choose your agent">
            {TABS.map((t, i) => (
              <button
                key={t.id}
                ref={(el) => {
                  tabRefs.current[i] = el;
                }}
                type="button"
                role="tab"
                id={`tab-${t.id}`}
                aria-selected={active === i}
                aria-controls={`panel-${t.id}`}
                tabIndex={active === i ? 0 : -1}
                className="tab"
                onClick={() => setActive(i)}
                onKeyDown={onKey}
              >
                {t.name}
              </button>
            ))}
          </div>
          {TABS.map((t, i) => (
            <div
              key={t.id}
              role="tabpanel"
              id={`panel-${t.id}`}
              aria-labelledby={`tab-${t.id}`}
              hidden={active !== i}
              tabIndex={0}
              className="tabpanel"
            >
              <p className="tab-intro">{t.intro}</p>
              <CommandBlock cmds={t.cmds} />
            </div>
          ))}
        </div>

        <div className="cli">
          <h3>After install</h3>
          <dl className="cli-list">
            {CLI.map(([cmd, what]) => (
              <div key={cmd}>
                <dt>
                  <code>{cmd}</code>
                </dt>
                <dd>{what}</dd>
              </div>
            ))}
          </dl>
          <p className="cli-live">
            Live view while Flinch runs: <code>http://127.0.0.1:7331/</code>
          </p>
        </div>
      </div>
    </section>
  );
}
