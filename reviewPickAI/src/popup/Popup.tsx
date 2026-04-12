import { useState, useEffect } from 'react';
import { Loader2, AlertCircle, CheckCircle2, Play } from 'lucide-react';
import type { ExtensionMessage, CrawlState } from '@/types';
import { detectPlatform } from '@/content/utils';
import { STORAGE_KEYS } from '@/constants';

type Phase =
  | 'idle'
  | 'unsupported'
  | 'no-api-key'
  | 'ready'
  | 'crawling'
  | 'analyzing'
  | 'done'
  | 'error';

const DEFAULT_MAX_REVIEWS = 50;
// 30분 이내 crawlState만 복원
const STATE_TTL_MS = 30 * 60 * 1000;

export function Popup() {
  const [phase, setPhase] = useState<Phase>('idle');
  const [platform, setPlatform] = useState<string>('');
  const [progress, setProgress] = useState({ pages: 0, reviews: 0 });
  const [analysisProgress, setAnalysisProgress] = useState({ done: 0, total: 0 });
  const [errorMsg, setErrorMsg] = useState('');
  const [apiKey, setApiKey] = useState('');
  const [showApiInput, setShowApiInput] = useState(false);
  const [maxReviews, setMaxReviews] = useState<number>(DEFAULT_MAX_REVIEWS);

  useEffect(() => {
    chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
      if (!tab?.url) return;
      const p = detectPlatform(new URL(tab.url).hostname);
      if (!p) {
        setPhase('unsupported');
        return;
      }
      setPlatform(p === 'coupang' ? '쿠팡' : '네이버 쇼핑');

      // API 키 + 수집 개수 + 진행 상태 한번에 로드
      chrome.storage.local.get(
        [STORAGE_KEYS.GEMINI_API_KEY, STORAGE_KEYS.MAX_REVIEWS, STORAGE_KEYS.CRAWL_STATE],
        (result) => {
          const key = result[STORAGE_KEYS.GEMINI_API_KEY] as string | undefined;
          const savedMax = result[STORAGE_KEYS.MAX_REVIEWS] as number | undefined;
          const savedState = result[STORAGE_KEYS.CRAWL_STATE] as CrawlState | undefined;

          if (savedMax) setMaxReviews(savedMax);

          // 진행 중인 상태만 복원 (error/done은 복원하지 않음)
          if (savedState && Date.now() - savedState.updatedAt < STATE_TTL_MS) {
            if (savedState.phase === 'crawling') {
              setProgress({ pages: savedState.pages, reviews: savedState.reviews });
              setPhase('crawling');
              return;
            }
            if (savedState.phase === 'analyzing') {
              setAnalysisProgress({ done: savedState.chunksComplete, total: savedState.totalChunks });
              setPhase('analyzing');
              return;
            }
          }

          if (!key) {
            setPhase('no-api-key');
          } else {
            setApiKey(key);
            setPhase('ready');
          }
        },
      );
    });

    const listener = (message: ExtensionMessage) => {
      if (message.action === 'CRAWL_PROGRESS') {
        setProgress({ pages: message.pagesScraped, reviews: message.totalReviews });
        setPhase('crawling');
      } else if (message.action === 'ANALYSIS_PROGRESS') {
        setAnalysisProgress({ done: message.chunksComplete, total: message.totalChunks });
        setPhase('analyzing');
      } else if (message.action === 'ANALYSIS_COMPLETE') {
        setPhase((prev) => (prev === 'analyzing' || prev === 'crawling') ? 'done' : prev);
      } else if (message.action === 'ANALYSIS_ERROR') {
        setErrorMsg(message.message);
        setPhase('error');
      }
    };

    chrome.runtime.onMessage.addListener(listener);
    return () => chrome.runtime.onMessage.removeListener(listener);
  }, []);

  const saveApiKey = () => {
    if (!apiKey.trim()) return;
    chrome.storage.local.set({ [STORAGE_KEYS.GEMINI_API_KEY]: apiKey.trim() }, () => {
      setShowApiInput(false);
      setPhase('ready');
    });
  };

  const listModels = async () => {
    const key = apiKey || (await new Promise<string>((res) => {
      chrome.storage.local.get('geminiApiKey', (r) => res(r.geminiApiKey ?? ''));
    }));
    if (!key) { alert('API 키를 먼저 입력하세요.'); return; }

    const allModels: string[] = [];
    let pageToken = '';
    do {
      const url = `https://generativelanguage.googleapis.com/v1beta/models?pageSize=100&key=${key}${pageToken ? `&pageToken=${pageToken}` : ''}`;
      const res = await fetch(url);
      const data = await res.json();
      (data.models ?? []).forEach((m: { name: string }) => allModels.push(m.name.replace('models/', '')));
      pageToken = data.nextPageToken ?? '';
    } while (pageToken);

    const filtered = allModels.filter((n) => n.includes('gemini') || n.includes('flash'));
    alert(`=== gemini-3 / flash 모델 ===\n${filtered.join('\n')}\n\n=== 전체 (${allModels.length}개) ===\n${allModels.join('\n')}`);
  };

  const handleMaxReviewsChange = (value: number) => {
    setMaxReviews(value);
    chrome.storage.local.set({ [STORAGE_KEYS.MAX_REVIEWS]: value });
  };

  const cancelCrawl = () => {
    chrome.storage.local.remove(STORAGE_KEYS.CRAWL_STATE);
    chrome.action.setBadgeText({ text: '' });

    chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
      if (!tab?.id) {
        setPhase('ready');
        return;
      }
      chrome.tabs.sendMessage(tab.id, { action: 'CANCEL_CRAWL' } as ExtensionMessage, () => {
        void chrome.runtime.lastError;
        setPhase('ready');
      });
    });
  };

  const startCrawl = () => {
    setErrorMsg('');
    setPhase('crawling');
    setProgress({ pages: 0, reviews: 0 });

    chrome.tabs.query({ active: true, currentWindow: true }, ([tab]) => {
      if (!tab?.id) return;
      const tabId = tab.id;
      const msg: ExtensionMessage = { action: 'START_CRAWL', maxReviews };

      const sendMsg = (onFail: () => void) => {
        chrome.tabs.sendMessage(tabId, msg, (response) => {
          if (chrome.runtime.lastError || !response?.ok) {
            onFail();
          }
        });
      };

      // 1차 전송 시도
      sendMsg(() => {
        // 콘텐츠 스크립트가 없으면 자동 주입 후 재시도
        chrome.scripting.executeScript(
          { target: { tabId }, files: ['content.js'] },
          () => {
            if (chrome.runtime.lastError) {
              setPhase('error');
              setErrorMsg('스크립트 주입 실패. 페이지를 새로고침 후 다시 시도하세요.');
              return;
            }
            // 주입 후 초기화 대기 → 재시도
            setTimeout(() => {
              sendMsg(() => {
                setPhase('error');
                setErrorMsg('콘텐츠 스크립트 통신 실패. 페이지를 새로고침 후 다시 시도하세요.');
              });
            }, 150);
          },
        );
      });
    });
  };

  return (
    <div className="w-[320px] bg-surface font-sans">
      {/* 헤더 */}
      <div className="px-5 pt-5 pb-4 border-b border-outline-variant/15">
        <div className="flex items-center justify-between">
          <div className="flex items-center gap-2.5">
            <div className="w-8 h-8 rounded-[10px] bg-primary flex items-center justify-center">
              <span className="text-white font-bold text-sm">R</span>
            </div>
            <div>
              <p className="text-[14px] font-bold text-text-primary">ReviewPick AI</p>
              <p className="text-[11px] text-text-secondary">리뷰 AI 분석</p>
            </div>
          </div>
          <div className="flex gap-2">
            <button
              onClick={listModels}
              className="text-[11px] text-text-disabled hover:text-text-secondary transition-colors"
            >
              모델확인
            </button>
            <button
              onClick={() => setShowApiInput((v) => !v)}
              className="text-[11px] text-text-disabled hover:text-text-secondary transition-colors"
            >
              API 키
            </button>
          </div>
        </div>
      </div>

      {/* API 키 입력 */}
      {showApiInput && (
        <div className="px-5 py-3 bg-bg border-b border-outline-variant/15">
          <p className="text-[12px] text-text-secondary mb-2">Gemini API 키</p>
          <div className="flex gap-2">
            <input
              type="password"
              value={apiKey}
              onChange={(e) => setApiKey(e.target.value)}
              placeholder="AIza..."
              className="flex-1 px-3 py-2 text-[12px] bg-surface-container-low rounded-[10px] outline-none focus:ring-2 focus:ring-primary/20 transition-shadow"
            />
            <button
              onClick={saveApiKey}
              className="px-3 py-2 bg-primary text-white text-[12px] rounded-[10px] hover:bg-primary/90"
            >
              저장
            </button>
          </div>
        </div>
      )}

      {/* 본문 */}
      <div className="px-5 py-5">
        {phase === 'idle' && (
          <div className="flex items-center justify-center py-4">
            <Loader2 size={20} className="animate-spin text-primary" />
          </div>
        )}

        {phase === 'unsupported' && (
          <div className="flex flex-col items-center gap-3 py-4">
            <AlertCircle size={24} className="text-text-disabled" />
            <p className="text-[13px] text-text-secondary text-center leading-relaxed">
              쿠팡 또는 네이버 쇼핑<br />상품 페이지에서 사용하세요.
            </p>
          </div>
        )}

        {phase === 'no-api-key' && (
          <div className="flex flex-col gap-3 py-2">
            <p className="text-[13px] text-text-primary">
              Gemini API 키를 먼저 설정해주세요.
            </p>
            <button
              onClick={() => setShowApiInput(true)}
              className="w-full py-2.5 bg-primary text-white text-[13px] font-medium rounded-[12px] hover:bg-primary/90 transition-colors"
            >
              API 키 입력하기
            </button>
          </div>
        )}

        {phase === 'ready' && (
          <div className="flex flex-col gap-4">
            <div className="flex items-center gap-2 p-3 bg-primary/5 rounded-[12px]">
              <CheckCircle2 size={16} className="text-primary flex-shrink-0" />
              <p className="text-[13px] text-text-primary">
                <span className="font-semibold">{platform}</span> 페이지 감지됨
              </p>
            </div>

            {/* 수집 개수 설정 */}
            <div className="flex flex-col gap-2">
              <div className="flex items-center justify-between">
                <p className="text-[12px] text-text-secondary font-medium">수집할 리뷰 개수</p>
                <span className="text-[14px] font-bold text-primary">{maxReviews}개</span>
              </div>
              <input
                type="range"
                min={10}
                max={100}
                step={10}
                value={maxReviews}
                onChange={(e) => handleMaxReviewsChange(Number(e.target.value))}
                className="w-full accent-primary cursor-pointer"
              />
              <div className="flex justify-between text-[10px] text-text-disabled">
                <span>10</span>
                <span>100</span>
              </div>
            </div>

            <button
              onClick={startCrawl}
              className="w-full flex items-center justify-center gap-2 py-3 bg-primary text-white text-[14px] font-bold rounded-[14px] hover:bg-primary/90 active:scale-[0.98] transition-all"
            >
              <Play size={14} className="fill-white" />
              분석 시작
            </button>
          </div>
        )}

        {phase === 'crawling' && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <Loader2 size={16} className="animate-spin text-primary" />
              <p className="text-[13px] font-medium text-text-primary">리뷰 수집 중...</p>
            </div>
            <div className="p-3 bg-bg rounded-[12px]">
              <div className="grid grid-cols-2 gap-2 text-center">
                <div>
                  <p className="text-[20px] font-bold text-primary">{progress.reviews}</p>
                  <p className="text-[11px] text-text-secondary">수집된 리뷰</p>
                </div>
                <div>
                  <p className="text-[20px] font-bold text-text-primary">{progress.pages}</p>
                  <p className="text-[11px] text-text-secondary">페이지</p>
                </div>
              </div>
              {/* 수집 목표 대비 진행률 */}
              <div className="mt-3">
                <div className="flex justify-between text-[10px] text-text-disabled mb-1">
                  <span>진행률</span>
                  <span>{progress.reviews} / {maxReviews}</span>
                </div>
                <div className="h-1 bg-surface-container-high rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all duration-500"
                    style={{ width: `${Math.min((progress.reviews / maxReviews) * 100, 100)}%` }}
                  />
                </div>
              </div>
            </div>
            <p className="text-[11px] text-text-disabled text-center">
              팝업을 닫아도 백그라운드에서 계속 수집됩니다.
            </p>
            <button
              onClick={cancelCrawl}
              className="w-full py-2 border border-outline-variant/30 text-[13px] text-text-secondary rounded-[12px] hover:border-negative hover:text-negative transition-colors"
            >
              수집 취소
            </button>
          </div>
        )}

        {phase === 'analyzing' && (
          <div className="flex flex-col gap-3">
            <div className="flex items-center gap-2">
              <Loader2 size={16} className="animate-spin text-primary" />
              <p className="text-[13px] font-medium text-text-primary">AI 분석 중...</p>
            </div>
            {analysisProgress.total > 0 && (
              <div>
                <div className="flex justify-between text-[11px] text-text-secondary mb-1">
                  <span>청크 처리</span>
                  <span>{analysisProgress.done}/{analysisProgress.total}</span>
                </div>
                <div className="h-1.5 bg-surface-container-high rounded-full overflow-hidden">
                  <div
                    className="h-full bg-primary rounded-full transition-all duration-300"
                    style={{
                      width: `${(analysisProgress.done / analysisProgress.total) * 100}%`,
                    }}
                  />
                </div>
              </div>
            )}
            <p className="text-[11px] text-text-disabled text-center">
              완료되면 알림이 전송됩니다.
            </p>
            <button
              onClick={() => { setPhase('ready'); chrome.storage.local.remove(STORAGE_KEYS.CRAWL_STATE); }}
              className="w-full py-2 border border-outline-variant/30 text-[13px] text-text-secondary rounded-[12px] hover:border-outline-variant hover:text-text-primary transition-colors"
            >
              닫기
            </button>
          </div>
        )}

        {phase === 'done' && (
          <div className="flex flex-col items-center gap-3 py-2">
            <CheckCircle2 size={28} className="text-primary" />
            <p className="text-[14px] font-bold text-text-primary">분석 완료!</p>
            <p className="text-[12px] text-text-secondary">대시보드 탭이 열렸습니다.</p>
            <button
              onClick={() => setPhase('ready')}
              className="w-full py-2.5 border border-outline-variant/30 text-[13px] text-text-secondary rounded-[12px] hover:border-primary hover:text-primary transition-colors"
            >
              새 분석 시작
            </button>
          </div>
        )}

        {phase === 'error' && (
          <div className="flex flex-col gap-3 py-2">
            <div className="flex items-start gap-2">
              <AlertCircle size={16} className="text-negative flex-shrink-0 mt-0.5" />
              <p className="text-[13px] text-text-primary leading-relaxed">{errorMsg}</p>
            </div>
            <button
              onClick={() => setPhase('ready')}
              className="w-full py-2.5 border border-outline-variant/30 text-[13px] text-text-secondary rounded-[12px] hover:border-primary hover:text-primary transition-colors"
            >
              다시 시도
            </button>
          </div>
        )}
      </div>
    </div>
  );
}
