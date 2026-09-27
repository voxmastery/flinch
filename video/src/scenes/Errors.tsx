import React from "react";
import { interpolate, useCurrentFrame } from "remotion";
import { Scene, Chip, fadeUp, focusIn } from "../components/Scene";
import { Terminal } from "../components/Terminal";
import { Creature } from "../components/Creature";
import { Caption } from "../components/Caption";
import { TitleCard } from "../components/TitleCard";
import { C, FONT } from "../theme";
import { cues } from "../timeline";

const Q = cues("errors");
const CLAMP = { extrapolateLeft: "clamp", extrapolateRight: "clamp" } as const;
const BUILD = "scripts/build.sh";
const FIX = "cp config/app.example.json config/app.json && sh scripts/build.sh";
const LESSON =
  "`scripts/build.sh` failed with “Error: config/app.json not found”; it passed after `cp config/app.example.json config/app.json`.";

export const Errors: React.FC = () => {
  const frame = useCurrentFrame();
  const panels = interpolate(frame, [Q.titleOut, Q.titleOut + 14], [0, 1], CLAMP);
  const cap1Out = interpolate(frame, [Q.caption2 - 10, Q.caption2 - 2], [1, 0], CLAMP);
  return (
    <Scene push={1.04}>
      <TitleCard text="Not every mistake deletes something." at={Q.title} size={96} out={Q.titleOut} />
      <div style={{ position: "absolute", inset: 0, opacity: panels, filter: `blur(${(1 - panels) * 10}px)` }}>
        <Chip text="First chat" at={Q.titleOut} style={{ left: 90, top: 40 }} />
        <Terminal title="Claude Code" width={860} height={530} style={{ left: 90, top: 110 }} lines={[
          { at: Q.typeBuild, kind: "cmd", text: BUILD },
          { at: Q.error, kind: "deny", text: "Error: config/app.json not found" },
          { at: Q.typeFix, kind: "cmd", text: FIX },
          { at: Q.ok, kind: "ok", text: "build ok" },
          { at: Q.stored, kind: "agent", label: "Flinch", text: "Stored the fix for this error." },
        ]} />
        <div style={{ position: "absolute", inset: 0, ...fadeUp(frame, Q.chat2) }}>
          <Chip text="A brand-new chat" style={{ left: 990, top: 40 }} />
          <Chip text="First try" at={Q.ok2 + 4} style={{ left: 1300, top: 40, color: C.calm, borderColor: C.calm }} />
          <Terminal title="Claude Code" width={840} height={530} style={{ left: 990, top: 110 }} lines={[
            { at: Q.lesson, kind: "agent", label: "Flinch lesson", text: LESSON },
            { at: Q.typeFix2, kind: "cmd", text: FIX },
            { at: Q.ok2, kind: "ok", text: "build ok" },
          ]} />
        </div>
        <div style={{ position: "absolute", left: 830, top: 650 }}>
          <Creature size={250} cues={[{ at: Q.error, mood: "wary" }, { at: Q.ok, mood: "calm" }, { at: Q.ok2, mood: "healing" }]} />
        </div>
        <div style={{ position: "absolute", left: 0, right: 0, top: 890, textAlign: "center", fontFamily: FONT.body,
          fontSize: 34, color: C.muted, ...focusIn(frame, Q.rules) }}>
          Claude Code's rules are written in advance. Flinch writes its own.
        </div>
      </div>
      <div style={{ opacity: cap1Out }}><Caption at={Q.caption1} text="Errors teach it too." bottom={50} /></div>
      <Caption at={Q.caption2} text="It remembers what fixed them." bottom={50} />
    </Scene>
  );
};
