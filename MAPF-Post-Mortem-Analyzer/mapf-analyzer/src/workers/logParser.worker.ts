/// <reference lib="webworker" />
import { ParseResult, AgentState, MapData } from '../utils/schema';

// 단순화된 JSON 파서 뼈대 (추후 정밀화 및 동적 스키마 어댑터 연동 예정)
self.onmessage = async (e: MessageEvent) => {
    const { file } = e.data as { file: File };

    try {
        const text = await file.text();
        let parsed: any;

        // 임시: JSON 파싱 로직
        if (file.name.endsWith('.json')) {
            // AI 동적 스키마 어댑터 호출 (Vercel API 연동)
            try {
                const response = await fetch('/api/generate-adapter', {
                    method: 'POST',
                    headers: { 'Content-Type': 'application/json' },
                    body: JSON.stringify({ sampleData: text.substring(0, 2500) })
                });

                if (response.ok) {
                    const { adapterCode } = await response.json();
                    // 주의: MVP 목적의 function 샌드박싱 실행.
                    // 반환받은 코드는 function parseLog(jsonString) { ... } 형태여야 함
                    const parseFunc = new Function('jsonString', adapterCode + '\nreturn parseLog(jsonString);');
                    const aiResult = parseFunc(text);
                    if (aiResult && aiResult.mapData && aiResult.agentsData) {
                        self.postMessage({
                            mapData: aiResult.mapData,
                            agentsData: aiResult.agentsData,
                            totalFrames: aiResult.totalFrames || 0,
                            errors: []
                        });
                        return;
                    }
                }
            } catch (adapterErr) {
                console.warn('AI 샌드박스 어댑터 파싱 실패. 기본 폴백 구조를 사용합니다.', adapterErr);
            }

            parsed = JSON.parse(text);
        } else {
            throw new Error("Currently only JSON is supported in MVP baseline.");
        }

        // MAPF 표준 포맷 추출 가정 (임시 Mock)
        const mapData: MapData = {
            width: parsed.map?.width || 100,
            height: parsed.map?.height || 100,
            obstacles: parsed.map?.obstacles || []
        };

        const agentsData: Record<number, AgentState[]> = {};
        let maxFrame = 0;

        // TODO: 실 데이터 구조에 맞게 매핑 로직 이터레이션
        if (parsed && typeof parsed === 'object' && Array.isArray((parsed as Record<string, unknown>).agents)) {
            const parsedAgents = (parsed as Record<string, unknown>).agents as Array<Record<string, unknown>>;
            parsedAgents.forEach((agent) => {
                const id = Number(agent.id);
                const pathData = agent.path as Array<Record<string, unknown>>;
                agentsData[id] = pathData.map((p, idx: number) => {
                    if (idx > maxFrame) maxFrame = idx;
                    return {
                        agentId: id,
                        frame: idx,
                        position: { x: Number(p.x), y: Number(p.y) },
                        velocity: Number(p.v || 0),
                        status: p.v === 0 ? 'waiting' : 'moving'
                    };
                });
            });
        }

        const result: ParseResult = {
            mapData,
            agentsData,
            totalFrames: maxFrame,
            errors: []
        };

        self.postMessage(result);
    } catch (error: unknown) {
        const errorMsg = error instanceof Error ? error.message : 'Unknown Error';
        self.postMessage({ errors: [errorMsg] });
    }
};
