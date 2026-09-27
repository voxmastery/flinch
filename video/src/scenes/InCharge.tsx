import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Scene, fadeUp } from "../components/Scene";
import { Terminal } from "../components/Terminal";
import { Creature } from "../components/Creature";
import { Caption } from "../components/Caption";
import { ReflexGrid } from "../components/ReflexGrid";
import { C, FONT } from "../theme";
import { CMD } from "../data";
import { cues } from "../timeline";

const Q = cues("charge");
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const Step: React.FC<{ n: number; title: string; at: number; children?: React.ReactNode; top: number }> = ({ n, title, at, children, top }) => {
  const frame = useCurrentFrame();
  return (
    <div style={{ position: "absolute", left: 1060, top, width: 780, display: "flex", gap: 26, ...fadeUp(frame, at) }}>
      <div style={{ fontFamily: FONT.display, fontWeight: 800, fontSize: 56, color: C.muted, width: 40, lineHeight: 1 }}>{n}</div>
      <div style={{ flex: 1 }}>
        <div style={{ fontFamily: FONT.display, fontWeight: 700, fontSize: 46, letterSpacing: "-0.02em", lineHeight: 1.1 }}>{title}</div>
        {children}
      </div>
    </div>
  );
};

const Choice: React.FC<{ label: string; selected: number }> = ({ label, selected }) => (
  <span style={{
    display: "inline-block", padding: "6px 26px", borderRadius: 12, marginRight: 14, fontFamily: FONT.body, fontSize: 32,
    border: `2px solid ${selected > 0 ? C.calm : C.line}`,
    background: selected > 0 ? `rgba(127,227,196,${0.9 * selected})` : "transparent",
    color: selected > 0.5 ? C.ink : C.muted,
  }}>{label}</span>
);

export const InCharge: React.FC = () => {
  const frame = useCurrentFrame();
  const yes = interpolate(frame, [Q.yes, Q.yes + 6], [0, 1], CLAMP);
  const cool = interpolate(frame, [Q.heal, Q.heal + 70], [1, 0], CLAMP);
  return (
    <Scene push={1.03}>
      <Terminal title="Claude Code" width={900} height={440} style={{ left: 90, top: 70 }} lines={[
        { at: Q.typeUser, kind: "user", label: "You", text: "I really do want to wipe data/, it's test data." },
        { at: Q.typeAgent, kind: "cmd", text: CMD.scar },
        { at: Q.allowed, kind: "ok", text: "runs: the scar was lifted" },
      ]} />
      <div style={{ position: "absolute", left: 110, top: 560 }}>
        <Creature size={300} cues={[{ at: 0, mood: "scarred" }, { at: Q.heal, mood: "forgiven" }]} />
      </div>
      <div style={{ position: "absolute", left: 470, top: 585 }}>
        <ReflexGrid width={480} painAmt={cool} bloom={0.6 * cool} idKey="charge" />
        <div style={{ marginTop: 12, fontFamily: FONT.body, fontSize: 26, color: C.muted }}>
          {frame >= Q.heal + 30 ? "pain memory cleared" : "pain memory"}
        </div>
      </div>

      <Step n={1} title="When Flinch asks, you decide." at={Q.stepA} top={80}>
        <div style={{ marginTop: 18, fontFamily: FONT.body, fontSize: 32, color: C.text }}>Do you want to proceed?</div>
        <div style={{ marginTop: 14 }}><Choice label="Yes" selected={yes} /><Choice label="No" selected={0} /></div>
      </Step>
      <Step n={2} title="A scar? Forgive it." at={Q.stepB} top={330}>
        <Terminal title="Your terminal" width={720} height={190} style={{ position: "relative", marginTop: 18 }} lines={[
          { at: Q.typeForgive, kind: "cmd", text: "flinch forgive p_c3c86a69" },
          { at: Q.forgave, kind: "ok", text: "forgave p_c3c86a69: `rm -rf data/`" },
        ]} />
      </Step>
      <Step n={3} title="Or run it yourself." at={Q.stepC} top={680}>
        <div style={{ marginTop: 10, fontFamily: FONT.body, fontSize: 34, color: C.muted }}>Flinch only guards the agent.</div>
      </Step>
      <Caption at={Q.caption} text="Flinch stops the agent, not you." bottom={50} />
    </Scene>
  );
};
