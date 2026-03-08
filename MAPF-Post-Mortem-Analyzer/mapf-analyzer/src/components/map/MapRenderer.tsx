import React, { useRef } from 'react';
import { useCanvasRenderer } from '../../hooks/useCanvasRenderer';

const MapRenderer: React.FC = () => {
    const canvasRef = useRef<HTMLCanvasElement>(null);

    useCanvasRenderer(canvasRef);

    return (
        <div className="w-full h-full cursor-grab active:cursor-grabbing overflow-hidden">
            <canvas
                ref={canvasRef}
                className="w-full h-full block"
            />
        </div>
    );
};

export default MapRenderer;
