import React, { useState, useEffect } from 'react';
import { Navbar } from './components/Navbar';
import { SkyCanvas } from './components/SkyCanvas';
import { GalaxyInspector } from './components/GalaxyInspector';
import { GuideModal } from './components/GuideModal';
import { Galaxy, CatalogManifest } from './types/galaxy';
import rawManifest from './data/tng_jwst_deep_field.json';
import { Sparkles } from 'lucide-react';

const manifest = rawManifest as unknown as CatalogManifest;

export const App: React.FC = () => {
  const [galaxies, setGalaxies] = useState<Galaxy[]>(manifest.galaxies);
  const [selectedGalaxy, setSelectedGalaxy] = useState<Galaxy | null>(null);
  const [resetTrigger, setResetTrigger] = useState<number>(0);
  const [isConnected, setIsConnected] = useState<boolean>(false);
  const [isGuideOpen, setIsGuideOpen] = useState<boolean>(false);

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

  const handleSelectById = (id: string) => {
    const found = galaxies.find((g) => g.id === id);
    if (found) {
      setSelectedGalaxy(found);
    }
  };

  const handleUpdateGalaxy = (updated: Galaxy) => {
    setGalaxies((prev) => prev.map((g) => (g.id === updated.id ? updated : g)));
  };

  const galaxyIds = manifest.galaxies.map((g) => g.id);

  return (
    <div className="w-screen h-screen flex flex-col bg-cosmos-950 text-slate-100 overflow-hidden font-sans">
      {/* Top Navbar */}
      <Navbar
        nGalaxies={galaxies.length}
        selectedId={selectedGalaxy?.id || null}
        isConnected={isConnected}
        onResetView={() => setResetTrigger((prev) => prev + 1)}
        onSelectGalaxy={handleSelectById}
        onOpenGuide={() => setIsGuideOpen(true)}
        galaxiesList={galaxyIds}
      />

      {/* Beginner & Student Guide Modal */}
      <GuideModal isOpen={isGuideOpen} onClose={() => setIsGuideOpen(false)} />

      {/* Main Sky & Inspector Area */}
      <div className="flex-1 relative flex overflow-hidden">
        {/* Interactive Sky Canvas */}
        <div className="flex-1 h-full relative">
          <SkyCanvas
            galaxies={galaxies}
            selectedGalaxy={selectedGalaxy}
            onSelectGalaxy={setSelectedGalaxy}
            centerRa={manifest.field_center.ra}
            centerDec={manifest.field_center.dec}
            fieldRadius={manifest.field_center.radius_deg}
            resetTrigger={resetTrigger}
          />

          {/* Floating Field Summary Badge (Bottom Left) */}
          <div className="absolute bottom-4 left-4 z-10 flex items-center space-x-2 bg-cosmos-900/90 border border-cosmos-800 backdrop-blur px-3 py-1.5 rounded-lg text-xs shadow-lg pointer-events-none">
            <Sparkles className="w-3.5 h-3.5 text-indigo-400" />
            <span className="text-slate-300 font-medium">GOODS-S Deep Field</span>
            <span className="text-slate-500">•</span>
            <span className="text-slate-400">RA 53.15°, Dec -27.78°</span>
            <span className="text-slate-500">•</span>
            <span className="text-amber-400 font-mono">{galaxies.length} galaxies</span>
          </div>
        </div>

        {/* Slide-over Galaxy Inspector */}
        {selectedGalaxy && (
          <GalaxyInspector
            galaxy={selectedGalaxy}
            filters={manifest.filters}
            onClose={() => setSelectedGalaxy(null)}
            onUpdateGalaxy={handleUpdateGalaxy}
          />
        )}
      </div>
    </div>
  );
};

export default App;
