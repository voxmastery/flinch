import { loadFont as loadDisplay } from "@remotion/google-fonts/BricolageGrotesque";
import { loadFont as loadBody } from "@remotion/google-fonts/AtkinsonHyperlegible";
import { loadFont as loadMono } from "@remotion/google-fonts/JetBrainsMono";

export const C = {
  ground: "#141833",
  raised: "#1C2145",
  cellDim: "#262B52",
  line: "#343A6B",
  calm: "#7FE3C4",
  wary: "#F2B544",
  pain: "#FF4D5E",
  text: "#E8EAF6",
  muted: "#9AA0C8",
  ink: "#12161d",
} as const;

export const FONT = {
  display: loadDisplay("normal", { weights: ["500", "700", "800"], subsets: ["latin"] }).fontFamily,
  body: loadBody("normal", { weights: ["400", "700"], subsets: ["latin"] }).fontFamily,
  mono: loadMono("normal", { weights: ["400", "600"], subsets: ["latin"] }).fontFamily,
} as const;
