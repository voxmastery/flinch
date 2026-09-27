import "./Creature.css";

export type Mood = "calm" | "wary" | "flinch";

const BODY =
  "M200 78 C 286 74, 346 132, 350 206 C 354 276, 292 318, 200 320 C 108 322, 50 280, 50 206 C 50 134, 114 82, 200 78 Z";

const MOUTH: Record<Mood, string> = {
  calm: "M182 244 Q200 258 218 244",
  wary: "M184 250 Q200 246 216 250",
  flinch: "M188 248 Q200 234 212 248 Q200 262 188 248 Z",
};

const CAPTION: Record<Mood, string> = {
  calm: "calm",
  wary: "wary, asking first",
  flinch: "flinching",
};

function Eye({ cx }: { cx: number }) {
  const dir = cx < 200 ? 1 : -1;
  const tip = cx + dir * 14;
  const back = cx - dir * 12;
  return (
    <g className="cr-eye">
      <g className="cr-eye-open">
        <ellipse cx={cx} cy={196} rx={15} ry={21} className="cr-pupil" />
        <circle cx={cx + 5} cy={188} r={5} className="cr-glint" />
      </g>
      <path className="cr-eye-shut" d={`M${back} 184 L${tip} 196 L${back} 208`} />
    </g>
  );
}

interface CreatureProps {
  mood: Mood;
  /** Bumped on every new flinch so the recoil animation restarts. */
  beat: number;
}

export function Creature({ mood, beat }: CreatureProps) {
  return (
    <svg
      className={`creature mood-${mood}`}
      viewBox="0 0 400 360"
      role="img"
      aria-label={`The Flinch creature, ${CAPTION[mood]}`}
    >
      <defs>
        <radialGradient id="cr-sheen" cx="0.35" cy="0.28" r="0.75">
          <stop offset="0" stopColor="#ffffff" stopOpacity="0.5" />
          <stop offset="0.45" stopColor="#ffffff" stopOpacity="0.06" />
          <stop offset="1" stopColor="#000000" stopOpacity="0.2" />
        </radialGradient>
        <filter id="cr-blur" x="-50%" y="-50%" width="200%" height="200%">
          <feGaussianBlur stdDeviation="22" />
        </filter>
      </defs>
      <ellipse className="cr-ground" cx="200" cy="338" rx="120" ry="12" />
      <g className="cr-figure" key={mood === "flinch" ? beat : "still"}>
        <g className="cr-breath">
          <ellipse className="cr-halo" cx="200" cy="200" rx="165" ry="135" filter="url(#cr-blur)" />
          <g className="cr-stalk">
            <path d="M206 82 C 206 56, 222 40, 242 38" />
            <circle cx="244" cy="38" r="8" />
          </g>
          <path className="cr-body" d={BODY} />
          <path className="cr-sheen" d={BODY} fill="url(#cr-sheen)" />
          <ellipse className="cr-cheek" cx="118" cy="236" rx="20" ry="10" />
          <ellipse className="cr-cheek" cx="282" cy="236" rx="20" ry="10" />
          <Eye cx={150} />
          <Eye cx={250} />
          <path className="cr-mouth" d={MOUTH[mood]} />
        </g>
      </g>
    </svg>
  );
}
