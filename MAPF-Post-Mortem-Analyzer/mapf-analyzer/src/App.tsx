import CanvasArea from './components/layout/CanvasArea';
import SidebarArea from './components/layout/SidebarArea';
import TimelineArea from './components/layout/TimelineArea';
import Dropzone from './components/parser/Dropzone';
import { useAppStore } from './store/useAppStore';
import { useEffect } from 'react';
import { detectDeadlockCycles } from './utils/deadlockDetector';
import { AgentState } from './utils/schema';

function App() {
  const { mapData, currentFrame, agentsData, setDeadlockEdges } = useAppStore();

  useEffect(() => {
    if (!mapData) return;

    // 현재 프레임의 모든 에이전트 상태 추출
    const currentAgents: AgentState[] = [];
    Object.values(agentsData).forEach(frames => {
      if (frames[currentFrame]) {
        currentAgents.push(frames[currentFrame]);
      }
    });

    const { edges } = detectDeadlockCycles(currentAgents);
    setDeadlockEdges(edges);
  }, [currentFrame, mapData, agentsData, setDeadlockEdges]);

  return (
    <div className="w-screen h-screen flex flex-col bg-background text-zinc-100 overflow-hidden font-sans relative">
      {!mapData && <Dropzone />}
      <main className="flex-1 flex w-full relative min-h-0">
        <CanvasArea />
        <SidebarArea />
      </main>
      <TimelineArea />
    </div>
  );
}

export default App;
