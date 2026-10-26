'use client';

/* ─── Mountain-curve SVG connector between day cards ─────────────────────── */
export function MountainConnector({
  fromLeft,
  completed,
}: {
  fromLeft: boolean;
  completed: boolean;
}) {
  // Cubic bezier swooping from one side to the other
  const d = fromLeft ? 'M 160,5 C 160,65 340,55 340,115' : 'M 340,5 C 340,65 160,55 160,115';

  // Decorative terrain slash-marks scattered around the curve
  const marks: [number, number, number][] = fromLeft
    ? [
        [210, 28, 35],
        [185, 52, -25],
        [240, 60, 42],
        [275, 70, -20],
        [310, 82, 30],
        [330, 44, -35],
      ]
    : [
        [290, 28, -35],
        [315, 52, 25],
        [260, 60, -42],
        [225, 70, 20],
        [190, 82, -30],
        [170, 44, 35],
      ];

  return (
    <div
      className={`w-full select-none pointer-events-none ${
        completed ? 'text-primary/30' : 'text-muted-foreground/20'
      }`}
    >
      <svg viewBox="0 0 500 120" className="w-full h-[100px]" preserveAspectRatio="xMidYMid meet">
        {/* Main curved dashed line */}
        <path
          d={d}
          fill="none"
          stroke="currentColor"
          strokeWidth="2.5"
          strokeDasharray="10 7"
          strokeLinecap="round"
        />
        {/* Terrain hash marks */}
        {marks.map(([mx, my, angle], idx) => {
          const a = (angle * Math.PI) / 180;
          const len = 9;
          return (
            <line
              key={idx}
              x1={mx - len * Math.cos(a)}
              y1={my - len * Math.sin(a)}
              x2={mx + len * Math.cos(a)}
              y2={my + len * Math.sin(a)}
              stroke="currentColor"
              strokeWidth="1.5"
              strokeLinecap="round"
              opacity="0.7"
            />
          );
        })}
      </svg>
    </div>
  );
}
