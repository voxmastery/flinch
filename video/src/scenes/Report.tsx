import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Scene } from "../components/Scene";
import { Terminal } from "../components/Terminal";
import { Creature } from "../components/Creature";
import { Caption } from "../components/Caption";
import { Grid3D } from "../components/Grid3D";
import { CMD } from "../data";
import { cues } from "../timeline";

const Q = cues("report");
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

export const Report: React.FC = () => {
  const frame = useCurrentFrame();
  const into = interpolate(frame, [Q.grid, Q.grid + 30], [0, 1], CLAMP);
  const painAmt = interpolate(frame, [Q.grid + 10, Q.grid + 90], [0, 1], CLAMP);
  return (
    <Scene push={1.05}>
      <div style={{ position: "absolute", inset: 0, opacity: into }}>
        <Grid3D width={1500} painAmt={painAmt} bloom={0.9 * painAmt} idKey="report"
          rotateX={interpolate(frame, [Q.grid, 210], [38, 56], CLAMP)}
          rotateZ={interpolate(frame, [Q.grid, 210], [-12, -4], CLAMP)}
          scale={interpolate(frame, [Q.grid, 210], [0.85, 1.12], CLAMP)} translateY={-40} />
      </div>
      <div style={{
        position: "absolute", inset: 0, opacity: 1 - into, filter: `blur(${into * 14}px)`,
        transform: `scale(${1 + into * 0.12})`,
      }}>
        <Terminal title="Claude Code" width={1000} height={330} style={{ left: 110, top: 150 }} lines={[
          { at: -100, kind: "cmd", text: CMD.scar },
          { at: Q.typeUser, kind: "user", label: "You", text: "you deleted the customer database!" },
        ]} />
        <div style={{ position: "absolute", left: 1300, top: 190 }}>
          <Creature size={440} cues={[{ at: Q.hurt, mood: "hurt" }]} />
        </div>
      </div>
      <Caption at={Q.caption} text="Flinch gave it pain receptors. Now it's a scar." bottom={64} />
    </Scene>
  );
};
