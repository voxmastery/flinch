// Paints the 80x50 reflex grid: pain cells in red, a command's active cells in pale blue,
// and cells that are both active and painful white-hot. `level` (0..1) fades the command in.

type RGB = readonly [number, number, number];

const BASE: RGB = [38, 43, 82]; // --cell-dim
const PAIN: RGB = [255, 77, 94]; // --pain
const ACTIVE: RGB = [154, 160, 200]; // --muted
const HOT: RGB = [255, 246, 238];

function mix(a: RGB, b: RGB, t: number): RGB {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

function css(c: RGB): string {
  return `rgb(${c[0] | 0},${c[1] | 0},${c[2] | 0})`;
}

function makeGlow(size: number): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d");
  if (!g) return c;
  const grad = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grad.addColorStop(0, "rgba(255,240,230,0.85)");
  grad.addColorStop(0.35, "rgba(255,170,160,0.25)");
  grad.addColorStop(1, "rgba(255,120,120,0)");
  g.fillStyle = grad;
  g.fillRect(0, 0, size, size);
  return c;
}

let glowSprite: HTMLCanvasElement | null = null;

export interface PaintInput {
  ctx: CanvasRenderingContext2D;
  cols: number;
  rows: number;
  cell: number;
  pain: readonly number[];
  active: ReadonlySet<number>;
  level: number;
}

export function paintGrid({ ctx, cols, rows, cell, pain, active, level }: PaintInput): void {
  const gap = cell > 6 ? 1.5 : 0.8;
  const size = cell - gap;
  const hot: Array<[number, number, number]> = [];
  ctx.clearRect(0, 0, cols * cell, rows * cell);

  for (let i = 0; i < cols * rows; i++) {
    const w = pain[i] ?? 0;
    const on = active.has(i) ? level : 0;
    let rgb = mix(BASE, PAIN, Math.min(1, w) * 0.62);
    if (on > 0) {
      rgb = w > 0 ? mix(rgb, HOT, on * w) : mix(rgb, ACTIVE, on * 0.85);
      if (w > 0) hot.push([i % cols, Math.floor(i / cols), on * w]);
    }
    ctx.fillStyle = css(rgb);
    ctx.fillRect((i % cols) * cell + gap / 2, Math.floor(i / cols) * cell + gap / 2, size, size);
  }

  if (hot.length === 0) return;
  glowSprite ??= makeGlow(64);
  const r = cell * 1.8;
  ctx.globalCompositeOperation = "lighter";
  for (const [x, y, a] of hot) {
    ctx.globalAlpha = a * 0.6;
    ctx.drawImage(glowSprite, x * cell + cell / 2 - r, y * cell + cell / 2 - r, r * 2, r * 2);
  }
  ctx.globalAlpha = 1;
  ctx.globalCompositeOperation = "source-over";
}
