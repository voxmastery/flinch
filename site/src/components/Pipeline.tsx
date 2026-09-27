import "./Pipeline.css";

type Tone = "pain" | "wary" | "calm";

interface Step {
  n: string;
  title: string;
  when: string;
  outcome: string;
  tone: Tone;
  split?: boolean;
}

const STEPS: readonly Step[] = [
  { n: "1", title: "Scar", when: "Exact repeat of a past mistake", outcome: "Blocked in 0.17 ms", tone: "pain" },
  {
    n: "2",
    title: "Reflex",
    when: "Similar action, shares reflex cells",
    outcome: "Blocked or asks first",
    tone: "pain",
    split: true,
  },
  { n: "3", title: "Danger sense", when: "Never-seen destroyer", outcome: "Asks first, fully offline", tone: "wary" },
];

const END = { title: "Then it runs", when: "Nothing matched" };

function Horizontal() {
  const xs = [300, 580, 860];
  const y = 132;
  return (
    <svg className="pipe pipe-h" viewBox="0 0 1160 330" aria-hidden="true">
      <line className="pipe-rail" x1="130" y1={y} x2="1030" y2={y} />
      <g>
        <rect className="pipe-start" x="0" y={y - 26} width="164" height="52" rx="8" />
        <text className="pipe-mono" x="82" y={y + 6} textAnchor="middle">agent command</text>
      </g>
      {STEPS.map((s, i) => (
        <g key={s.n}>
          <text className="pipe-title" x={xs[i]} y="42" textAnchor="middle">{s.title}</text>
          <text className="pipe-when" x={xs[i]} y="70" textAnchor="middle">{s.when}</text>
          <line className={`pipe-exit tone-${s.tone}`} x1={xs[i]} y1={y + 30} x2={xs[i]} y2="236" />
          <circle className="pipe-node" cx={xs[i]} cy={y} r="30" />
          <text className="pipe-num" x={xs[i]} y={y + 9} textAnchor="middle">{s.n}</text>
          <rect className={`pipe-tag tone-${s.tone}${s.split ? " is-split" : ""}`} x={xs[i] - 128} y="240" width="256" height="48" rx="24" />
          <text className="pipe-outcome" x={xs[i]} y="270" textAnchor="middle">{s.outcome}</text>
        </g>
      ))}
      <g>
        <text className="pipe-title" x="1085" y="42" textAnchor="middle">{END.title}</text>
        <text className="pipe-when" x="1085" y="70" textAnchor="middle">{END.when}</text>
        <rect className="pipe-tag tone-calm" x="1030" y={y - 23} width="110" height="46" rx="23" />
        <text className="pipe-outcome" x="1085" y={y + 6} textAnchor="middle">Runs</text>
      </g>
    </svg>
  );
}

function Vertical() {
  const ys = [40, 200, 360];
  const x = 34;
  return (
    <svg className="pipe pipe-v" viewBox="0 0 340 600" aria-hidden="true">
      <line className="pipe-rail" x1={x} y1="20" x2={x} y2="540" />
      {STEPS.map((s, i) => (
        <g key={s.n}>
          <circle className="pipe-node" cx={x} cy={ys[i]} r="24" />
          <text className="pipe-num pipe-num-sm" x={x} y={ys[i] + 8} textAnchor="middle">{s.n}</text>
          <text className="pipe-title" x="76" y={ys[i] + 2}>{s.title}</text>
          <text className="pipe-when" x="76" y={ys[i] + 30}>{s.when}</text>
          <line className={`pipe-exit tone-${s.tone}`} x1={x + 24} y1={ys[i] + 72} x2="76" y2={ys[i] + 72} />
          <rect className={`pipe-tag tone-${s.tone}${s.split ? " is-split" : ""}`} x="76" y={ys[i] + 50} width="258" height="44" rx="22" />
          <text className="pipe-outcome" x="205" y={ys[i] + 78} textAnchor="middle">{s.outcome}</text>
        </g>
      ))}
      <rect className="pipe-tag tone-calm" x={x - 26} y="530" width="92" height="44" rx="22" />
      <text className="pipe-outcome" x={x + 20} y="558" textAnchor="middle">Runs</text>
      <text className="pipe-when" x="112" y="558">{END.when}</text>
    </svg>
  );
}

/** The reflex check, as a diagram: scar, then reflex, then danger sense, then the command runs. */
export function Pipeline() {
  return (
    <div className="pipe-block">
      <h3 id="check-title" className="pipe-heading">
        Before every action: how a command is checked
      </h3>
      <p className="pipe-lede">Three checks run in order. The first one that matches decides.</p>
      <figure className="pipe-figure" aria-labelledby="check-title">
        <Horizontal />
        <Vertical />
        <figcaption className="visually-hidden">
          <ol>
            {STEPS.map((s) => (
              <li key={s.n}>
                {s.title}: {s.when}. {s.outcome}.
              </li>
            ))}
            <li>{END.when}: the command runs.</li>
          </ol>
        </figcaption>
      </figure>
      <p className="pipe-note">
        An exact repeat is blocked even when the Flinch daemon is stopped. One daemon serves every project, so a scar
        learned in Claude Code also blocks the same command in Cursor.
      </p>
    </div>
  );
}
