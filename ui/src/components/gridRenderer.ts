// Imperative canvas renderer for the reflex grid. Owns its animation buffers
// (typed arrays mutated per frame for performance) and a requestAnimationFrame loop.

const ACTIVE_FADE_MS = 1500;
const BLOOM_MS = 2600;
const WEIGHT_EASE = 0.08;
const BASE: RGB = [17, 22, 32];
const PAIN: RGB = [255, 46, 72];
const ACTIVE: RGB = [70, 225, 255];
const HOT: RGB = [255, 244, 236];

type RGB = [number, number, number];

function mix(a: RGB, b: RGB, t: number): RGB {
  return [a[0] + (b[0] - a[0]) * t, a[1] + (b[1] - a[1]) * t, a[2] + (b[2] - a[2]) * t];
}

function makeSprite(rgb: RGB, size: number): HTMLCanvasElement {
  const c = document.createElement("canvas");
  c.width = c.height = size;
  const g = c.getContext("2d");
  if (!g) return c;
  const grad = g.createRadialGradient(size / 2, size / 2, 0, size / 2, size / 2, size / 2);
  grad.addColorStop(0, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.9)`);
  grad.addColorStop(0.35, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0.28)`);
  grad.addColorStop(1, `rgba(${rgb[0]},${rgb[1]},${rgb[2]},0)`);
  g.fillStyle = grad;
  g.fillRect(0, 0, size, size);
  return c;
}

export class GridRenderer {
  private readonly ctx: CanvasRenderingContext2D;
  private cols: number;
  private rows: number;
  private target: Float32Array;
  private shown: Float32Array;
  private activeAt: Float64Array;
  private bloomAt: Float64Array;
  private cell = 8;
  private frame = 0;
  private readonly sprites: Record<"pain" | "active" | "hot", HTMLCanvasElement>;

  constructor(private readonly canvas: HTMLCanvasElement, cols: number, rows: number) {
    const ctx = canvas.getContext("2d");
    if (!ctx) throw new Error("2D canvas is not available");
    this.ctx = ctx;
    this.cols = cols;
    this.rows = rows;
    const n = cols * rows;
    this.target = new Float32Array(n);
    this.shown = new Float32Array(n);
    this.activeAt = new Float64Array(n).fill(-Infinity);
    this.bloomAt = new Float64Array(n).fill(-Infinity);
    this.sprites = { pain: makeSprite(PAIN, 64), active: makeSprite(ACTIVE, 64), hot: makeSprite(HOT, 64) };
  }

  setShape(cols: number, rows: number): void {
    if (cols === this.cols && rows === this.rows) return;
    this.cols = cols;
    this.rows = rows;
    const n = cols * rows;
    this.target = new Float32Array(n);
    this.shown = new Float32Array(n);
    this.activeAt = new Float64Array(n).fill(-Infinity);
    this.bloomAt = new Float64Array(n).fill(-Infinity);
  }

  setWeights(weights: readonly number[]): void {
    const n = Math.min(weights.length, this.target.length);
    for (let i = 0; i < n; i++) this.target[i] = weights[i];
  }

  activate(cells: readonly number[]): void {
    const now = performance.now();
    for (const i of cells) if (i >= 0 && i < this.activeAt.length) this.activeAt[i] = now;
  }

  bloom(cells: readonly number[]): void {
    const now = performance.now();
    for (const i of cells) {
      if (i < 0 || i >= this.bloomAt.length) continue;
      this.bloomAt[i] = now + Math.random() * 500;
      this.shown[i] = Math.min(this.shown[i], 0.05);
    }
  }

  resize(width: number, height: number): void {
    const dpr = window.devicePixelRatio || 1;
    this.cell = Math.max(2, Math.min(width / this.cols, height / this.rows));
    const w = this.cell * this.cols;
    const h = this.cell * this.rows;
    this.canvas.style.width = `${w}px`;
    this.canvas.style.height = `${h}px`;
    this.canvas.width = Math.round(w * dpr);
    this.canvas.height = Math.round(h * dpr);
    this.ctx.setTransform(dpr, 0, 0, dpr, 0, 0);
  }

  start(): void {
    const loop = () => {
      this.draw(performance.now());
      this.frame = requestAnimationFrame(loop);
    };
    this.frame = requestAnimationFrame(loop);
  }

  stop(): void {
    cancelAnimationFrame(this.frame);
  }

  private draw(now: number): void {
    const { ctx, cell, cols } = this;
    const n = this.target.length;
    const gap = cell > 6 ? 1.2 : 0.6;
    const size = cell - gap;
    const glows: Array<[number, number, "pain" | "active" | "hot", number]> = [];

    ctx.globalCompositeOperation = "source-over";
    ctx.fillStyle = "#07090e";
    ctx.fillRect(0, 0, cell * cols, cell * this.rows);

    for (let i = 0; i < n; i++) {
      this.shown[i] += (this.target[i] - this.shown[i]) * WEIGHT_EASE;
      const w = this.shown[i];
      const bAge = now - this.bloomAt[i];
      const b = bAge >= 0 && bAge < BLOOM_MS ? Math.sin((bAge / BLOOM_MS) * Math.PI) : 0;
      const aAge = now - this.activeAt[i];
      const a = aAge >= 0 && aAge < ACTIVE_FADE_MS ? Math.pow(1 - aAge / ACTIVE_FADE_MS, 1.6) : 0;

      const pain = Math.min(1, Math.pow(w, 0.7) + b * 0.6);
      let rgb = mix(BASE, PAIN, pain * 0.9);
      if (a > 0) rgb = mix(rgb, w > 0.12 ? HOT : ACTIVE, a * (w > 0.12 ? 1 : 0.85));

      ctx.fillStyle = `rgb(${rgb[0] | 0},${rgb[1] | 0},${rgb[2] | 0})`;
      const x = (i % cols) * cell;
      const y = Math.floor(i / cols) * cell;
      ctx.fillRect(x + gap / 2, y + gap / 2, size, size);

      if (a > 0.05) glows.push([x, y, w > 0.12 ? "hot" : "active", a]);
      else if (pain > 0.5) glows.push([x, y, "pain", (pain - 0.45) * 0.35]);
    }

    ctx.globalCompositeOperation = "lighter";
    // Halos stay within about one neighbouring cell so 5% activity reads as 5%, not a full screen.
    const r = cell * 1.5;
    for (const [x, y, kind, alpha] of glows) {
      const rr = kind === "hot" ? r * 1.25 : r;
      ctx.globalAlpha = Math.min(1, alpha * 0.75);
      ctx.drawImage(this.sprites[kind], x + cell / 2 - rr, y + cell / 2 - rr, rr * 2, rr * 2);
    }
    ctx.globalAlpha = 1;
    ctx.globalCompositeOperation = "source-over";
  }
}
