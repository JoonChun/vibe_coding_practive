export default async function handler(req: any, res: any) {
    if (req.method !== 'POST') {
        return res.status(405).json({ error: 'Method not allowed' });
    }

    try {
        const { sampleData } = req.body;

        if (!sampleData) {
            return res.status(400).json({ error: 'Sample data is required.' });
        }

        // Google Gemini API 동적 임포트 처리 (빌드 의존성 회피)
        const { GoogleGenAI } = await import('@google/genai');
        const ai = new GoogleGenAI({ apiKey: process.env.VERCEL_GEMINI_API_KEY || '' });

        const prompt = `
당신은 MAPF(다중 에이전트 경로 탐색) 프론트엔드 데이터 파싱 전문가입니다.
사용자가 비표준 포맷의 JSON 로그 첫 50줄의 샘플을 드롭했습니다.
이 데이터를 다음 TypeScript/JavaScript 인터페이스 규격으로 변환하는 단일 JavaScript(ES6) 파싱 함수 문자열을 작성하세요.

[목표 포맷]
interface Position { x: number; y: number; theta?: number; }
interface MapData { width: number; height: number; obstacles: Position[]; }
interface AgentState {
  agentId: number;
  frame: number;
  position: Position;
  velocity: number;
  targetNodeId?: string;
  status: 'moving' | 'waiting' | 'deadlock' | 'completed';
}
// 결과는 반드시 이런 구조여야 합니다: { mapData: MapData, agentsData: { [agentId: number]: AgentState[] }, totalFrames: number }

[입력 샘플 데이터]
${sampleData}

[제약 사항]
오직 "function parseLog(jsonString) { ... return result; }" 형태의 함수 코드 자체만 응답하십시오. (마크다운 백틱 제외)
    `;

        const response = await ai.models.generateContent({
            model: 'gemini-2.5-flash',
            contents: prompt,
        });

        const code = response.text?.replace(/```javascript/g, '').replace(/```js/g, '').replace(/```/g, '').trim();

        res.status(200).json({ adapterCode: code });
    } catch (error: unknown) {
        console.error('Gemini API Error:', error);
        const errorMessage = error instanceof Error ? error.message : 'Unknown error';
        res.status(500).json({ error: 'Failed to generate adapter code', details: errorMessage });
    }
}
