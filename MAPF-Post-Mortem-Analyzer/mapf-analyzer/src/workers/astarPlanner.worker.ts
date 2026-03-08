/// <reference lib="webworker" />
import { Position, MapData } from '../utils/schema';

// A* 휴리스틱 (맨해튼 거리)
const heuristic = (a: Position, b: Position) => Math.abs(a.x - b.x) + Math.abs(a.y - b.y);

// 노드 고유 키
const toKey = (p: Position) => `${p.x},${p.y}`;

interface AStarNode {
    pos: Position;
    g: number;
    h: number;
    f: number;
    parent?: AStarNode;
}

// 단순 A* 구현체 (실제 MAPF에서는 타임스페이셜 예약 테이블이 필요하지만, 단일 우회용 MVP 모드)
self.onmessage = (e: MessageEvent) => {
    const { mapData, start, goal, dynamicObstacles } = e.data as {
        mapData: MapData,
        start: Position,
        goal: Position,
        dynamicObstacles: Position[] // 현재 다른 에이전트들이 서있는 위치(기본 페널티)
    };

    try {
        const obstacleSet = new Set<string>();
        mapData.obstacles.forEach(o => obstacleSet.add(toKey(o)));

        // 임시 페널티 맵
        const penaltyMap = new Map<string, number>();
        dynamicObstacles.forEach(o => penaltyMap.set(toKey(o), 100)); // 다른 에이전트 자리 겹치지 않게 가중치 부여

        const openList: AStarNode[] = [];
        const closedSet = new Set<string>();

        const startNode: AStarNode = { pos: start, g: 0, h: heuristic(start, goal), f: heuristic(start, goal) };
        openList.push(startNode);

        let pathFound = false;
        let finalNode: AStarNode | null = null;

        const dirs = [[0, 1], [1, 0], [0, -1], [-1, 0]]; // 상하좌우

        // 최대 탐색 제한 (무한루프 방지)
        let iterCount = 0;
        const MAX_ITER = 20000;

        while (openList.length > 0 && iterCount < MAX_ITER) {
            iterCount++;
            // 가장 f값이 작은 노드 선택
            openList.sort((a, b) => a.f - b.f);
            const current = openList.shift()!;

            const currentKey = toKey(current.pos);
            if (current.pos.x === goal.x && current.pos.y === goal.y) {
                pathFound = true;
                finalNode = current;
                break;
            }

            closedSet.add(currentKey);

            for (const [dx, dy] of dirs) {
                const nx = current.pos.x + dx;
                const ny = current.pos.y + dy;
                const neighborPos = { x: nx, y: ny };
                const neighborKey = toKey(neighborPos);

                // 맵 범위 체크
                if (nx < 0 || ny < 0 || nx >= mapData.width || ny >= mapData.height) continue;

                // 고정 장애물 및 방문 체크
                if (obstacleSet.has(neighborKey) || closedSet.has(neighborKey)) continue;

                // 비용 계산 (기본 1 + 동적 장애물 페널티)
                const cost = 1 + (penaltyMap.get(neighborKey) || 0);
                const gScore = current.g + cost;

                const existingNode = openList.find(n => toKey(n.pos) === neighborKey);

                if (!existingNode || gScore < existingNode.g) {
                    const hScore = heuristic(neighborPos, goal);
                    const neighborNode: AStarNode = {
                        pos: neighborPos,
                        g: gScore,
                        h: hScore,
                        f: gScore + hScore,
                        parent: current
                    };

                    if (!existingNode) {
                        openList.push(neighborNode);
                    } else {
                        existingNode.g = neighborNode.g;
                        existingNode.f = neighborNode.f;
                        existingNode.parent = neighborNode.parent;
                    }
                }
            }
        }

        if (pathFound && finalNode) {
            const path: Position[] = [];
            let curr: AStarNode | undefined = finalNode;
            while (curr) {
                path.push(curr.pos);
                curr = curr.parent;
            }
            path.reverse();
            self.postMessage({ success: true, path, info: `Found in ${iterCount} iterations` });
        } else {
            self.postMessage({ success: false, error: 'Path not found or max iteration reached' });
        }

    } catch (err: unknown) {
        const errorMsg = err instanceof Error ? err.message : 'Unknown Error';
        self.postMessage({ success: false, error: errorMsg });
    }
};
