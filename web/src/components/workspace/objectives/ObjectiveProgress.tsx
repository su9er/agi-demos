import React from 'react';

import { CheckCircle2, Target } from 'lucide-react';

export interface ObjectiveProgressProps {
  progress: number;
  size?: number | undefined;
  strokeWidth?: number | undefined;
  color?: string | undefined;
}

export const ObjectiveProgress: React.FC<ObjectiveProgressProps> = ({
  progress,
  size = 48,
  strokeWidth = 4,
  color,
}) => {
  const radius = (size - strokeWidth) / 2;
  const circumference = radius * 2 * Math.PI;
  const offset = circumference - (progress / 100) * circumference;
  const strokeColor = color ?? 'var(--color-primary)';

  return (
    <div
      className="relative inline-flex items-center justify-center"
      style={{ width: size, height: size }}
    >
      <svg
        className="h-full w-full -rotate-90 transform"
        width={size}
        height={size}
        aria-label={`Progress: ${String(Math.round(progress))}%`}
      >
        <title>{`Progress: ${String(Math.round(progress))}%`}</title>
        <circle
          className="text-border-light dark:text-border-dark"
          strokeWidth={strokeWidth}
          stroke="currentColor"
          fill="transparent"
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
        <circle
          style={{
            stroke: strokeColor,
            strokeDasharray: circumference,
            strokeDashoffset: offset,
            transition: 'stroke-dashoffset 0.5s ease-in-out',
          }}
          className="drop-shadow-sm motion-reduce:transition-none"
          strokeWidth={strokeWidth}
          strokeLinecap="round"
          fill="transparent"
          r={radius}
          cx={size / 2}
          cy={size / 2}
        />
      </svg>
      <div
        className="absolute flex flex-col items-center justify-center gap-0.5 text-xs font-semibold text-primary dark:text-primary-200"
        style={color ? { color: strokeColor } : undefined}
      >
        {progress >= 100 ? <CheckCircle2 size={14} /> : <Target size={14} />}
        {Math.round(progress)}%
      </div>
    </div>
  );
};
