import { AgentState } from './schema';

// 에이전트 대기 그래프(Wait-for-Graph)의 노드 및 간선을 분석해 사이클을 반환
export const detectDeadlockCycles = (
    agents: AgentState[]
): { inCycleAgentIds: Set<number>, edges: [number, number][] } => {
    const inCycleAgentIds = new Set<number>();
    const edges: [number, number][] = []; // [fromAgent, toAgent]

    // 1. 현재 대기 상태인(속도==0) 에이전트들과 그들의 점유 위치 매핑
    const waitingAgents = agents.filter(a => a.status === 'waiting' || a.status === 'deadlock');
    const posToAgentId = new Map<string, number>();

    agents.forEach(a => {
        // 모든 에이전트의 현재 위치를 기록 (대기중이 아니더라도 길막 중일 수 있음)
        const posKey = `${Math.round(a.position.x)},${Math.round(a.position.y)}`;
        posToAgentId.set(posKey, a.agentId);
    });

    // 2. 간선 생성: waiting 에이전트의 타겟 위치(또는 바라보는 방향 바로 앞 칸)를 점유중인 에이전트가 있는지 확인
    const adjacencyList = new Map<number, number[]>();

    waitingAgents.forEach(waiter => {
        if (!waiter.targetNodeId) {
            // 타겟 노드가 명시되어 있지 않은 배열 기반의 경우, 위치 + 방향(theta)로 앞 셀을 추정 (간단 휴리스틱)
            // PRD상에는 targetNodeId 점유 상태를 비교한다고 명시되어 있음.
            return;
        }

        // targetNodeId가 "x,y" 형태의 포맷이라고 가정
        const blockingAgentId = posToAgentId.get(waiter.targetNodeId);

        if (blockingAgentId !== undefined && blockingAgentId !== waiter.agentId) {
            if (!adjacencyList.has(waiter.agentId)) {
                adjacencyList.set(waiter.agentId, []);
            }
            adjacencyList.get(waiter.agentId)!.push(blockingAgentId);
            edges.push([waiter.agentId, blockingAgentId]);
        }
    });

    // 3. DFS를 이용해 사이클 감지
    const visited = new Set<number>();
    const recursionStack = new Set<number>();
    const parentMap = new Map<number, number>();

    const dfs = (nodeId: number): boolean => {
        visited.add(nodeId);
        recursionStack.add(nodeId);

        const neighbors = adjacencyList.get(nodeId) || [];
        for (const neighbor of neighbors) {
            if (!visited.has(neighbor)) {
                parentMap.set(neighbor, nodeId);
                if (dfs(neighbor)) return true;
            } else if (recursionStack.has(neighbor)) {
                // 사이클 발견 (neighbor부터 역추적)
                inCycleAgentIds.add(neighbor);
                let curr = nodeId;
                while (curr !== neighbor && curr !== undefined) {
                    inCycleAgentIds.add(curr);
                    curr = parentMap.get(curr)!;
                }
                return true;
            }
        }

        recursionStack.delete(nodeId);
        return false;
    };

    // 모든 노드에 대해 수행 (연결되지 않은 컴포넌트 처리)
    for (const nodeId of adjacencyList.keys()) {
        if (!visited.has(nodeId)) {
            dfs(nodeId);
        }
    }

    return { inCycleAgentIds, edges };
};
