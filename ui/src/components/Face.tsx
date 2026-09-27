import { useEffect, useState } from "react";
import type { FaceCue } from "../store";
import { MOOD_CAPTION, useFaceMood, type Mood } from "./useFaceMood";
import "./Face.css";

const BODY =
  "M200 78 C 286 74, 346 132, 350 206 C 354 276, 292 318, 200 320 C 108 322, 50 280, 50 206 C 50 134, 114 82, 200 78 Z";

const MOUTH: Record<Mood, string> = {
  calm: "M182 244 Q200 258 218 244",
  healing: "M178 242 Q200 262 222 242",
  wary: "M184 250 Q200 246 216 250",
  flinch: "M188 248 Q200 234 212 248 Q200 262 188 248 Z",
  hurt: "M176 252 Q184 243 192 251 Q200 259 208 251 Q216 243 224 252",
  mending: "M184 252 Q200 244 216 252",
};

const BLINK_EVERY_MS = 4000;
const BLINK_MS = 160;

function useBlink(enabled: boolean): boolean {
  const [closed, setClosed] = useState(false);
  useEffect(() => {
    if (!enabled) return;
    let close: number | undefined;
    const tick = window.setInterval(() => {
      setClosed(true);
      close = window.setTimeout(() => setClosed(false), BLINK_MS);
    }, BLINK_EVERY_MS + Math.random() * 800);
    return () => {
      window.clearInterval(tick);
      window.clearTimeout(close);
      setClosed(false);
    };
  }, [enabled]);
  return closed;
}

function Eye({ cx }: { cx: number }) {
  const dir = cx < 200 ? 1 : -1;
  const tip = cx + dir * 14;
  const back = cx - dir * 12;
  return (
    <g className="eye">
      <g className="eye-open">
        <ellipse cx={cx} cy={196} rx={15} ry={21} className="pupil" />
        <circle cx={cx + 5} cy={188} r={5} className="glint" />
      </g>
      <path className="eye-shut" d={`M${back} 184 L${tip} 196 L${back} 208`} />
    </g>
  );
}

interface FaceProps {
  cue: { seq: number; kind: FaceCue };
  action: string;
}

export function Face({ cue, action }: FaceProps) {
  const mood = useFaceMood(cue);
  const blink = useBlink(mood === "calm" || mood === "healing");

  return (
    <div className="face-wrap">
      <svg
        className={`face mood-${mood}${blink ? " blink" : ""}`}
        viewBox="0 0 400 360"
        role="img"
        aria-label={`Flinch is ${MOOD_CAPTION[mood]}`}
      >
        <defs>
          <radialGradient id="face-sheen" cx="0.35" cy="0.28" r="0.75">
            <stop offset="0" stopColor="#ffffff" stopOpacity="0.55" />
            <stop offset="0.45" stopColor="#ffffff" stopOpacity="0.08" />
            <stop offset="1" stopColor="#000000" stopOpacity="0.22" />
          </radialGradient>
          <filter id="face-blur" x="-50%" y="-50%" width="200%" height="200%">
            <feGaussianBlur stdDeviation="22" />
          </filter>
        </defs>
        <ellipse className="ground" cx="200" cy="338" rx="120" ry="12" />
        <g className="figure">
          <g className="breath">
            <ellipse className="halo" cx="200" cy="200" rx="165" ry="135" filter="url(#face-blur)" />
            <g className="sprout">
              <path d="M206 82 C 206 56, 222 40, 242 38" />
              <circle cx="244" cy="38" r="8" />
            </g>
            <path className="body" d={BODY} />
            <path className="sheen" d={BODY} fill="url(#face-sheen)" />
            <g className="crack">
              <path d="M272 104 L258 134 L276 156 L254 186 L266 210" />
              <path d="M276 156 L298 166" />
            </g>
            <ellipse className="cheek" cx="118" cy="236" rx="20" ry="10" />
            <ellipse className="cheek" cx="282" cy="236" rx="20" ry="10" />
            <Eye cx={150} />
            <Eye cx={250} />
            <path className="mouth" d={MOUTH[mood]} />
          </g>
        </g>
      </svg>
      <div className={`face-caption mood-${mood}`}>{MOOD_CAPTION[mood]}</div>
      <div className="face-action mono" title={action}>
        {action || "waiting for the first agent action"}
      </div>
    </div>
  );
}
