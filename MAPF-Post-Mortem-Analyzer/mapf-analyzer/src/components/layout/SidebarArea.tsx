import React from 'react';
import { Settings, FileText, Activity, AlertTriangle } from 'lucide-react';
import { useAppStore } from '../../store/useAppStore';

const SidebarArea: React.FC = () => {
    const { deadlockEdges } = useAppStore();

    // 데드락 사이클에 연관된 에이전트 추출
    const cycleAgents = new Set<number>();
    deadlockEdges.forEach(([fromId, toId]) => {
        cycleAgents.add(fromId);
        cycleAgents.add(toId);
    });
    const cycleAgentsArr = Array.from(cycleAgents).sort();

    return (
        <div className="w-80 shrink-0 bg-zinc-900 flex flex-col overflow-y-auto z-10">
            <div className="p-4 border-b border-zinc-800 flex items-center gap-2 font-semibold text-white">
                <Activity size={18} className="text-primary" />
                Inspector
            </div>

            <div className="flex-1 p-4 flex flex-col gap-6">
                <section>
                    <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3 flex items-center gap-2">
                        <AlertTriangle size={14} className={cycleAgentsArr.length > 0 ? "text-neon-red" : ""} />
                        Deadlock Analysis
                    </h3>
                    <div className="bg-zinc-800/50 rounded-lg p-3 text-sm text-zinc-300 border border-zinc-800">
                        {cycleAgentsArr.length > 0 ? (
                            <div>
                                <span className="text-neon-red font-bold">Cycle Detected!</span>
                                <p className="mt-2 mb-2 text-zinc-400">Wait-for-graph cycle involves:</p>
                                <div className="flex flex-wrap gap-2">
                                    {cycleAgentsArr.map(id => (
                                        <span key={id} className="bg-zinc-700 px-2 py-0.5 rounded text-xs text-white">
                                            Agent {id}
                                        </span>
                                    ))}
                                </div>
                            </div>
                        ) : (
                            <span className="text-zinc-500">No deadlock cycle at this frame.</span>
                        )}
                    </div>
                </section>

                <section>
                    <h3 className="text-xs font-semibold text-zinc-500 uppercase tracking-wider mb-3 items-center flex gap-2">
                        <Settings size={14} /> Workbench
                    </h3>
                    <div className="flex flex-col gap-2">
                        <button className="w-full py-2 bg-zinc-800 hover:bg-zinc-700 rounded text-sm text-zinc-300 transition border border-zinc-700 disabled:opacity-50">
                            Run Target Re-planner (A*)
                        </button>
                        <button
                            className="w-full py-2 bg-zinc-800 hover:bg-zinc-700 rounded text-sm text-zinc-300 transition border border-zinc-700 flex items-center justify-center gap-2"
                            onClick={() => location.reload()}
                        >
                            <FileText size={14} /> Reset Logs
                        </button>
                    </div>
                </section>
            </div>
        </div>
    );
};

export default SidebarArea;
