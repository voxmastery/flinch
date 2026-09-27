import { useEffect, useMemo, useRef } from "react";
import { GRID, PAIN_WEIGHTS, activeCells } from "../../data/reflex";
import { paintGrid } from "./gridPaint";

const FADE_MS = 380;

interface ReflexCanvasProps {
  /** Command whose active cells are lit, or null for pain memory only. */
  command: string | null;
  /** Skip the fade (reduced motion). */
  instant: boolean;
}

export function ReflexCanvas({ command, instant }: ReflexCanvasProps) {
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const cellRef = useRef(8);
  const levelRef = useRef(0);
  const shownRef = useRef<string | null>(null);
  const active = useMemo(() => new Set(activeCells(command ?? shownRef.current ?? "")), [command]);

  const draw = (level: number, cells: ReadonlySet<number>) => {
    const ctx = canvasRef.current?.getContext("2d");
    if (!ctx) return;
    paintGrid({ ctx, cols: GRID.cols, rows: GRID.rows, cell: cellRef.current, pain: PAIN_WEIGHTS, active: cells, level });
  };

  // Keep the canvas sized to its box at device resolution.
  useEffect(() => {
    const canvas = canvasRef.current;
    if (!canvas) return;
    const fit = () => {
      const width = canvas.parentElement?.clientWidth ?? 640;
      const cell = width / GRID.cols;
      const dpr = Math.min(window.devicePixelRatio || 1, 2);
      cellRef.current = cell;
      canvas.width = Math.round(width * dpr);
      canvas.height = Math.round(cell * GRID.rows * dpr);
      canvas.getContext("2d")?.setTransform(dpr, 0, 0, dpr, 0, 0);
      draw(levelRef.current, active);
    };
    const ro = new ResizeObserver(fit);
    ro.observe(canvas.parentElement ?? canvas);
    fit();
    return () => ro.disconnect();
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [active]);

  // Fade the command's cells in (or out) only while the level is changing.
  useEffect(() => {
    const target = command ? 1 : 0;
    if (command) shownRef.current = command;
    if (instant) {
      levelRef.current = target;
      draw(target, active);
      return;
    }
    const from = levelRef.current;
    const start = performance.now();
    let frame = 0;
    const step = (now: number) => {
      const t = Math.min(1, (now - start) / FADE_MS);
      const eased = 1 - Math.pow(1 - t, 3);
      levelRef.current = from + (target - from) * eased;
      draw(levelRef.current, active);
      if (t < 1) frame = requestAnimationFrame(step);
    };
    frame = requestAnimationFrame(step);
    return () => cancelAnimationFrame(frame);
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [command, instant, active]);

  return <canvas ref={canvasRef} className="reflex-canvas" aria-hidden="true" />;
}
