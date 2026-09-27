import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Scene, fadeUp } from "../components/Scene";
import { Creature } from "../components/Creature";
import { Caption } from "../components/Caption";
import { Grid3D } from "../components/Grid3D";
import { Meter } from "../components/Meter";
import { Glitch } from "../components/Cinema";
import { C, FONT } from "../theme";
import { CMD, PAIN, avoidOf, codeOf } from "../data";
import { CHARS_PER_FRAME, cues } from "../timeline";

const Q = cues("general");
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

interface Phase { cmd: string; type: number; verdict: string; verdictAt: number }
const A: Phase = { cmd: CMD.near, type: Q.typeA, verdict: "blocked", verdictAt: Q.flinchA };
const B: Phase = { cmd: CMD.far, type: Q.typeB, verdict: "asks first", verdictAt: Q.askB };

const shared = (cmd: string) => codeOf(cmd).filter((i) => PAIN[i] > 0).length;

const Legend: React.FC = () => {
  const item = (color: string, text: string) => (
    <div style={{ display: "flex", alignItems: "center", gap: 12 }}>
      <div style={{ width: 22, height: 22, borderRadius: 5, background: color }} />
      <span>{text}</span>
    </div>
  );
  return (
    <div style={{ display: "flex", gap: 36, fontFamily: FONT.body, fontSize: 28, color: C.muted }}>
      {item(C.pain, "pain memory")}{item(C.muted, "this command")}{item("#ffffff", "both")}
    </div>
  );
};

export const Generalize: React.FC = () => {
  const frame = useCurrentFrame();
  const p = frame >= Q.typeB - 3 ? B : A;
  const typedFrames = Math.ceil(p.cmd.length / CHARS_PER_FRAME);
  const lit0 = p.type + typedFrames + 2;
  const activeAmt = interpolate(frame, [lit0, lit0 + (p === A ? 40 : 30)], [0, 1], CLAMP);
  const flare = p === A ? Q.flareA : lit0 + 32;
  const hot = interpolate(frame, [flare, flare + 8, flare + 30, flare + 55], [0, 1, 0.55, 0.35], CLAMP);
  const score = avoidOf(p.cmd) * interpolate(frame, [flare + 8, p.verdictAt - 4], [0, 1], CLAMP);
  const typed = p.cmd.slice(0, Math.max(0, Math.floor((frame - p.type) * CHARS_PER_FRAME)));
  const count = Math.round(shared(p.cmd) * activeAmt);
  return (
    <Scene push={1.04}>
      <Glitch at={Q.flinchA} len={10} px={8} id="glitch-general">
        <div style={{ position: "absolute", left: -110, top: -30, width: 1320, height: 1080 }}>
          <Grid3D width={1300} painAmt={1} active={codeOf(p.cmd)} activeAmt={activeAmt} hot={hot} dimPain={activeAmt}
            bloom={0.6} rise={70 * activeAmt} idKey="general"
            rotateX={52} rotateZ={interpolate(frame, [0, 300], [-16, -3])}
            scale={interpolate(frame, [0, 300], [0.92, 1.02])} translateY={-70} />
        </div>
        <div style={{ position: "absolute", left: 1120, top: 0, right: 0, bottom: 0,
          background: "linear-gradient(90deg, rgba(20,24,51,0), rgba(20,24,51,0.88) 130px)" }} />
        <div style={{ position: "absolute", left: 110, top: 880, ...fadeUp(frame, 30) }}><Legend /></div>
        <div key={p.cmd} style={{ position: "absolute", left: 1250, top: 90, width: 600, ...fadeUp(frame, p.type - 3) }}>
          <div style={{ fontFamily: FONT.body, fontSize: 30, color: C.muted }}>Agent tries</div>
          <div style={{ fontFamily: FONT.mono, fontSize: 46, fontWeight: 600, marginTop: 6, height: 62 }}>{typed}</div>
          <div style={{ fontFamily: FONT.body, fontSize: 32, marginTop: 22 }}>
            <span style={{ fontFamily: FONT.mono, fontWeight: 600 }}>{count}</span> of 200 cells shared with the scar
          </div>
          <div style={{ marginTop: 46 }}>
            <Meter label="reflex" value={score} width={560} verdict={p.verdict}
              verdictOpacity={interpolate(frame, [p.verdictAt, p.verdictAt + 10], [0, 1], CLAMP)} />
          </div>
        </div>
        <div style={{ position: "absolute", left: 1440, top: 610 }}>
          <Creature size={280} cues={[{ at: Q.flinchA, mood: "flinch" }, { at: Q.typeB - 3, mood: "calm" }, { at: Q.askB, mood: "wary" }]} />
        </div>
      </Glitch>
      <Caption at={Q.caption} text="Similar enough to hurt." bottom={56} />
    </Scene>
  );
};
