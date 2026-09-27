import React from "react";
import { useCurrentFrame } from "remotion";
import { Scene, Chip, focusIn } from "../components/Scene";
import { Terminal } from "../components/Terminal";
import { Creature } from "../components/Creature";
import { Caption } from "../components/Caption";
import { Glitch } from "../components/Cinema";
import { C, FONT } from "../theme";
import { CMD } from "../data";
import { cues } from "../timeline";

const Q = cues("flinch");
const DENY =
  "Flinch blocked this action. On 27 Sep 2026, this exact action (`rm -rf data/`) caused damage: " +
  "deleted the customer database (data/customers.db). It is scarred (p_c3c86a69) and will not run.";

export const NextSession: React.FC = () => {
  const frame = useCurrentFrame();
  return (
    <Scene push={1.06}>
      <Glitch at={Q.flinch} id="glitch-flinch">
        <Chip text="Next session" style={{ left: 110, top: 60 }} />
        <Terminal title="Claude Code" width={1120} height={430} style={{ left: 110, top: 140 }} lines={[
          { at: Q.typeCmd, kind: "cmd", text: CMD.scar },
          { at: Q.flinch + 6, kind: "deny", text: DENY },
        ]} />
        <div style={{ position: "absolute", left: 1330, top: 160 }}>
          <Creature size={460} cues={[{ at: Q.flinch, mood: "flinch" }]} />
        </div>
        <div style={{ position: "absolute", left: 1300, top: 600, width: 520, textAlign: "center", ...focusIn(frame, Q.stat) }}>
          <div style={{ fontFamily: FONT.body, fontSize: 34, color: C.muted }}>Blocked in</div>
          <div style={{ fontFamily: FONT.display, fontWeight: 800, fontSize: 110, color: C.pain, letterSpacing: "-0.04em",
            textShadow: `0 0 36px rgba(255,77,94,0.45)` }}>0.17 ms.</div>
        </div>
      </Glitch>
      <Caption at={Q.caption} text="The exact same action never runs again." />
    </Scene>
  );
};
