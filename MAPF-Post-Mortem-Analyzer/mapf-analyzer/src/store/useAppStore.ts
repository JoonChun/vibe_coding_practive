import { create } from 'zustand';
import { AgentState, MapData } from '../utils/schema';

interface AppState {
    // Map / Log Data
    mapData: MapData | null;
    agentsData: Record<number, AgentState[]>; // agentId -> frame별 상태
    totalFrames: number;

    // Playback State
    currentFrame: number;
    isPlaying: boolean;
    playbackSpeed: number;
    deadlockEdges: [number, number][];

    // Actions
    setLogData: (mapData: MapData, agentsData: Record<number, AgentState[]>, totalFrames: number) => void;
    setCurrentFrame: (frame: number) => void;
    togglePlay: () => void;
    setPlaybackSpeed: (speed: number) => void;
    setDeadlockEdges: (edges: [number, number][]) => void;
}

export const useAppStore = create<AppState>((set) => ({
    mapData: null,
    agentsData: {},
    totalFrames: 0,

    currentFrame: 0,
    isPlaying: false,
    playbackSpeed: 1,
    deadlockEdges: [],

    setLogData: (mapData, agentsData, totalFrames) => set({ mapData, agentsData, totalFrames, currentFrame: 0, isPlaying: false, deadlockEdges: [] }),
    setCurrentFrame: (frame) => set({ currentFrame: frame }),
    togglePlay: () => set((state) => ({ isPlaying: !state.isPlaying })),
    setPlaybackSpeed: (speed) => set({ playbackSpeed: speed }),
    setDeadlockEdges: (edges) => set({ deadlockEdges: edges }),
}));
