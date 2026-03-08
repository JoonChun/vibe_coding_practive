export interface Position {
    x: number;
    y: number;
    theta?: number; // radians
}

export interface MapData {
    width: number;
    height: number;
    obstacles: Position[];
}

export interface AgentState {
    agentId: number;
    frame: number;
    position: Position;
    velocity: number;
    targetNodeId?: string; // Wait-for-Graph 용 목적지 추적
    status: 'moving' | 'waiting' | 'deadlock' | 'completed';
}

export interface ParseResult {
    mapData: MapData;
    agentsData: Record<number, AgentState[]>;
    totalFrames: number;
    errors: string[];
}
