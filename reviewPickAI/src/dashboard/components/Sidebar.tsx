import { useState, useEffect, useRef } from 'react';
import { Search, Plus, Trash2 } from 'lucide-react';
import type { ExtensionMessage } from '@/types';

interface SidebarProps {
  onKeywordFilter: (keyword: string) => void;
  activeKeyword: string;
}

export function Sidebar({ onKeywordFilter, activeKeyword }: SidebarProps) {
  const [inputValue, setInputValue] = useState(activeKeyword);
  const [compareUrls, setCompareUrls] = useState<string[]>([]);
  const [compareInput, setCompareInput] = useState('');
  const debounceRef = useRef<ReturnType<typeof setTimeout>>();

  // 외부 prop(마인드맵 클릭)이 바뀌면 인풋 표시만 동기화 — onKeywordFilter 호출 금지
  useEffect(() => {
    setInputValue(activeKeyword);
  }, [activeKeyword]);

  const handleInputChange = (value: string) => {
    setInputValue(value);
    clearTimeout(debounceRef.current);
    debounceRef.current = setTimeout(() => {
      onKeywordFilter(value);

      if (value) {
        const msg: ExtensionMessage = { action: 'RE_ANALYZE', keyword: value };
        chrome.runtime.sendMessage(msg).catch(() => {});
      }
    }, 600);
  };

  const addCompareUrl = () => {
    const url = compareInput.trim();
    if (!url || compareUrls.includes(url)) return;
    if (compareUrls.length >= 3) {
      alert('비교 상품은 최대 3개까지 추가할 수 있습니다.');
      return;
    }
    setCompareUrls((prev) => [...prev, url]);
    setCompareInput('');
    const msg: ExtensionMessage = { action: 'COMPARE_ADD', url };
    chrome.runtime.sendMessage(msg).catch(() => {});
  };

  const removeCompareUrl = (url: string) => {
    setCompareUrls((prev) => prev.filter((u) => u !== url));
  };

  return (
    <aside className="flex flex-col gap-4 h-full">
      {/* 키워드 필터 카드 */}
      <div className="bg-surface rounded-3xl p-6 shadow-whisper flex flex-col gap-4">
        <h3 className="font-headline font-semibold text-[15px] text-on-surface">
          스마트 키워드 필터
        </h3>

        <div className="relative">
          <Search
            size={14}
            className="absolute left-3.5 top-1/2 -translate-y-1/2 text-on-surface-variant"
          />
          <input
            type="text"
            value={inputValue}
            onChange={(e) => handleInputChange(e.target.value)}
            placeholder="키워드 입력..."
            className="w-full pl-9 pr-3 py-2.5 bg-surface-container-low rounded-[12px] text-[13px] text-on-surface placeholder:text-on-surface-variant border-none outline-none focus:ring-2 focus:ring-primary/20 transition-shadow"
          />
        </div>

        {activeKeyword && (
          <div className="flex items-center gap-2">
            <span className="text-[11px] text-secondary">필터 적용 중:</span>
            <span className="px-2.5 py-0.5 bg-primary/10 text-primary text-[12px] rounded-full font-semibold">
              {activeKeyword}
            </span>
            <button
              onClick={() => {
                setInputValue('');
                onKeywordFilter('');
              }}
              className="text-on-surface-variant hover:text-negative text-[11px] transition-colors"
            >
              ✕
            </button>
          </div>
        )}
      </div>

      {/* 벤치마킹 비교 카드 */}
      <div className="bg-surface rounded-3xl p-6 shadow-whisper flex flex-col gap-4">
        <h3 className="font-headline font-semibold text-[15px] text-on-surface">
          벤치마킹 비교
        </h3>

        <div className="flex flex-col gap-2">
          {compareUrls.map((url) => (
            <div
              key={url}
              className="flex items-center gap-2 p-2.5 bg-surface-container-low rounded-[12px]"
            >
              <span className="flex-1 text-[11px] text-secondary truncate">{url}</span>
              <button
                onClick={() => removeCompareUrl(url)}
                className="flex-shrink-0 text-on-surface-variant hover:text-negative transition-colors"
              >
                <Trash2 size={12} />
              </button>
            </div>
          ))}
        </div>

        {compareUrls.length < 3 && (
          <div className="flex gap-2">
            <input
              type="url"
              value={compareInput}
              onChange={(e) => setCompareInput(e.target.value)}
              onKeyDown={(e) => e.key === 'Enter' && addCompareUrl()}
              placeholder="상품 URL 붙여넣기"
              className="flex-1 px-3 py-2.5 bg-surface-container-low rounded-[12px] text-[12px] text-on-surface placeholder:text-on-surface-variant border-none outline-none focus:ring-2 focus:ring-primary/20 transition-shadow"
            />
            <button
              onClick={addCompareUrl}
              className="flex-shrink-0 w-9 h-9 bg-gradient-primary rounded-[12px] flex items-center justify-center hover:opacity-90 transition-opacity"
            >
              <Plus size={15} className="text-white" />
            </button>
          </div>
        )}

        {compareUrls.length > 0 && (
          <p className="text-[11px] text-on-surface-variant leading-relaxed">
            각 상품 페이지에서 분석 시작 후 비교 대시보드가 열립니다.
          </p>
        )}
      </div>
    </aside>
  );
}
