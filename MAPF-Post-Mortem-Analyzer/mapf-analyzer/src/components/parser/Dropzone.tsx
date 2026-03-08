import React, { useCallback } from 'react';
import { useAppStore } from '../../store/useAppStore';
import { UploadCloud } from 'lucide-react';
// Vite 워커 임포트 방식
import ParserWorker from '../../workers/logParser.worker?worker';

const Dropzone: React.FC = () => {
    const setLogData = useAppStore(state => state.setLogData);

    const processFile = (file: File) => {
        // 50MB 이상 제한
        if (file.size > 50 * 1024 * 1024) {
            alert("로그 파일은 50MB를 넘을 수 없습니다.");
            return;
        }

        const worker = new ParserWorker();

        worker.onmessage = (e: MessageEvent) => {
            const { mapData, agentsData, totalFrames, errors } = e.data;
            if (errors && errors.length > 0) {
                alert("파싱 에러: " + errors.join('\n'));
            } else {
                setLogData(mapData, agentsData, totalFrames);
            }
            worker.terminate();
        };

        worker.onerror = (err) => {
            console.error(err);
            alert("Worker 파싱 중 에러 발생");
            worker.terminate();
        };

        worker.postMessage({ file });
    };

    const handleDrop = useCallback((e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
        if (e.dataTransfer.files && e.dataTransfer.files.length > 0) {
            processFile(e.dataTransfer.files[0]);
        }
    }, [processFile]);

    const handleDragOver = (e: React.DragEvent<HTMLDivElement>) => {
        e.preventDefault();
    };

    return (
        <div
            className="absolute inset-0 z-50 flex items-center justify-center bg-zinc-900/80 backdrop-blur-sm"
            onDrop={handleDrop}
            onDragOver={handleDragOver}
        >
            <div className="flex flex-col items-center justify-center p-12 border-2 border-dashed border-zinc-500 rounded-xl bg-zinc-800/50 text-zinc-400 max-w-md text-center pointer-events-none">
                <UploadCloud size={48} className="mb-4 text-primary" />
                <h2 className="text-xl font-bold text-white mb-2">Drop MAPF Log File Here</h2>
                <p className="text-sm">JSON, CSV 파일 지원 (최대 50MB)</p>
            </div>
        </div>
    );
};

export default Dropzone;
