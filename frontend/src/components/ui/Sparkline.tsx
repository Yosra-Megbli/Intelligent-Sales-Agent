import React from "react";

interface SparklineProps {
  data: number[];
  color?: string;
  width?: number;
  height?: number;
  positive?: boolean;
}

export const Sparkline: React.FC<SparklineProps> = ({
  data,
  color,
  width = 64,
  height = 24,
  positive = true,
}) => {
  if (!data || data.length < 2) {
    return <div style={{ width, height }} className="opacity-0" />;
  }

  const min = Math.min(...data);
  const max = Math.max(...data);
  const range = max - min || 1;

  const points = data
    .map((val, index) => {
      const x = (index / (data.length - 1)) * (width - 4) + 2;
      const y = height - 3 - ((val - min) / range) * (height - 6);
      return `${x.toFixed(1)},${y.toFixed(1)}`;
    })
    .join(" ");

  const strokeColor =
    color || (positive ? "var(--color-teal-text)" : "var(--color-danger)");

  return (
    <svg
      width={width}
      height={height}
      className="overflow-visible select-none shrink-0"
    >
      <polyline
        fill="none"
        stroke={strokeColor}
        strokeWidth="2"
        strokeLinecap="round"
        strokeLinejoin="round"
        points={points}
      />
    </svg>
  );
};
