import { useState, useRef, useCallback } from 'react';
import { Loader2, AlertCircle, Lightbulb, TrendingUp, TrendingDown, X } from 'lucide-react';
import type { MindmapNode } from '@/types';
import { useAnalysisData } from './hooks/useAnalysisData';
import { Header } from './components/Header';
import { SentimentChart } from './components/SentimentChart';
import { AISummaryCard } from './components/AISummaryCard';
import { Mindmap } from './components/Mindmap';
import { ReviewList } from './components/ReviewList';
import { Sidebar } from './components/Sidebar';
import { ComparisonView } from './components/ComparisonView';

export function Dashboard() {
  const { data, loading, error, comparisonSessions } = useAnalysisData();
  const [activeKeyword, setActiveKeyword] = useState('');
  const [activeNodeId, setActiveNodeId] = useState<string>();
  const [filterIndices, setFilterIndices] = useState<number[] | undefined>();
  const svgRef = useRef<SVGSVGElement>(null);

  const handleNodeClick = useCallback((node: MindmapNode) => {
    setActiveNodeId(node.id);
    setFilterIndices(node.relatedReviewIndices);
    setActiveKeyword(node.label);
  }, []);

  const handleKeywordFilter = useCallback((keyword: string) => {
    setActiveKeyword(keyword);
    // Sidebar에서 키워드를 타이핑하면 마인드맵 노드 기반 인덱스 필터를 해제하고
    // 텍스트 하이라이트만 동작하도록 함
    setFilterIndices(undefined);
    setActiveNodeId(undefined);
  }, []);

  const clearNodeFilter = useCallback(() => {
    setActiveNodeId(undefined);
    setFilterIndices(undefined);
    setActiveKeyword('');
  }, []);

  if (loading) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-secondary">
          <Loader2 size={32} className="animate-spin text-primary" />
          <p className="text-[14px]">분석 결과를 불러오는 중...</p>
        </div>
      </div>
    );
  }

  if (error) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="flex flex-col items-center gap-3 text-negative">
          <AlertCircle size={32} />
          <p className="text-[14px]">{error}</p>
        </div>
      </div>
    );
  }

  if (!data) {
    return (
      <div className="min-h-screen bg-bg flex items-center justify-center">
        <div className="flex flex-col items-center gap-5 text-secondary">
          <div className="w-16 h-16 rounded-[20px] bg-gradient-primary flex items-center justify-center">
            <span className="text-white text-2xl font-bold font-headline">R</span>
          </div>
          <div className="text-center">
            <p className="text-[17px] font-bold text-on-surface font-headline">ReviewPick AI</p>
            <p className="text-[13px] mt-1">쿠팡 또는 네이버 상품 페이지에서 분석을 시작하세요.</p>
          </div>
        </div>
      </div>
    );
  }

  return (
    <div id="dashboard-root" className="min-h-screen bg-bg">
      <Header data={data} svgRef={svgRef} />

      <main className="max-w-screen-2xl mx-auto px-8 py-8">
        <div className="grid grid-cols-12 gap-6">

          {/* ─── Row 1: AI 요약 (8) + 감성 차트 (4) ─── */}
          <section className="col-span-12 lg:col-span-8">
            <AISummaryCard summary={data.summary} />
          </section>

          <section className="col-span-12 lg:col-span-4">
            <SentimentChart sentiment={data.sentiment} />
          </section>

          {/* ─── Row 2: 마케팅 인사이트 (12) ─── */}
          {data.summary.marketingInsights.length > 0 && (
            <section className="col-span-12 bg-surface rounded-3xl p-8 shadow-whisper">
              <div className="flex items-center justify-between mb-8">
                <h2 className="font-headline font-semibold text-[17px] text-on-surface flex items-center gap-2">
                  <Lightbulb size={20} className="text-primary" />
                  마케팅 소구점 &amp; 전략
                </h2>
                <span className="text-[12px] text-secondary">
                  리뷰 {data.totalReviews.toLocaleString()}개 기반
                </span>
              </div>

              <div className="grid md:grid-cols-2 gap-10">
                {/* 핵심 소구점 */}
                <div>
                  <h3 className="text-[11px] font-bold text-secondary uppercase tracking-widest mb-6 border-l-4 border-primary pl-3">
                    핵심 소구점
                  </h3>
                  <div className="space-y-5">
                    {data.summary.marketingInsights.map((insight, i) => (
                      <div key={i} className="flex gap-4">
                        <div className="w-10 h-10 shrink-0 bg-primary/5 rounded-[14px] flex items-center justify-center">
                          <TrendingUp size={18} className="text-primary" />
                        </div>
                        <p className="text-[14px] text-on-surface leading-relaxed pt-2">
                          {insight}
                        </p>
                      </div>
                    ))}
                  </div>
                </div>

                {/* 개선 필요 포인트 */}
                <div>
                  <h3 className="text-[11px] font-bold text-secondary uppercase tracking-widest mb-6 border-l-4 border-negative pl-3">
                    개선 필요 포인트
                  </h3>
                  <div className="flex gap-4">
                    <div className="w-10 h-10 shrink-0 bg-negative/5 rounded-[14px] flex items-center justify-center">
                      <TrendingDown size={18} className="text-negative" />
                    </div>
                    <p className="text-[14px] text-on-surface leading-relaxed pt-2">
                      {data.summary.negative}
                    </p>
                  </div>
                </div>
              </div>
            </section>
          )}

          {/* ─── Row 3: 마인드맵 (8) + 사이드바 (4) ─── */}
          <div className="col-span-12 lg:col-span-8 bg-surface rounded-3xl overflow-hidden shadow-whisper">
            <div className="mindmap-bg flex flex-col" style={{ minHeight: 520 }}>
              {/* 마인드맵 헤더 */}
              <div className="px-6 py-5 flex items-center justify-between bg-surface/70 backdrop-blur-sm border-b border-outline-variant/10">
                <div>
                  <h2 className="font-headline font-bold text-[16px] text-on-surface">
                    키워드 마인드맵
                  </h2>
                  <p className="text-[12px] text-secondary mt-0.5">
                    노드를 클릭해 관련 리뷰를 필터링하세요
                  </p>
                </div>
                {activeNodeId && (
                  <button
                    onClick={clearNodeFilter}
                    className="flex items-center gap-1.5 text-[12px] text-primary font-medium hover:opacity-70 transition-opacity"
                  >
                    <X size={14} />
                    필터 해제
                  </button>
                )}
              </div>

              {/* D3 마인드맵 */}
              <div className="flex-1" style={{ height: 460 }}>
                <Mindmap
                  ref={svgRef}
                  root={data.mindmapRoot}
                  onNodeClick={handleNodeClick}
                  activeNodeId={activeNodeId}
                />
              </div>
            </div>
          </div>

          <div className="col-span-12 lg:col-span-4">
            <Sidebar onKeywordFilter={handleKeywordFilter} activeKeyword={activeKeyword} />
          </div>

          {/* ─── Row 4: 벤치마킹 비교 (12) — 세션이 있을 때만 표시 ─── */}
          {comparisonSessions.length > 0 && (
            <div className="col-span-12">
              <ComparisonView products={comparisonSessions[comparisonSessions.length - 1].products} />
            </div>
          )}

          {/* ─── Row 5: 리뷰 목록 (12) ─── */}
          <div className="col-span-12 bg-surface rounded-3xl overflow-hidden shadow-whisper">
            <ReviewList
              reviews={data.reviews}
              highlightKeyword={activeKeyword}
              filterIndices={filterIndices}
            />
          </div>

        </div>
      </main>
    </div>
  );
}
