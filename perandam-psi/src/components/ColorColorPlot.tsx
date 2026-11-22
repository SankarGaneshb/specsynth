import React, { useState } from 'react';
import { Galaxy } from '../types/galaxy';

interface ColorColorPlotProps {
  allGalaxies: Galaxy[];
  selectedGalaxy: Galaxy;
  currentZ: number;
  currentAv: number;
}

export const ColorColorPlot: React.FC<ColorColorPlotProps> = ({
  allGalaxies,
  selectedGalaxy,
  currentZ,
  currentAv,
}) => {
  const [hoveredPoint, setHoveredPoint] = useState<{ x: number; y: number; label: string } | null>(null);

  // Define colors: X = (F200W - F277W), Y = (F150W - F444W)
  const getColors = (g: Galaxy, z: number, av: number) => {
    // Base fluxes
    const origF150 = g.fluxes['jwst_f150w'] || 1e-32;
    const origF200 = g.fluxes['jwst_f200w'] || 1e-32;
    const origF277 = g.fluxes['jwst_f277w'] || 1e-32;
    const origF444 = g.fluxes['jwst_f444w'] || 1e-32;

    const deltaAv = av - g.av;

    // Attenuation factors for each band at redshift z
    const tauFactor = (w_piv: number) => {
      const rest_w = w_piv / (1.0 + z);
      return Math.exp(-((deltaAv / 1.086) * Math.pow(rest_w / 5500.0, -0.7)));
    };

    const f150 = origF150 * tauFactor(15000);
    const f200 = origF200 * tauFactor(20000);
    const f277 = origF277 * tauFactor(27700);
    const f444 = origF444 * tauFactor(44400);

    const m150 = -2.5 * Math.log10(Math.max(1e-35, f150)) - 48.60;
    const m200 = -2.5 * Math.log10(Math.max(1e-35, f200)) - 48.60;
    const m277 = -2.5 * Math.log10(Math.max(1e-35, f277)) - 48.60;
    const m444 = -2.5 * Math.log10(Math.max(1e-35, f444)) - 48.60;

    const colorX = m200 - m277; // F200W - F277W
    const colorY = m150 - m444; // F150W - F444W
    return { colorX, colorY };
  };

  // Dimensions & Scale (AB color ranges: X ∈ [-1.0, 2.5], Y ∈ [-1.0, 4.0])
  const svgWidth = 440;
  const svgHeight = 260;
  const padding = { top: 30, right: 25, bottom: 42, left: 52 };

  const plotWidth = svgWidth - padding.left - padding.right;
  const plotHeight = svgHeight - padding.top - padding.bottom;

  const minX = -0.8;
  const maxX = 2.2;
  const minY = -0.5;
  const maxY = 3.8;

  const toScreenX = (val: number) =>
    padding.left + ((val - minX) / (maxX - minX)) * plotWidth;

  // In astronomy CMDs, Y is usually plotted normal or inverted. Here, redder (higher color index) goes up
  const toScreenY = (val: number) =>
    padding.top + plotHeight - ((val - minY) / (maxY - minY)) * plotHeight;

  // Current active galaxy position
  const activePos = getColors(selectedGalaxy, currentZ, currentAv);
  const activeScreenX = toScreenX(activePos.colorX);
  const activeScreenY = toScreenY(activePos.colorY);

  // Compute Redshift Evolutionary Track (z from 0.2 to 8.5)
  const zSamples = [0.2, 0.5, 0.8, 1.2, 1.6, 2.0, 2.5, 3.0, 3.5, 4.2, 5.0, 6.0, 7.0, 8.2];
  const trackPoints = zSamples.map((z) => {
    const pt = getColors(selectedGalaxy, z, selectedGalaxy.av);
    return {
      z,
      x: toScreenX(pt.colorX),
      y: toScreenY(pt.colorY),
      colorX: pt.colorX,
      colorY: pt.colorY,
    };
  });

  const trackPathD = trackPoints.reduce((acc, pt, idx) => {
    return idx === 0 ? `M ${pt.x} ${pt.y}` : `${acc} L ${pt.x} ${pt.y}`;
  }, '');

  // Dust Reddening Vector (Av = +1.0 mag arrow starting from reference point)
  const refVecPt = { colorX: 0.2, colorY: 0.5 };
  const refVecEnd = { colorX: refVecPt.colorX + 0.35, colorY: refVecPt.colorY + 0.85 };
  const vecStart = { x: toScreenX(refVecPt.colorX), y: toScreenY(refVecPt.colorY) };
  const vecEnd = { x: toScreenX(refVecEnd.colorX), y: toScreenY(refVecEnd.colorY) };

  return (
    <div className="relative w-full bg-cosmos-950/80 rounded-xl border border-cosmos-800 p-3 select-none">
      {/* Title & Methodology Badge */}
      <div className="flex items-center justify-between mb-2">
        <div className="flex items-center space-x-2">
          <span className="text-xs font-semibold text-slate-200">Color-Color Space (JOSS Fig. 3 Track)</span>
          <span className="text-[10px] font-mono px-2 py-0.5 rounded bg-indigo-950/80 text-indigo-300 border border-indigo-800/60">
            F150W-F444W vs F200W-F277W
          </span>
        </div>
        <span className="text-[10px] text-amber-400 font-mono">
          z: {currentZ.toFixed(2)} • Av: {currentAv.toFixed(2)}
        </span>
      </div>

      <svg viewBox={`0 0 ${svgWidth} ${svgHeight}`} className="w-full h-auto overflow-visible">
        {/* Grid lines */}
        {[-0.5, 0.0, 0.5, 1.0, 1.5, 2.0].map((xVal) => (
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

        {[0.0, 1.0, 2.0, 3.0].map((yVal) => (
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

        {/* Population Scatter (Background IllustrisTNG Sample) */}
        {allGalaxies.map((g) => {
          const pt = getColors(g, g.redshift, g.av);
          const px = toScreenX(pt.colorX);
          const py = toScreenY(pt.colorY);
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

        {/* Track Milestone Redshift Waypoint Dots */}
        {trackPoints.map((pt, idx) => (
          <g key={`wp-${idx}`}>
            <circle
              cx={pt.x}
              cy={pt.y}
              r={2.2}
              fill="#c7d2fe"
              stroke="#4338ca"
              strokeWidth={1}
            />
            {[0.5, 2.0, 5.0, 8.0].some((target) => Math.abs(pt.z - target) < 0.25) && (
              <text
                x={pt.x + 4}
                y={pt.y - 3}
                fill="#a5b4fc"
                fontSize="7.5"
                fontFamily="monospace"
                fontWeight="bold"
              >
                z={pt.z.toFixed(1)}
              </text>
            )}
          </g>
        ))}

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

        {/* Active Galaxy Highlight Marker */}
        <circle
          cx={activeScreenX}
          cy={activeScreenY}
          r={7}
          fill="#f59e0b"
          fillOpacity={0.3}
          stroke="#f59e0b"
          strokeWidth={2}
          className="animate-ping"
        />
        <circle
          cx={activeScreenX}
          cy={activeScreenY}
          r={5}
          fill="#fbbf24"
          stroke="#ffffff"
          strokeWidth={1.8}
        />

        {/* Axis Labels */}
        <text
          x={padding.left + plotWidth / 2}
          y={svgHeight - 6}
          fill="#94a3b8"
          fontSize="10"
          textAnchor="middle"
          fontWeight="bold"
        >
          JWST (F200W - F277W) [AB mag]
        </text>

        <text
          x={16}
          y={padding.top + plotHeight / 2}
          fill="#94a3b8"
          fontSize="10"
          textAnchor="middle"
          fontWeight="bold"
          transform={`rotate(-90, 16, ${padding.top + plotHeight / 2})`}
        >
          JWST (F150W - F444W) [AB mag]
        </text>
      </svg>

      {/* Real-time Trajectory Status Footer */}
      <div className="mt-1 flex items-center justify-between text-[11px] text-slate-300 font-mono bg-cosmos-900/90 rounded px-2.5 py-1 border border-cosmos-800">
        <div className="flex items-center space-x-2 text-[10px]">
          <span className="w-2 h-2 rounded-full bg-amber-400" />
          <span>Active Position: ({activePos.colorX.toFixed(2)}, {activePos.colorY.toFixed(2)})</span>
        </div>
        <span className="text-[10px] text-indigo-300">
          Dotted curve = Redshift trajectory z ∈ [0.2, 8.5]
        </span>
      </div>
    </div>
  );
};
