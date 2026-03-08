import { useEffect, useRef, useState } from 'react';
import { useAppStore } from '../store/useAppStore';

interface ViewState {
    x: number;
    y: number;
    scale: number;
}

export const useCanvasRenderer = (canvasRef: React.RefObject<HTMLCanvasElement>) => {
    const { mapData, agentsData, currentFrame } = useAppStore();

    const [viewState, setViewState] = useState<ViewState>({ x: 0, y: 0, scale: 20 });
    const isDragging = useRef(false);
    const lastMousePos = useRef({ x: 0, y: 0 });

    // 줌 컨트롤
    const handleWheel = (e: WheelEvent) => {
        e.preventDefault();
        const zoomSensitivity = 0.05;
        const delta = e.deltaY > 0 ? -1 : 1;
        setViewState(prev => ({
            ...prev,
            scale: Math.max(2, Math.min(100, prev.scale * (1 + delta * zoomSensitivity)))
        }));
    };

    // 패닝 컨트롤
    const handleMouseDown = (e: MouseEvent) => {
        isDragging.current = true;
        lastMousePos.current = { x: e.clientX, y: e.clientY };
    };

    const handleMouseMove = (e: MouseEvent) => {
        if (!isDragging.current) return;
        const dx = e.clientX - lastMousePos.current.x;
        const dy = e.clientY - lastMousePos.current.y;
        lastMousePos.current = { x: e.clientX, y: e.clientY };
        setViewState(prev => ({ ...prev, x: prev.x + dx, y: prev.y + dy }));
    };

    const handleMouseUp = () => {
        isDragging.current = false;
    };

    useEffect(() => {
        const canvas = canvasRef.current;
        if (!canvas) return;
        const ctx = canvas.getContext('2d');
        if (!ctx) return;

        // Canvas 초기화 및 리사이징 로직
        const resizeCanvas = () => {
            if (!canvas.parentElement) return;
            canvas.width = canvas.parentElement.clientWidth;
            canvas.height = canvas.parentElement.clientHeight;
            draw();
        };

        const draw = () => {
            if (!ctx || !mapData) return;

            // 배경 클리어
            ctx.fillStyle = '#18181B'; // zinc-900
            ctx.fillRect(0, 0, canvas.width, canvas.height);

            ctx.save();
            // 변환 적용 (패닝, 줌) - 중앙 정렬을 위한 기본 오프셋 추가 가능
            ctx.translate(canvas.width / 2 + viewState.x, canvas.height / 2 + viewState.y);
            ctx.scale(viewState.scale, viewState.scale);
            // 맵 중앙을 원점으로 보정
            ctx.translate(-mapData.width / 2, -mapData.height / 2);

            // 1. Grid 그리기
            ctx.strokeStyle = '#27272A'; // zinc-800
            ctx.lineWidth = 1 / viewState.scale;
            for (let i = 0; i <= mapData.width; i++) {
                ctx.beginPath(); ctx.moveTo(i, 0); ctx.lineTo(i, mapData.height); ctx.stroke();
            }
            for (let j = 0; j <= mapData.height; j++) {
                ctx.beginPath(); ctx.moveTo(0, j); ctx.lineTo(mapData.width, j); ctx.stroke();
            }

            // 2. 장애물 그리기
            ctx.fillStyle = '#3F3F46'; // zinc-700
            mapData.obstacles.forEach(obs => {
                ctx.fillRect(obs.x, obs.y, 1, 1);
            });

            // 3. 에이전트 폴리곤 그리기 (현재 프레임 기준)
            Object.values(agentsData).forEach(agentFrames => {
                const state = agentFrames[currentFrame];
                if (!state) return;

                ctx.fillStyle = 'rgba(59, 130, 246, 0.7)'; // blue-500 반투명
                if (state.status === 'deadlock') {
                    ctx.fillStyle = 'rgba(239, 68, 68, 0.8)'; // neon-red 반투명 (충돌/데드락 시 빨간 블렌딩)
                } else if (state.status === 'waiting') {
                    ctx.fillStyle = 'rgba(245, 158, 11, 0.7)'; // amber 반투명 (대기중)
                }

                ctx.save();
                ctx.translate(state.position.x + 0.5, state.position.y + 0.5); // 셀 중앙
                if (state.position.theta !== undefined) {
                    ctx.rotate(state.position.theta);
                }

                // 반경 0.4 크기의 원 또는 폴리곤 렌더링
                ctx.beginPath();
                ctx.arc(0, 0, 0.4, 0, Math.PI * 2);
                ctx.fill();
                ctx.restore();
            });

            // 4. 데드락(Wait-for) 화살표 오버레이 렌더링
            ctx.strokeStyle = '#EF4444'; // neon-red
            ctx.fillStyle = '#EF4444';
            ctx.lineWidth = 2 / viewState.scale;
            useAppStore.getState().deadlockEdges.forEach(([fromId, toId]) => {
                const fromAgent = agentsData[fromId]?.[currentFrame];
                const toAgent = agentsData[toId]?.[currentFrame];
                if (fromAgent && toAgent) {
                    const startX = fromAgent.position.x + 0.5;
                    const startY = fromAgent.position.y + 0.5;
                    const endX = toAgent.position.x + 0.5;
                    const endY = toAgent.position.y + 0.5;

                    ctx.beginPath();
                    ctx.moveTo(startX, startY);
                    ctx.lineTo(endX, endY);
                    ctx.stroke();

                    // 화살표 머리(도착점 원형) 렌더링
                    ctx.beginPath();
                    ctx.arc(endX, endY, 0.15, 0, Math.PI * 2);
                    ctx.fill();
                }
            });

            ctx.restore();
        };

        resizeCanvas();
        window.addEventListener('resize', resizeCanvas);
        canvas.addEventListener('wheel', handleWheel, { passive: false });
        canvas.addEventListener('mousedown', handleMouseDown);
        window.addEventListener('mousemove', handleMouseMove);
        window.addEventListener('mouseup', handleMouseUp);

        return () => {
            window.removeEventListener('resize', resizeCanvas);
            canvas.removeEventListener('wheel', handleWheel);
            canvas.removeEventListener('mousedown', handleMouseDown);
            window.removeEventListener('mousemove', handleMouseMove);
            window.removeEventListener('mouseup', handleMouseUp);
        };
    }, [mapData, agentsData, currentFrame, viewState, canvasRef]);

    return { setViewState };
};
