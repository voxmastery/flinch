import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Scene, fadeUp } from "../components/Scene";
import { Terminal } from "../components/Terminal";
import { Creature } from "../components/Creature";
import { Caption } from "../components/Caption";
import { Meter } from "../components/Meter";
import { CMD, dangerOf } from "../data";
import { C } from "../theme";
import { cues } from "../timeline";

const Q = cues("danger");
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const Danger: React.FC = () => {
  const frame = useCurrentFrame();
  const value = dangerOf(CMD.heroku) * interpolate(frame, [62, Q.ask - 4], [0, 1], CLAMP);
  return (
    <Scene push={1.06}>
      <Terminal title="Claude Code" width={1120} height={470} style={{ left: 100, top: 90 }} lines={[
        { at: Q.typeCmd, kind: "cmd", text: CMD.heroku },
        { at: Q.ask, kind: "ask",
          text: "Flinch: this action looks destructive and hard to undo (learned danger 0.99). Confirm only if it is intended." },
        { at: Q.proceed, kind: "agent", text: "Do you want to proceed?" },
      ]} />
      <div style={{ position: "absolute", left: 1370, top: 110 }}>
        <Creature size={400} cues={[{ at: Q.ask, mood: "wary" }]} />
      </div>
      <div style={{ position: "absolute", left: 1300, top: 520, ...fadeUp(frame, 58) }}>
        <Meter label="danger sense" value={value} width={520} lines={false} color={C.wary}
          verdict="asks first" verdictOpacity={interpolate(frame, [Q.ask, Q.ask + 12], [0, 1], CLAMP)} />
      </div>
      <Caption at={Q.caption} text="Never seen before? It asks first. Offline." bottom={64} />
    </Scene>
  );
};
