import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { SkyCanvas } from './components/SkyCanvas';
import { MilkyWayComparator3D } from './components/MilkyWayComparator3D';
import { LightconeCanvas3D } from './components/LightconeCanvas3D';
import { CosmicTimeScrubber } from './components/CosmicTimeScrubber';
import { GalaxyInspector } from './components/GalaxyInspector';
import { GuideModal } from './components/GuideModal';
import { Galaxy, CatalogManifest, SkyColorMode, ViewportMode } from './types/galaxy';
import rawGoodsSManifest from './data/tng_goods_s_mock_508.json';
import rawTng100Manifest from './data/tng_100_calibration.json';
import customGalaxiesData from './data/custom_galaxies.json';
import { Sparkles, Layers, Box } from 'lucide-react';

export type DatasetId = 'goods_s_mock' | 'tng_100';

const DATASETS: Record<DatasetId, CatalogManifest> = {
  goods_s_mock: rawGoodsSManifest as unknown as CatalogManifest,
  tng_100: rawTng100Manifest as unknown as CatalogManifest,
};

const customGalaxies: Galaxy[] = ((customGalaxiesData as any)?.galaxies || []) as Galaxy[];

export const App: React.FC = () => {
  const [datasetId, setDatasetId] = useState<DatasetId>('goods_s_mock');
  const manifest = DATASETS[datasetId];
  const [galaxies, setGalaxies] = useState<Galaxy[]>(() => [
    ...customGalaxies.map((g) => ({ ...g })),
    ...manifest.galaxies.map((g) => ({ ...g }))
  ]);
  const [selectedGalaxy, setSelectedGalaxy] = useState<Galaxy | null>(null);
  const [resetTrigger, setResetTrigger] = useState<number>(0);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isGuideOpen, setIsGuideOpen] = useState<boolean>(false);
  const [colorMode, setColorMode] = useState<SkyColorMode>('rgb');
  const [viewportMode, setViewportMode] = useState<ViewportMode>('2d');
  const [previousViewportMode, setPreviousViewportMode] = useState<ViewportMode>('3d');
  const [discoveryMode, setDiscoveryMode] = useState<boolean>(false);
  const [scrubberZ, setScrubberZ] = useState<number>(0.0);

  const handleViewportChange = (newMode: ViewportMode) => {
    if (newMode !== viewportMode) {
      if (viewportMode !== 'twin') {
        setPreviousViewportMode(viewportMode);
      }
      setViewportMode(newMode);
    }
  };

  // Switch active dataset
  const handleSwitchDataset = (newId: DatasetId) => {
    setDatasetId(newId);
    setGalaxies([
      ...customGalaxies.map((g) => ({ ...g })),
      ...DATASETS[newId].galaxies.map((g) => ({ ...g }))
    ]);
    setSelectedGalaxy(null);
    setResetTrigger((prev) => prev + 1);
  };

  // Check connection to local SpecSynth HTTP bridge (localhost:8000)
  useEffect(() => {
    const checkConnection = async () => {
      try {
        const res = await fetch('http://127.0.0.1:8000/api/health', { method: 'GET' });
        if (res.ok) {
          setIsConnected(true);
        } else {
          setIsConnected(false);
        }
      } catch {
        setIsConnected(false);
      }
    };

    checkConnection();
    const interval = setInterval(checkConnection, 5000);
    return () => clearInterval(interval);
  }, []);

  // Keyboard shortcut: Escape closes the inspector
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        setSelectedGalaxy(null);
      }
    };
    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, []);

  const handleSelectGalaxy = (galaxy: Galaxy | null) => {
    setSelectedGalaxy(galaxy);
    if (galaxy && typeof galaxy.redshift === 'number') {
      setScrubberZ(galaxy.redshift);
    }
  };

  const handleScrubberChange = (newZ: number) => {
    setScrubberZ(newZ);
    if (selectedGalaxy) {
      handleUpdateGalaxy({
        ...selectedGalaxy,
        redshift: newZ,
      });
    } else if (galaxies.length > 0) {
      // Find closest galaxy to this redshift so the right side is visible and active
      let closest = galaxies[0];
      let minDiff = Math.abs((galaxies[0].redshift ?? 0) - newZ);
      for (let i = 1; i < galaxies.length; i++) {
        const diff = Math.abs((galaxies[i].redshift ?? 0) - newZ);
        if (diff < minDiff) {
          minDiff = diff;
          closest = galaxies[i];
        }
      }
      if (closest && minDiff < 1.2) {
        setSelectedGalaxy(closest);
      }
    }
  };

  const handleSelectById = (id: string) => {
    const found = galaxies.find((g) => g.id === id);
    if (found) {
      handleSelectGalaxy(found);
    }
  };

  const handleUpdateGalaxy = (updated: Galaxy) => {
    setGalaxies((prev) => prev.map((g) => (g.id === updated.id ? updated : g)));
    setSelectedGalaxy(updated);
  };

  return (
    <div className="w-screen h-screen flex flex-col bg-cosmos-950 text-slate-100 overflow-hidden font-sans">
      {/* Top Navbar */}
      <Navbar
        nGalaxies={galaxies.length}
        selectedId={selectedGalaxy?.id || null}
        isConnected={isConnected}
        colorMode={colorMode}
        onChangeColorMode={setColorMode}
        viewportMode={viewportMode}
        onToggleViewportMode={() => handleViewportChange(viewportMode === 'twin' ? '2d' : 'twin')}
        onChangeViewportMode={handleViewportChange}
        onResetView={() => setResetTrigger((prev) => prev + 1)}
        onSelectGalaxy={handleSelectById}
        onOpenGuide={() => setIsGuideOpen(true)}
        galaxies={galaxies}
        discoveryMode={discoveryMode}
        onToggleDiscoveryMode={() => setDiscoveryMode((prev) => !prev)}
        datasetId={datasetId}
        onSwitchDataset={handleSwitchDataset}
      />

      {/* Beginner & Student Guide Modal */}
      <GuideModal isOpen={isGuideOpen} onClose={() => setIsGuideOpen(false)} />

      {/* Main Sky & Inspector Area: Persistent Viewports (Zero WebGL Context Churn) */}
      <div className="flex-1 relative flex overflow-hidden">
        {/* 3D Galaxy Stage (Milky Way Comparator) */}
        <div className={`flex-1 h-full relative ${viewportMode === 'twin' ? 'block' : 'hidden'}`}>
          <MilkyWayComparator3D
            galaxy={selectedGalaxy || galaxies[0]}
            allGalaxies={galaxies}
            onSelectGalaxy={(g) => handleSelectGalaxy(g)}
            onClose={() => handleViewportChange(previousViewportMode)}
            onCloseLabel={previousViewportMode === '3d' ? 'Back to 3D Lightcone' : 'Back to 2D Sky'}
            isActive={viewportMode === 'twin'}
          />
        </div>

        {/* 3D Cosmological Lightcone Canvas & Progenitor Trajectories */}
        <div className={`flex-1 h-full relative ${viewportMode === '3d' ? 'block' : 'hidden'}`}>
          <LightconeCanvas3D
            galaxies={galaxies}
            selectedGalaxy={selectedGalaxy}
            onSelectGalaxy={handleSelectGalaxy}
            centerRa={manifest.field_center.ra}
            centerDec={manifest.field_center.dec}
            fieldRadius={manifest.field_center.radius_deg}
            resetTrigger={resetTrigger}
            colorMode={colorMode}
            discoveryMode={discoveryMode}
            scrubberZ={scrubberZ}
            onScrubberChange={handleScrubberChange}
            isActive={viewportMode === '3d'}
          />
          <CosmicTimeScrubber
            currentRedshift={scrubberZ}
            onRedshiftChange={handleScrubberChange}
            minZ={0.0}
            maxZ={8.5}
          />
        </div>

        {/* 2D Projected Sky Canvas */}
        <div className={`flex-1 h-full relative ${viewportMode === '2d' ? 'block' : 'hidden'}`}>
          <SkyCanvas
            galaxies={galaxies}
            selectedGalaxy={selectedGalaxy}
            onSelectGalaxy={handleSelectGalaxy}
            centerRa={manifest.field_center.ra}
            centerDec={manifest.field_center.dec}
            fieldRadius={manifest.field_center.radius_deg}
            resetTrigger={resetTrigger}
            colorMode={colorMode}
            discoveryMode={discoveryMode}
            isActive={viewportMode === '2d'}
          />

          {/* Floating Field Summary Badge (Bottom Left) */}
          <div className="absolute bottom-4 left-4 z-10 flex items-center space-x-2 bg-cosmos-900/90 border border-cosmos-800 backdrop-blur px-3 py-1.5 rounded-lg text-xs shadow-lg pointer-events-none font-mono">
            <Layers className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-slate-300 font-semibold font-sans">
              {datasetId === 'goods_s_mock' ? 'GOODS-S Deep Mock' : 'TNG-100 Calibration'}
            </span>
            <span className="text-slate-500">•</span>
            <span className="text-slate-400">
              RA {manifest.field_center.ra.toFixed(2)}°, Dec {manifest.field_center.dec.toFixed(2)}°
            </span>
            <span className="text-slate-500">•</span>
            <span className="text-amber-400 font-bold">{galaxies.length} galaxies</span>
          </div>
        </div>

        {/* Slide-over Galaxy Inspector */}
        {selectedGalaxy && viewportMode !== 'twin' && (
          <GalaxyInspector
            galaxy={selectedGalaxy}
            allGalaxies={galaxies}
            filters={manifest.filters}
            onClose={() => setSelectedGalaxy(null)}
            onUpdateGalaxy={handleUpdateGalaxy}
            onOpenGalaxyTwin={() => handleViewportChange('twin')}
            externalZ={scrubberZ}
            onExternalZChange={handleScrubberChange}
          />
        )}
      </div>
    </div>
  );
};

export default App;
