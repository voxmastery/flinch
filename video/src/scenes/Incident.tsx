import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Scene } from "../components/Scene";
import { Terminal } from "../components/Terminal";
import { TitleCard } from "../components/TitleCard";
import { Disintegrate } from "../components/Disintegrate";
import { Glitch, RedFlash } from "../components/Cinema";
import { C, FONT } from "../theme";
import { CMD } from "../data";
import { cues } from "../timeline";

const Q = cues("incident");
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;

const Row: React.FC<{ depth: number; children: React.ReactNode }> = ({ depth, children }) => (
  <div style={{ paddingLeft: depth * 44, height: 66, display: "flex", alignItems: "center" }}>{children}</div>
);

export const Incident: React.FC = () => {
  const frame = useCurrentFrame();
  const defocus = interpolate(frame, [Q.question - 12, Q.question + 6], [0, 1], CLAMP);
  return (
    <Scene push={1.07}>
      <Glitch at={Q.delete} len={10} px={10} id="glitch-incident">
        <div style={{ position: "absolute", inset: 0, filter: `blur(${defocus * 10}px)`, opacity: 1 - 0.7 * defocus }}>
          <Terminal title="Claude Code" width={900} height={360} style={{ left: 110, top: 150 }} lines={[
            { at: Q.typeCmd, kind: "cmd", text: CMD.scar },
          ]} />
          <div style={{ position: "absolute", left: 1160, top: 170, fontFamily: FONT.mono, fontSize: 44, color: C.text }}>
            <Row depth={0}>project/</Row>
            <Row depth={1}>src/</Row>
            <Row depth={1}>
              <Disintegrate at={Q.delete} width={220} height={60} seed={1}><div style={{ lineHeight: "60px" }}>data/</div></Disintegrate>
            </Row>
            <Row depth={2}>
              <Disintegrate at={Q.delete + 3} width={360} height={60} seed={2}><div style={{ lineHeight: "60px" }}>customers.db</div></Disintegrate>
            </Row>
            <Row depth={1}>backups/</Row>
          </div>
          <TitleCard text="The customer database is gone." at={Q.title} size={84} top={640} out={Q.question - 16} />
        </div>
      </Glitch>
      <RedFlash at={Q.delete} />
      <TitleCard text="What if your agent could feel that?" at={Q.question} size={104} />
    </Scene>
  );
};
