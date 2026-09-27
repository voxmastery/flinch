import React from "react";
import { ReflexGrid, gridHeight, type GridProps } from "./ReflexGrid";

interface Props extends Omit<GridProps, "only"> {
  rotateX: number;
  rotateZ: number;
  scale: number;
  translateY?: number;
  /** How far the command's cells float above the plane, in px. */
  rise?: number;
  style?: React.CSSProperties;
}

/** The reflex grid as a real 3D plane under CSS perspective. */
export const Grid3D: React.FC<Props> = ({ rotateX, rotateZ, scale, translateY = 0, rise = 0, style, ...grid }) => {
  const h = gridHeight(grid.width);
  return (
    <div style={{ position: "absolute", inset: 0, perspective: 1700, perspectiveOrigin: "50% 35%", ...style }}>
      <div style={{
        position: "absolute", left: "50%", top: "50%", width: grid.width, height: h,
        marginLeft: -grid.width / 2, marginTop: -h / 2, transformStyle: "preserve-3d",
        transform: `translateY(${translateY}px) rotateX(${rotateX}deg) rotateZ(${rotateZ}deg) scale(${scale})`,
      }}>
        <div style={{ position: "absolute", inset: 0 }}>
          <ReflexGrid {...grid} only="ground" idKey={`${grid.idKey ?? "g"}-ground`} />
        </div>
        <div style={{ position: "absolute", inset: 0, transform: `translateZ(${rise}px)` }}>
          <ReflexGrid {...grid} only="active" idKey={`${grid.idKey ?? "g"}-active`} />
        </div>
      </div>
    </div>
  );
};
