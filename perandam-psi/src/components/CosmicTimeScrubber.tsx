import React, { useState, useEffect, useRef } from 'react';
import {
  Play,
  Pause,
  RotateCcw,
  Clock,
  Sparkles,
  ChevronUp,
  ChevronDown,
  Layers,
  Calendar,
} from 'lucide-react';
import { lookbackTimeGyr, COSMIC_EPOCHS } from '../utils/cosmo3d';
import { comovingDistanceMpc } from '../utils/physics';

interface CosmicTimeScrubberProps {
  currentRedshift: number;
  onRedshiftChange: (z: number) => void;
  minZ?: number;
  maxZ?: number;
}

export const CosmicTimeScrubber: React.FC<CosmicTimeScrubberProps> = ({
  currentRedshift,
  onRedshiftChange,
  minZ = 0.0,
  maxZ = 8.5,
}) => {
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [isCollapsed, setIsCollapsed] = useState<boolean>(false);
  const animRef = useRef<number | null>(null);

  const lookbackGyr = lookbackTimeGyr(currentRedshift);
  // Total age at z=0 is ~13.8 Gyr in Flat Lambda-CDM
  const cosmicAgeGyr = Math.max(0.4, 13.803 - lookbackGyr);
  const comovMpc = comovingDistanceMpc(currentRedshift);
  const scaleFactorA = 1.0 / (1.0 + currentRedshift);

  // Play animation loop (scrubbing forward in time: from high-z down to z=0, or cycling)
  useEffect(() => {
    if (!isPlaying) {
      if (animRef.current) cancelAnimationFrame(animRef.current);
      return;
    }

    let lastTime = performance.now();
    const step = (now: number) => {
      const dt = (now - lastTime) / 1000;
      lastTime = now;

      // Advance time towards present day (decreasing z), then loop back
      let nextZ = currentRedshift - dt * 0.45;
      if (nextZ < minZ) {
        nextZ = maxZ; // Loop back to cosmic dawn
      }
      onRedshiftChange(Number(nextZ.toFixed(2)));

      animRef.current = requestAnimationFrame(step);
    };

    animRef.current = requestAnimationFrame(step);
    return () => {
      if (animRef.current) cancelAnimationFrame(animRef.current);
    };
  }, [isPlaying, currentRedshift, minZ, maxZ, onRedshiftChange]);

  return (
    <div className="absolute bottom-4 left-1/2 transform -translate-x-1/2 z-20 w-[94%] max-w-4xl bg-cosmos-950/95 border border-cosmos-700/80 rounded-2xl shadow-2xl backdrop-blur-md text-xs text-slate-200 transition-all select-none">
      {/* Header Bar */}
      <div className="flex items-center justify-between px-4 py-2 border-b border-cosmos-800/80">
        <div className="flex items-center space-x-2">
          <Clock className="w-4 h-4 text-cyan-400" />
          <span className="font-semibold text-cyan-300">Cosmic Time Scrubber</span>
          <span className="text-[10px] px-1.5 py-0.5 rounded bg-cyan-950/80 border border-cyan-800/60 text-cyan-300 font-mono">
            Flat ΛCDM FLRW
          </span>
        </div>

        {/* Quick Readout */}
        <div className="flex items-center space-x-3 text-xs font-mono">
          <div>
            <span className="text-slate-500">Redshift: </span>
            <span className="font-bold text-amber-300">z = {currentRedshift.toFixed(2)}</span>
          </div>
          <div className="hidden sm:inline">
            <span className="text-slate-500">Lookback: </span>
            <span className="font-bold text-cyan-300">~{lookbackGyr.toFixed(2)} Gyr</span>
          </div>
          <div className="hidden md:inline">
            <span className="text-slate-500">Cosmic Age: </span>
            <span className="font-bold text-slate-200">{cosmicAgeGyr.toFixed(2)} Gyr</span>
          </div>

          <button
            onClick={() => setIsCollapsed((prev) => !prev)}
            className="p-1 rounded hover:bg-cosmos-800 text-slate-400 hover:text-slate-200 transition-colors"
            title={isCollapsed ? "Expand scrubber controls" : "Collapse scrubber controls"}
          >
            {isCollapsed ? <ChevronUp className="w-4 h-4 text-cyan-400" /> : <ChevronDown className="w-4 h-4" />}
          </button>
        </div>
      </div>

      {/* Expanded Controls */}
      {!isCollapsed && (
        <div className="p-3.5 space-y-3">
          {/* Main Slider & Play Button */}
          <div className="flex items-center space-x-3">
            <button
              onClick={() => setIsPlaying((prev) => !prev)}
              className={`p-2 rounded-xl flex items-center justify-center transition-all shadow-md ${
                isPlaying
                  ? 'bg-amber-600 hover:bg-amber-500 text-slate-950'
                  : 'bg-cyan-600 hover:bg-cyan-500 text-slate-950'
              }`}
              title={isPlaying ? "Pause time-lapse" : "Play forward cosmic evolution"}
            >
              {isPlaying ? <Pause className="w-4 h-4 fill-current" /> : <Play className="w-4 h-4 fill-current ml-0.5" />}
            </button>

            <button
              onClick={() => {
                setIsPlaying(false);
                onRedshiftChange(0.0);
              }}
              className="p-2 rounded-xl bg-cosmos-800 hover:bg-cosmos-700 text-slate-300 hover:text-slate-100 transition-colors border border-cosmos-700/60"
              title="Reset to Present Day (z = 0)"
            >
              <RotateCcw className="w-4 h-4" />
            </button>

            {/* Redshift Slider with High-z on Right, Present Day on Left */}
            <div className="flex-1 relative">
              <input
                type="range"
                min={minZ}
                max={maxZ}
                step="0.05"
                value={currentRedshift}
                onChange={(e) => {
                  setIsPlaying(false);
                  onRedshiftChange(Number(e.target.value));
                }}
                className="w-full h-2 bg-cosmos-800 rounded-lg appearance-none cursor-pointer accent-cyan-400"
              />
              <div className="flex justify-between text-[10px] text-slate-500 font-mono mt-1">
                <span>Present Day (z = 0)</span>
                <span className="hidden sm:inline">Expansion (z = 1)</span>
                <span>Cosmic Noon (z = 2)</span>
                <span className="hidden sm:inline">Reionization (z = 6)</span>
                <span>Cosmic Dawn (z = 8.5)</span>
              </div>
            </div>
          </div>

          {/* Canonical Epoch Jump Buttons */}
          <div className="flex flex-wrap items-center gap-1.5 pt-1 border-t border-cosmos-800/60">
            <span className="text-[10px] text-slate-500 font-medium mr-1 hidden sm:inline">Jump to Epoch:</span>
            {COSMIC_EPOCHS.map((epoch) => {
              const isActive = Math.abs(currentRedshift - epoch.z) < 0.25;
              return (
                <button
                  key={`epoch-btn-${epoch.z}`}
                  onClick={() => {
                    setIsPlaying(false);
                    onRedshiftChange(epoch.z);
                  }}
                  className={`px-2 py-0.5 rounded-lg text-[10px] font-mono transition-all border ${
                    isActive
                      ? 'bg-cyan-950 border-cyan-500 text-cyan-200 font-bold shadow-sm'
                      : 'bg-cosmos-900 border-cosmos-700/60 text-slate-400 hover:bg-cosmos-800 hover:text-slate-200'
                  }`}
                  title={epoch.description}
                >
                  {epoch.label}
                </button>
              );
            })}
          </div>

          {/* Synchronized Metrics Grid */}
          <div className="grid grid-cols-2 sm:grid-cols-4 gap-2 pt-1 border-t border-cosmos-800/60 text-[11px] font-mono">
            <div className="bg-cosmos-900/60 p-1.5 rounded-lg border border-cosmos-800/40">
              <div className="text-slate-500 text-[10px]">Universe Scale a</div>
              <div className="font-bold text-slate-200">{scaleFactorA.toFixed(3)}</div>
              <div className="text-[10px] text-slate-500">{(scaleFactorA * 100).toFixed(1)}% of Today</div>
            </div>
            <div className="bg-cosmos-900/60 p-1.5 rounded-lg border border-cosmos-800/40">
              <div className="text-slate-500 text-[10px]">Lookback Time</div>
              <div className="font-bold text-cyan-300">~{lookbackGyr.toFixed(2)} Gyr</div>
              <div className="text-[10px] text-slate-500">{((lookbackGyr / 13.803) * 100).toFixed(1)}% Cosmic Past</div>
            </div>
            <div className="bg-cosmos-900/60 p-1.5 rounded-lg border border-cosmos-800/40">
              <div className="text-slate-500 text-[10px]">Universe Age</div>
              <div className="font-bold text-emerald-400">{cosmicAgeGyr.toFixed(2)} Gyr</div>
              <div className="text-[10px] text-slate-500">Since Big Bang</div>
            </div>
            <div className="bg-cosmos-900/60 p-1.5 rounded-lg border border-cosmos-800/40">
              <div className="text-slate-500 text-[10px]">Comoving Distance</div>
              <div className="font-bold text-amber-300">{comovMpc.toFixed(0)} Mpc</div>
              <div className="text-[10px] text-slate-500">{(comovMpc * 3.26e6 / 1e9).toFixed(2)} Gly</div>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};
