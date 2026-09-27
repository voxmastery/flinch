import React from "react";
import { Composition } from "remotion";
import { FlinchDemo } from "./FlinchDemo";
import { FPS, TOTAL_FRAMES } from "./timeline";

export const RemotionRoot: React.FC = () => (
  <Composition
    id="FlinchDemo"
    component={FlinchDemo}
    durationInFrames={TOTAL_FRAMES}
    fps={FPS}
    width={1920}
    height={1080}
  />
);
