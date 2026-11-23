import React, { useMemo } from 'react';
import { Galaxy, FilterCurveData } from '../types/galaxy';
import { forwardModelGalaxy } from '../utils/physics';

interface ColorColorPlotProps {
  allGalaxies: Galaxy[];
  selectedGalaxy: Galaxy;
  currentZ: number;
  currentAv: number;
  filters: FilterCurveData[];
}

export const ColorColorPlot: React.FC<ColorColorPlotProps> = ({
  allGalaxies,
  selectedGalaxy,
  currentZ,
  currentAv,
  filters,
}) => {
  // Compute active galaxy position using full in-flight forward model
  const activeModel = useMemo(() => {
    return forwardModelGalaxy(
      selectedGalaxy.sed,
      selectedGalaxy.redshift,
      currentZ,
      selectedGalaxy.av,
      currentAv,
      filters
    );
  }, [selectedGalaxy, currentZ, currentAv, filters]);

  const activeColorX = Number(
    ((activeModel.mags['jwst_f200w'] ?? 26.0) - (activeModel.mags['jwst_f277w'] ?? 26.0)).toFixed(2)
  );
  const activeColorY = Number(
    ((activeModel.mags['jwst_f150w'] ?? 26.0) - (activeModel.mags['jwst_f444w'] ?? 26.0)).toFixed(2)
  );

  // Compute Redshift Evolutionary Track across z in [0.2, 8.5] using the forward model
  const zTrackSteps = [0.2, 0.5, 0.8, 1.2, 1.6, 2.0, 2.5, 3.0, 3.8, 4.8, 6.0, 7.2, 8.5];
  const trackData = useMemo(() => {
    return zTrackSteps.map((zVal) => {
      const model = forwardModelGalaxy(
        selectedGalaxy.sed,
        selectedGalaxy.redshift,
        zVal,
        selectedGalaxy.av,
        selectedGalaxy.av,
        filters
      );
      const cx = (model.mags['jwst_f200w'] ?? 26.0) - (model.mags['jwst_f277w'] ?? 26.0);
      const cy = (model.mags['jwst_f150w'] ?? 26.0) - (model.mags['jwst_f444w'] ?? 26.0);
      return { z: zVal, colorX: Number(cx.toFixed(2)), colorY: Number(cy.toFixed(2)) };
    });
  }, [selectedGalaxy, filters]);

  // Adaptive bounds ensuring active galaxy and full track are enclosed
  const allX = [activeColorX, ...trackData.map((t) => t.colorX)];
  const allY = [activeColorY, ...trackData.map((t) => t.colorY)];
  const minX = Math.min(-1.5, Math.floor(Math.min(...allX) - 0.5));
  const maxX = Math.max(2.5, Math.ceil(Math.max(...allX) + 0.5));
  const minY = Math.min(-3.5, Math.floor(Math.min(...allY) - 0.5));
  const maxY = Math.max(4.0, Math.ceil(Math.max(...allY) + 0.5));

  // Dimensions
  const svgWidth = 440;
  const svgHeight = 240;
  const padding = { top: 22, right: 18, bottom: 42, left: 52 };

  const plotWidth = svgWidth - padding.left - padding.right;
  const plotHeight = svgHeight - padding.top - padding.bottom;

  const toScreenX = (val: number) => padding.left + ((val - minX) / (maxX - minX)) * plotWidth;
  const toScreenY = (val: number) => padding.top + plotHeight - ((val - minY) / (maxY - minY)) * plotHeight;

  const activeScreenX = toScreenX(activeColorX);
  const activeScreenY = toScreenY(activeColorY);

  // Axis ticks
  const xTicks: number[] = [];
  const xStep = maxX - minX > 5 ? 1.0 : 0.5;
  for (let v = Math.ceil(minX / xStep) * xStep; v <= maxX; v += xStep) {
    xTicks.push(Math.round(v * 10) / 10);
  }

  const yTicks: number[] = [];
  const yStep = maxY - minY > 8 ? 2.0 : 1.0;
  for (let v = Math.ceil(minY / yStep) * yStep; v <= maxY; v += yStep) {
    yTicks.push(Math.round(v * 10) / 10);
  }

  // Track path
  const trackPathD = trackData.reduce((acc, pt, idx) => {
    const sx = toScreenX(pt.colorX);
    const sy = toScreenY(pt.colorY);
    return idx === 0 ? `M ${sx} ${sy}` : `${acc} L ${sx} ${sy}`;
  }, '');

  // Dust Reddening Vector (Av = +1.0 mag arrow starting from reference point)
  const refVecPt = { colorX: minX + 0.25 * (maxX - minX), colorY: minY + 0.65 * (maxY - minY) };
  const refVecEnd = { colorX: refVecPt.colorX + 0.35, colorY: refVecPt.colorY + 0.85 };
  const vecStart = { x: toScreenX(refVecPt.colorX), y: toScreenY(refVecPt.colorY) };
  const vecEnd = { x: toScreenX(refVecEnd.colorX), y: toScreenY(refVecEnd.colorY) };

  return (
    <div className="relative w-full bg-cosmos-950/80 rounded-xl border border-cosmos-800 p-3 select-none shadow-md">
      {/* Title & Methodology Badge */}
      <div className="mb-2.5">
        <div className="flex items-center justify-between">
          <div className="flex items-center space-x-2">
            <span className="text-sm font-bold text-slate-100">Color-Color Space (JOSS Fig. 3 Track)</span>
            <span className="text-xs text-indigo-300 font-mono bg-indigo-950/60 px-2 py-0.5 rounded border border-indigo-800/60">
              Forward Modeled
            </span>
          </div>
          <span className="text-xs text-amber-400 font-mono bg-cosmos-900/90 px-2 py-0.5 rounded border border-cosmos-800">
            z = {currentZ.toFixed(2)} • Av = {currentAv.toFixed(2)} mag
          </span>
        </div>
        <div className="text-xs font-mono text-indigo-300 mt-1 flex items-center space-x-1.5">
          <span className="w-1.5 h-1.5 rounded-full bg-indigo-400" />
          <span>F150W − F444W vs F200W − F277W</span>
        </div>
      </div>

      <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full h-auto overflow-hidden">
        <defs>
          <clipPath id="color-plot-clip">
            <rect x={padding.left} y={padding.top} width={plotWidth} height={plotHeight} />
          </clipPath>
        </defs>

        {/* Plot Background Area */}
        <rect
          x={padding.left}
          y={padding.top}
          width={plotWidth}
          height={plotHeight}
          fill="#090d1a"
          stroke="#1e293b"
          strokeWidth={1}
        />

        {/* Grid lines */}
        {xTicks.map((xVal) => (
          <g key={`grid-x-${xVal}`}>
            <line
              x1={toScreenX(xVal)}
              y1={padding.top}
              x2={toScreenX(xVal)}
              y2={padding.top + plotHeight}
              stroke="#1e293b"
              strokeDasharray="2,2"
            />
            <text
              x={toScreenX(xVal)}
              y={padding.top + plotHeight + 14}
              fill="#64748b"
              fontSize="9"
              textAnchor="middle"
              fontFamily="monospace"
            >
              {xVal.toFixed(1)}
            </text>
          </g>
        ))}

        {yTicks.map((yVal) => (
          <g key={`grid-y-${yVal}`}>
            <line
              x1={padding.left}
              y1={toScreenY(yVal)}
              x2={padding.left + plotWidth}
              y2={toScreenY(yVal)}
              stroke="#1e293b"
              strokeDasharray="2,2"
            />
            <text
              x={padding.left - 6}
              y={toScreenY(yVal) + 3}
              fill="#64748b"
              fontSize="9"
              textAnchor="end"
              fontFamily="monospace"
            >
              {yVal.toFixed(1)}
            </text>
          </g>
        ))}

        {/* Data Group clipped to chart boundaries */}
        <g clipPath="url(#color-plot-clip)">
          {/* Background population scatter points */}
          {allGalaxies.map((g) => {
            const m150 = g.mags['jwst_f150w'] ?? 26.0;
            const m200 = g.mags['jwst_f200w'] ?? 26.0;
            const m277 = g.mags['jwst_f277w'] ?? 26.0;
            const m444 = g.mags['jwst_f444w'] ?? 26.0;
            const px = toScreenX(m200 - m277);
            const py = toScreenY(m150 - m444);

            if (px < padding.left || px > padding.left + plotWidth || py < padding.top || py > padding.top + plotHeight) {
              return null;
            }
            return (
              <circle
                key={`pop-${g.id}`}
                cx={px}
                cy={py}
                r={1.8}
                fill="#334155"
                fillOpacity={0.45}
              />
            );
          })}

          {/* Evolutionary Redshift Trajectory Track */}
          <path
            d={trackPathD}
            fill="none"
            stroke="#4f46e5"
            strokeWidth={3}
            strokeOpacity={0.3}
          />
          <path
            d={trackPathD}
            fill="none"
            stroke="#818cf8"
            strokeWidth={1.8}
            strokeDasharray="3,2"
          />

          {/* Track Milestone Waypoints (Distinct diamond styling to prevent collision) */}
          {trackData.map((pt, idx) => {
            const sx = toScreenX(pt.colorX);
            const sy = toScreenY(pt.colorY);
            const isInside = sx >= padding.left && sx <= padding.left + plotWidth && sy >= padding.top && sy <= padding.top + plotHeight;
            if (!isInside) return null;

            const isMilestone = [0.5, 2.0, 5.0, 8.0].some((target) => Math.abs(pt.z - target) < 0.35);

            // Distance to active beacon to prevent visual label collision
            const distToActive = Math.hypot(sx - activeScreenX, sy - activeScreenY);
            const shouldShowLabel = isMilestone && distToActive > 24;

            return (
              <g key={`track-wp-${idx}`}>
                {/* Diamond waypoint marker */}
                <polygon
                  points={`${sx},${sy - 3} ${sx + 3},${sy} ${sx},${sy + 3} ${sx - 3},${sy}`}
                  fill="#c7d2fe"
                  stroke="#4338ca"
                  strokeWidth={1}
                />
                {shouldShowLabel && (
                  <text
                    x={sx + 5}
                    y={sy - 4}
                    fill="#94a3b8"
                    fontSize="7"
                    fontFamily="monospace"
                    fontWeight="bold"
                  >
                    Track: z={pt.z.toFixed(1)}
                  </text>
                )}
              </g>
            );
          })}

          {/* Dust Reddening Vector Arrow */}
          <g opacity={0.85}>
            <line
              x1={vecStart.x}
              y1={vecStart.y}
              x2={vecEnd.x}
              y2={vecEnd.y}
              stroke="#fb7185"
              strokeWidth={1.8}
            />
            <polygon
              points={`${vecEnd.x},${vecEnd.y} ${vecEnd.x - 5},${vecEnd.y + 2} ${vecEnd.x - 2},${vecEnd.y + 5}`}
              fill="#fb7185"
            />
            <text
              x={vecStart.x - 4}
              y={vecStart.y - 4}
              fill="#fb7185"
              fontSize="8"
              fontFamily="monospace"
              fontWeight="bold"
            >
              Av = +1.0
            </text>
          </g>

          {/* Active Target Galaxy Beacon (Unambiguous Target Reticle + Beacon) */}
          <g>
            {/* Outer pulsating reticle */}
            <circle
              cx={activeScreenX}
              cy={activeScreenY}
              r={9}
              fill="none"
              stroke="#f59e0b"
              strokeWidth={1.5}
              strokeDasharray="2,2"
              className="animate-spin"
            />
            {/* Pulsing glow */}
            <circle
              cx={activeScreenX}
              cy={activeScreenY}
              r={7}
              fill="#f59e0b"
              fillOpacity={0.3}
              stroke="#f59e0b"
              strokeWidth={2}
            />
            {/* Solid core dot */}
            <circle
              cx={activeScreenX}
              cy={activeScreenY}
              r={4}
              fill="#fbbf24"
              stroke="#ffffff"
              strokeWidth={1.5}
            />
            {/* Explicit Active Target Callout Tag */}
            <g transform={`translate(${activeScreenX + 8}, ${activeScreenY - 8})`}>
              <rect
                x={0}
                y={-10}
                width={86}
                height={14}
                rx={3}
                fill="#1e1b4b"
                stroke="#fbbf24"
                strokeWidth={0.8}
                fillOpacity={0.9}
              />
              <text
                x={4}
                y={0}
                fill="#fef08a"
                fontSize="7.5"
                fontFamily="monospace"
                fontWeight="bold"
              >
                Target: z={currentZ.toFixed(2)}
              </text>
            </g>
          </g>
        </g>

        {/* Axis Labels */}
        <text
          x={padding.left + plotWidth / 2}
          y={svgHeight - 6}
          fill="#94a3b8"
          fontSize="11"
          textAnchor="middle"
          fontWeight="bold"
        >
          JWST (F200W - F277W) [AB mag]
        </text>

        <text
          x={14}
          y={padding.top + plotHeight / 2}
          fill="#94a3b8"
          fontSize="11"
          textAnchor="middle"
          fontWeight="bold"
          transform={`rotate(-90, 14, ${padding.top + plotHeight / 2})`}
        >
          JWST (F150W - F444W) [AB mag]
        </text>
      </svg>

      {/* Real-time Trajectory Status Footer */}
      <div className="mt-1 flex items-center justify-between text-xs text-slate-200 font-mono bg-cosmos-900/90 rounded px-3 py-1.5 border border-cosmos-800 shadow-sm">
        <div className="flex items-center space-x-2 text-xs font-semibold">
          <span className="w-2.5 h-2.5 rounded-full bg-amber-400 animate-pulse" />
          <span>Active Position: ({activeColorX.toFixed(2)}, {activeColorY.toFixed(2)})</span>
        </div>
        <span className="text-xs text-indigo-300">
          Dotted curve = Redshift trajectory z ∈ [0.2, 8.5]
        </span>
      </div>
    </div>
  );
};
