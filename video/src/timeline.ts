import tl from "./timeline.json";

export const FPS = tl.fps;
export const TOTAL_FRAMES = tl.total;
export const CHARS_PER_FRAME = tl.charsPerFrame;

export type SceneKey = keyof typeof tl.scenes;
export const SCENES = tl.scenes;
export const SCENE_ORDER = Object.keys(tl.scenes) as SceneKey[];

/** Local cue frames for a scene (shared with audio/make_soundtrack.py). */
export const cues = <K extends SceneKey>(key: K) => tl.scenes[key].cues as (typeof tl.scenes)[K]["cues"];
