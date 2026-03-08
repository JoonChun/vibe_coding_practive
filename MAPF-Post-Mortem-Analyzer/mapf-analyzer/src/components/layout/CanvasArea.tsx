import React from 'react';
import MapRenderer from '../map/MapRenderer';
import { useAppStore } from '../../store/useAppStore';

const CanvasArea: React.FC = () => {
    const mapData = useAppStore(state => state.mapData);

    return (
        <div className="flex-1 min-w-0 bg-zinc-900/50 border-r border-zinc-800 relative">
            <div className="absolute top-4 left-4 bg-zinc-800 px-3 py-1 rounded text-sm text-zinc-400 font-mono z-10 pointer-events-none">
                Map Canvas (2D Grid)
            </div>
            {mapData ? (
                <MapRenderer />
            ) : (
                <div className="w-full h-full flex items-center justify-center text-zinc-600 border border-dashed border-zinc-700 m-4 rounded-lg">
                    No Map Data
                </div>
            )}
        </div>
    );
};

export default CanvasArea;
