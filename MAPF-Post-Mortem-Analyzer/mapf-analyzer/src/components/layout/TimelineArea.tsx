import React, { useEffect, useRef } from 'react';
import { Play, Pause, SkipBack, SkipForward } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';

const TimelineArea: React.FC = () => {
    const {
        currentFrame, totalFrames, isPlaying, playbackSpeed,
        togglePlay, setCurrentFrame, mapData
    } = useAppStore();

    const animationRef = useRef<number>();
    const lastTimeRef = useRef<number>(0);

    // 재생 루프
    useEffect(() => {
        if (!isPlaying || totalFrames === 0) return;

        const loop = (time: number) => {
            if (lastTimeRef.current === 0) {
                lastTimeRef.current = time;
            }
            const deltaTime = time - lastTimeRef.current;

            // 1프레임당 재생 속도 제어 (예: 1배속 = 100ms 당 1프레임)
            const frameDuration = 100 / playbackSpeed;

            if (deltaTime >= frameDuration) {
                setCurrentFrame(Math.min(currentFrame + 1, totalFrames));
                lastTimeRef.current = time;

                // 끝에 도달하면 일시정지
                if (currentFrame >= totalFrames) {
                    togglePlay();
                    return;
                }
            }
            animationRef.current = requestAnimationFrame(loop);
        };

        animationRef.current = requestAnimationFrame(loop);

        return () => {
            if (animationRef.current) cancelAnimationFrame(animationRef.current);
        };
    }, [isPlaying, currentFrame, totalFrames, playbackSpeed, setCurrentFrame, togglePlay]);

    // 플레이 상태 변경 시 시간 초기화
    useEffect(() => {
        if (isPlaying) {
            lastTimeRef.current = 0;
            if (currentFrame >= totalFrames && totalFrames > 0) {
                setCurrentFrame(0); // 끝에서 재생 누르면 처음부터
            }
        }
    }, [isPlaying, currentFrame, totalFrames, setCurrentFrame]);

    const handleSliderChange = (e: React.ChangeEvent<HTMLInputElement>) => {
        setCurrentFrame(Number(e.target.value));
    };

    const progressPercent = totalFrames > 0 ? (currentFrame / totalFrames) * 100 : 0;

    return (
        <div className="h-20 bg-zinc-900 border-t border-zinc-800 flex items-center px-6 gap-6 w-full shrink-0 relative z-10">
            <div className="flex items-center gap-2">
                <button
                    className="p-2 hover:bg-zinc-800 rounded transition text-zinc-400 hover:text-white disabled:opacity-50"
                    onClick={() => setCurrentFrame(0)}
                    disabled={!mapData}
                >
                    <SkipBack size={20} />
                </button>
                <button
                    className="p-2 bg-primary hover:bg-blue-600 rounded transition text-white disabled:opacity-50"
                    onClick={togglePlay}
                    disabled={!mapData}
                >
                    {isPlaying ? <Pause size={20} className="ml-1" /> : <Play size={20} className="ml-1" />}
                </button>
                <button
                    className="p-2 hover:bg-zinc-800 rounded transition text-zinc-400 hover:text-white disabled:opacity-50"
                    onClick={() => setCurrentFrame(totalFrames)}
                    disabled={!mapData}
                >
                    <SkipForward size={20} />
                </button>
            </div>

            <div className="flex-1 flex flex-col justify-center h-full relative group">
                <div className="w-full h-3 bg-zinc-800 rounded-full relative overflow-hidden flex items-center">
                    <div
                        className="absolute top-0 left-0 h-full bg-primary pointer-events-none"
                        style={{ width: `${progressPercent}%` }}
                    />
                    {/* 이벤트 마커 렌더링 영역 (추후 데드락 발생 시간대에 빨간 마커 추가 등) */}
                    <input
                        type="range"
                        min={0}
                        max={totalFrames || 0}
                        value={currentFrame}
                        onChange={handleSliderChange}
                        className="absolute inset-0 w-full h-full opacity-0 cursor-pointer"
                        disabled={!mapData}
                    />
                </div>
            </div>

            <div className="font-mono text-sm text-zinc-400 w-24 text-right">
                {currentFrame} / {totalFrames}
            </div>
        </div>
    );
};

export default TimelineArea;
