import { useState, useEffect, useMemo } from 'react';
import { useLanguage } from '../contexts/LanguageContext';

const API_BASE = 'http://localhost:8000';

interface DateGroup {
  date: string;
  summary_count: number;
}

interface ArchiveItem {
  id: number;
  keyword: string;
  title: string;
  url: string;
  source: string;
  published_at: string;
  summary: string;
  importance_score: number;
}

function ImportanceBadge({ score }: { score: number }) {
  const color =
    score >= 8
      ? 'bg-[#ff8c00]/15 text-[#b85c00] border-[#ff8c00]/30'
      : score >= 6
      ? 'bg-primary-fixed/20 text-primary border-primary/20'
      : 'bg-surface-variant text-outline border-outline-variant/20';
  return (
    <span className={`inline-flex items-center gap-1 px-2 py-0.5 rounded-full border text-xs font-label font-bold ${color}`}>
      <span className="material-symbols-outlined text-[12px]">star</span>
      {score}
    </span>
  );
}

function SkeletonCard() {
  return (
    <div className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/10 animate-pulse">
      <div className="flex items-center gap-2 mb-3">
        <div className="h-3 w-16 bg-surface-variant rounded-full" />
        <div className="h-3 w-20 bg-surface-variant rounded-full" />
      </div>
      <div className="h-4 w-3/4 bg-surface-variant rounded-full mb-2" />
      <div className="h-4 w-1/2 bg-surface-variant rounded-full mb-4" />
      <div className="space-y-1.5">
        <div className="h-3 w-full bg-surface-variant rounded-full" />
        <div className="h-3 w-5/6 bg-surface-variant rounded-full" />
        <div className="h-3 w-4/6 bg-surface-variant rounded-full" />
      </div>
    </div>
  );
}

const Archive = () => {
  const { t } = useLanguage();
  const ar = t.archive;

  const [dateGroups, setDateGroups] = useState<DateGroup[]>([]);
  const [selectedDate, setSelectedDate] = useState<string | null>(null);
  const [items, setItems] = useState<ArchiveItem[]>([]);
  const [loadingGroups, setLoadingGroups] = useState(true);
  const [loadingItems, setLoadingItems] = useState(false);
  const [searchQuery, setSearchQuery] = useState('');
  const [expandedId, setExpandedId] = useState<number | null>(null);
  const [selectedKeyword, setSelectedKeyword] = useState<string | null>(null);

  // 날짜 그룹 로드
  useEffect(() => {
    const load = async () => {
      setLoadingGroups(true);
      try {
        const res = await fetch(`${API_BASE}/api/archives/dates`);
        if (res.ok) {
          const data: DateGroup[] = await res.json();
          setDateGroups(data);
          if (data.length > 0) setSelectedDate(data[0].date);
        }
      } catch {}
      setLoadingGroups(false);
    };
    load();
  }, []);

  // 날짜별 아이템 로드
  useEffect(() => {
    if (!selectedDate) return;
    const load = async () => {
      setLoadingItems(true);
      setItems([]);
      setExpandedId(null);
      setSelectedKeyword(null);
      try {
        const res = await fetch(`${API_BASE}/api/archives/${selectedDate}`);
        if (res.ok) {
          const data: ArchiveItem[] = await res.json();
          setItems(data);
        }
      } catch {}
      setLoadingItems(false);
    };
    load();
  }, [selectedDate]);

  // 키워드별 카운트 (선택된 날짜 안에서)
  const keywordCounts = useMemo(() => {
    const map = new Map<string, number>();
    for (const item of items) {
      map.set(item.keyword, (map.get(item.keyword) ?? 0) + 1);
    }
    return Array.from(map.entries()).sort((a, b) => b[1] - a[1]);
  }, [items]);

  // 클라이언트 필터링 (검색 + 키워드 칩, AND)
  const filteredItems = useMemo(() => {
    let result = items;
    if (selectedKeyword) {
      result = result.filter((item) => item.keyword === selectedKeyword);
    }
    if (searchQuery.trim()) {
      const q = searchQuery.toLowerCase();
      result = result.filter(
        (item) =>
          item.title.toLowerCase().includes(q) ||
          item.keyword.toLowerCase().includes(q) ||
          item.source.toLowerCase().includes(q)
      );
    }
    return result;
  }, [items, searchQuery, selectedKeyword]);

  // 날짜 포맷
  const formatDate = (dateStr: string) => {
    const d = new Date(dateStr);
    return d.toLocaleDateString('ko-KR', { year: 'numeric', month: 'long', day: 'numeric', weekday: 'short' });
  };

  // published_at 포맷
  const formatPublished = (iso: string) => {
    try {
      return new Date(iso).toLocaleString('ko-KR', {
        month: 'short', day: 'numeric', hour: '2-digit', minute: '2-digit', hour12: false,
      });
    } catch {
      return iso;
    }
  };

  return (
    <div className="flex h-full w-full">
      {/* Main Content */}
      <div className="flex-1 flex flex-col p-6 md:p-12 overflow-y-auto">

        {/* Page Header */}
        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-6">
          <div>
            <h1 className="font-headline text-4xl md:text-5xl font-bold text-primary tracking-tight mb-2">{ar.title}</h1>
            <p className="text-on-surface-variant font-body text-lg">{ar.subtitle}</p>
          </div>
          <div className="relative">
            <input
              type="text"
              placeholder={ar.search}
              value={searchQuery}
              onChange={(e) => setSearchQuery(e.target.value)}
              className="pl-10 pr-4 py-2 bg-surface-container-low border border-outline-variant/30 rounded-xl font-body text-sm focus:border-primary focus:ring-0 w-64 transition-colors"
            />
            <span className="material-symbols-outlined absolute left-3 top-1/2 -translate-y-1/2 text-outline text-[20px]">
              search
            </span>
          </div>
        </div>

        {/* No data — 날짜 그룹 로딩 완료 후 데이터 없음 */}
        {!loadingGroups && dateGroups.length === 0 && (
          <div className="flex flex-col items-center justify-center flex-1 bg-surface-container-low/50 rounded-3xl border border-outline-variant/10 border-dashed p-12 text-center h-[400px] mb-24 md:mb-0">
            <div className="w-20 h-20 bg-surface-variant rounded-full flex items-center justify-center mb-6">
              <span className="material-symbols-outlined text-4xl text-outline">inbox</span>
            </div>
            <h3 className="font-headline text-2xl font-bold text-primary mb-2">{ar.noBrews}</h3>
            <p className="font-body text-on-surface-variant max-w-md">{ar.noBrewsSub}</p>
          </div>
        )}

        {/* Content Grid */}
        {(loadingGroups || dateGroups.length > 0) && (
          <div className="grid grid-cols-1 lg:grid-cols-4 gap-8 pb-24 md:pb-0 items-start">

            {/* 날짜 사이드바 */}
            <aside className="lg:col-span-1">
              <h2 className="font-label text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-4 px-1">
                날짜별 브루
              </h2>
              <nav className="flex flex-col gap-2">
                {loadingGroups
                  ? Array.from({ length: 5 }).map((_, i) => (
                      <div key={i} className="h-14 bg-surface-container-low rounded-xl animate-pulse" />
                    ))
                  : dateGroups.map((g) => {
                      const isActive = g.date === selectedDate;
                      return (
                        <button
                          key={g.date}
                          onClick={() => setSelectedDate(g.date)}
                          className={`w-full text-left px-4 py-3 rounded-xl border transition-all duration-200 ${
                            isActive
                              ? 'bg-primary-container border-primary/30 shadow-sm'
                              : 'bg-surface-container border-outline-variant/20 hover:bg-surface-container-highest hover:border-outline-variant/40'
                          }`}
                        >
                          <div className="font-label text-sm font-bold text-white">
                            {formatDate(g.date)}
                          </div>
                          <div className="font-body text-xs mt-0.5 font-medium text-white/60">
                            기사 {g.summary_count}건
                          </div>
                        </button>
                      );
                    })}
              </nav>
            </aside>

            {/* 아이템 리스트 */}
            <section className="lg:col-span-3 flex flex-col gap-5">
              {/* 선택된 날짜 헤더 */}
              {selectedDate && !loadingGroups && (
                <div className="flex items-center justify-between px-1">
                  <div>
                    <h2 className="font-headline font-bold text-2xl text-primary">
                      {formatDate(selectedDate)}
                    </h2>
                    {!loadingItems && (
                      <p className="font-body text-sm text-on-surface-variant mt-0.5">
                        {searchQuery || selectedKeyword
                          ? `${filteredItems.length}건 / 전체 ${items.length}건`
                          : `총 ${items.length}건의 기사`}
                      </p>
                    )}
                  </div>
                </div>
              )}

              {/* 키워드 칩 필터 */}
              {!loadingItems && keywordCounts.length > 0 && (
                <div className="flex items-center gap-2 px-1 overflow-x-auto pb-1">
                  <button
                    onClick={() => setSelectedKeyword(null)}
                    className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-label font-bold border transition-all ${
                      selectedKeyword === null
                        ? 'bg-primary text-on-primary border-primary shadow-sm'
                        : 'bg-surface-container-low text-on-surface-variant border-outline-variant/20 hover:bg-surface-container-highest'
                    }`}
                  >
                    전체 ({items.length})
                  </button>
                  {keywordCounts.map(([kw, count]) => (
                    <button
                      key={kw}
                      onClick={() => setSelectedKeyword(kw)}
                      className={`shrink-0 px-3 py-1.5 rounded-full text-xs font-label font-bold border transition-all ${
                        selectedKeyword === kw
                          ? 'bg-primary text-on-primary border-primary shadow-sm'
                          : 'bg-surface-container-low text-on-surface-variant border-outline-variant/20 hover:bg-surface-container-highest'
                      }`}
                    >
                      {kw} ({count})
                    </button>
                  ))}
                </div>
              )}

              {/* 로딩 스켈레톤 */}
              {loadingItems &&
                Array.from({ length: 4 }).map((_, i) => <SkeletonCard key={i} />)}

              {/* 검색/필터 결과 없음 */}
              {!loadingItems && (searchQuery || selectedKeyword) && filteredItems.length === 0 && (
                <div className="flex flex-col items-center justify-center py-16 text-center opacity-60">
                  <span className="material-symbols-outlined text-5xl text-outline mb-3">search_off</span>
                  <p className="font-headline text-lg text-primary mb-1">일치하는 기사가 없습니다</p>
                  <p className="font-body text-sm text-on-surface-variant">
                    {searchQuery && selectedKeyword
                      ? `"${selectedKeyword}" 키워드 + "${searchQuery}" 검색 조건`
                      : searchQuery
                      ? `"${searchQuery}" 와 일치하는 기사가 없습니다`
                      : `"${selectedKeyword}" 키워드의 기사가 없습니다`}
                  </p>
                </div>
              )}

              {/* 아이템 카드 */}
              {!loadingItems &&
                filteredItems.map((item) => {
                  const isExpanded = expandedId === item.id;
                  return (
                    <div
                      key={item.id}
                      className="bg-surface-container-low rounded-2xl border border-outline-variant/10 shadow-[0_8px_30px_rgb(51,33,13,0.02)] hover:shadow-[0_8px_30px_rgb(51,33,13,0.06)] transition-all duration-300 overflow-hidden"
                    >
                      <div className="p-5">
                        {/* 메타 행 */}
                        <div className="flex flex-wrap items-center gap-2 mb-3">
                          <span className="bg-primary-fixed/20 text-primary border border-primary/15 text-xs font-label font-bold px-2.5 py-0.5 rounded-full">
                            {item.keyword}
                          </span>
                          <span className="text-xs font-body text-outline">{item.source}</span>
                          <span className="text-outline/40 text-xs">·</span>
                          <span className="text-xs font-body text-outline">{formatPublished(item.published_at)}</span>
                          <div className="ml-auto">
                            <ImportanceBadge score={item.importance_score} />
                          </div>
                        </div>

                        {/* 제목 (링크) */}
                        <a
                          href={item.url}
                          target="_blank"
                          rel="noopener noreferrer"
                          className="font-headline font-bold text-primary text-base leading-snug hover:text-primary/70 transition-colors line-clamp-2 block mb-3"
                        >
                          {item.title}
                        </a>

                        {/* AI 요약 */}
                        <p className={`font-body text-sm text-on-surface-variant leading-relaxed ${isExpanded ? '' : 'line-clamp-2'}`}>
                          {item.summary}
                        </p>

                        {/* 하단 액션 */}
                        <div className="flex items-center justify-between mt-3 pt-3 border-t border-outline-variant/15">
                          <button
                            onClick={() => setExpandedId(isExpanded ? null : item.id)}
                            className="flex items-center gap-1 text-xs font-label font-bold text-outline hover:text-primary transition-colors"
                          >
                            <span className="material-symbols-outlined text-[16px]">
                              {isExpanded ? 'expand_less' : 'expand_more'}
                            </span>
                            {isExpanded ? '요약 접기' : '요약 더보기'}
                          </button>
                          <a
                            href={item.url}
                            target="_blank"
                            rel="noopener noreferrer"
                            className="flex items-center gap-1 text-xs font-label font-bold text-outline hover:text-primary transition-colors"
                          >
                            원문 보기
                            <span className="material-symbols-outlined text-[16px]">open_in_new</span>
                          </a>
                        </div>
                      </div>
                    </div>
                  );
                })}
            </section>
          </div>
        )}
      </div>
    </div>
  );
};

export default Archive;
