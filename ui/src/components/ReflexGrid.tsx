import { useEffect, useRef } from "react";
import type { Pulse } from "../store";
import { GridRenderer } from "./gridRenderer";
import "./ReflexGrid.css";

interface ReflexGridProps {
  cols: number;
  rows: number;
  weights: number[];
  activation: Pulse | null;
  bloom: Pulse | null;
}

export function ReflexGrid({ cols, rows, weights, activation, bloom }: ReflexGridProps) {
  const boxRef = useRef<HTMLDivElement>(null);
  const canvasRef = useRef<HTMLCanvasElement>(null);
  const rendererRef = useRef<GridRenderer | null>(null);

  useEffect(() => {
    const canvas = canvasRef.current;
    const box = boxRef.current;
    if (!canvas || !box) return;
    let renderer: GridRenderer;
    try {
      renderer = new GridRenderer(canvas, cols, rows);
    } catch (err) {
      console.error("flinch: reflex grid could not start", err);
      return;
    }
    rendererRef.current = renderer;
    const fit = () => renderer.resize(box.clientWidth, box.clientHeight);
    const ro = new ResizeObserver(fit);
    ro.observe(box);
    fit();
    renderer.start();
    return () => {
      ro.disconnect();
      renderer.stop();
      rendererRef.current = null;
    };
    // Created once on mount; shape changes go through setShape below.
  }, []);

  useEffect(() => {
    const r = rendererRef.current;
    const box = boxRef.current;
    if (!r || !box) return;
    r.setShape(cols, rows);
    r.resize(box.clientWidth, box.clientHeight);
  }, [cols, rows]);

  useEffect(() => {
    rendererRef.current?.setWeights(weights);
  }, [weights]);

  useEffect(() => {
    if (activation) rendererRef.current?.activate(activation.cells);
  }, [activation]);

  useEffect(() => {
    if (bloom) rendererRef.current?.bloom(bloom.cells);
  }, [bloom]);

  return (
    <div className="reflex-grid" ref={boxRef}>
      <canvas ref={canvasRef} aria-label="reflex grid" />
    </div>
  );
}
