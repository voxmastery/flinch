import React from "react";
import { AbsoluteFill, Audio, Sequence, staticFile } from "remotion";
import { C } from "./theme";
import { SCENES, SCENE_ORDER, type SceneKey } from "./timeline";
import { FilmGrain, LightLeaks, Vignette } from "./components/Cinema";
import { ColdOpen } from "./scenes/ColdOpen";
import { Incident } from "./scenes/Incident";
import { Report } from "./scenes/Report";
import { NextSession } from "./scenes/NextSession";
import { Generalize } from "./scenes/Generalize";
import { Danger } from "./scenes/Danger";
import { Errors } from "./scenes/Errors";
import { InCharge } from "./scenes/InCharge";
import { Close } from "./scenes/Close";

const COMPONENTS: Record<SceneKey, React.FC> = {
  cold: ColdOpen, incident: Incident, report: Report, flinch: NextSession,
  general: Generalize, danger: Danger, errors: Errors, charge: InCharge, close: Close,
};

const CUTS = SCENE_ORDER.map((k) => SCENES[k].from).filter((f) => f > 0);

export const FlinchDemo: React.FC = () => (
  <AbsoluteFill style={{ backgroundColor: C.ground }}>
    {SCENE_ORDER.map((key) => {
      const Comp = COMPONENTS[key];
      return (
        <Sequence key={key} from={SCENES[key].from} durationInFrames={SCENES[key].dur} name={key}>
          <Comp />
        </Sequence>
      );
    })}
    <LightLeaks cuts={CUTS} />
    <Vignette />
    <FilmGrain />
    <Audio src={staticFile("soundtrack.wav")} />
  </AbsoluteFill>
);
