import { useState, useEffect, useCallback } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { useToast } from '../contexts/ToastContext';

const API_BASE = 'http://localhost:8000';

interface Keyword {
  id: number;
  word: string;
  exclude_words: string;
  max_results: number;
  time_range_hours: number;
  is_active: boolean;
}

const Keywords = () => {
  const { t } = useLanguage();
  const kw = t.keywords;
  const { showToast } = useToast();

  const [keywords, setKeywords] = useState<Keyword[]>([]);
  const [selected, setSelected] = useState<Keyword | null>(null);
  const [showAddModal, setShowAddModal] = useState(false);
  const [newWord, setNewWord] = useState('');
  const [newExclude, setNewExclude] = useState('');
  const [adding, setAdding] = useState(false);

  // 사이드패널 controlled state
  const [panelExclude, setPanelExclude] = useState('');
  const [panelMaxResults, setPanelMaxResults] = useState(15);
  const [panelTimeRange, setPanelTimeRange] = useState(24);
  const [isCustomRange, setIsCustomRange] = useState(false);
  const [saving, setSaving] = useState(false);

  // selected 변경 시 패널 상태 동기화
  useEffect(() => {
    setPanelExclude(selected?.exclude_words ?? '');
    setPanelMaxResults(selected?.max_results ?? 15);
    const tr = selected?.time_range_hours ?? 24;
    setPanelTimeRange(tr);
    setIsCustomRange(tr !== 24 && tr !== 48);
  }, [selected?.id]);

  const fetchKeywords = useCallback(async (selectId?: number | null) => {
    try {
      const res = await fetch(`${API_BASE}/api/keywords`);
      if (!res.ok) {
        showToast('error', `목록 조회 실패: HTTP ${res.status}`);
        return;
      }
      const data: Keyword[] = await res.json();
      setKeywords(data);

      if (selectId !== undefined) {
        // 삭제 후: 명시적으로 선택할 ID 지정 (null이면 첫 번째 선택)
        if (selectId === null) {
          setSelected(data.length > 0 ? data[0] : null);
        } else {
          const found = data.find(k => k.id === selectId) ?? null;
          setSelected(found);
        }
      } else {
        // 초기 로드: selected 없을 때만 첫 번째 선택
        setSelected(prev => (prev === null && data.length > 0 ? data[0] : prev));
      }
    } catch {
      showToast('error', '서버에 연결할 수 없습니다 (백엔드 실행 중인지 확인)');
    }
  }, [showToast]);

  // eslint-disable-next-line react-hooks/exhaustive-deps
  useEffect(() => { fetchKeywords(); }, []);

  const handleAdd = async () => {
    if (!newWord.trim()) return;
    setAdding(true);
    try {
      const res = await fetch(`${API_BASE}/api/keywords`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ word: newWord.trim(), exclude_words: newExclude.trim() }),
      });
      if (res.ok) {
        const created: Keyword = await res.json();
        setNewWord('');
        setNewExclude('');
        setShowAddModal(false);
        await fetchKeywords(created.id);
        showToast('success', '키워드가 추가되었습니다', created.word);
      } else if (res.status === 409) {
        showToast('error', '이미 존재하는 키워드입니다');
      } else {
        showToast('error', `추가 실패: HTTP ${res.status}`);
      }
    } catch {
      showToast('error', '서버에 연결할 수 없습니다 (백엔드 실행 중인지 확인)');
    } finally {
      setAdding(false);
    }
  };

  const handleDelete = async (id: number) => {
    if (!confirm(kw.deleteConfirm)) return;
    const deletedWord = keywords.find(k => k.id === id)?.word;
    try {
      const res = await fetch(`${API_BASE}/api/keywords/${id}`, { method: 'DELETE' });
      if (!res.ok) {
        showToast('error', `삭제 실패: HTTP ${res.status}`);
        return;
      }
      await fetchKeywords(null);
      showToast('success', '키워드가 삭제되었습니다', deletedWord);
    } catch {
      showToast('error', '서버에 연결할 수 없습니다 (백엔드 실행 중인지 확인)');
    }
  };

  const handleSaveConfig = async () => {
    if (!selected) return;
    setSaving(true);
    try {
      const res = await fetch(`${API_BASE}/api/keywords/${selected.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          exclude_words: panelExclude,
          max_results: panelMaxResults,
          time_range_hours: panelTimeRange,
        }),
      });
      if (res.ok) {
        const updated: Keyword = await res.json();
        setKeywords(prev => prev.map(k => (k.id === updated.id ? updated : k)));
        setSelected(updated);
        showToast('success', '설정이 저장되었습니다', updated.word);
      } else {
        showToast('error', `저장 실패: HTTP ${res.status}`);
      }
    } catch {
      showToast('error', '서버에 연결할 수 없습니다 (백엔드 실행 중인지 확인)');
    } finally {
      setSaving(false);
    }
  };

  const handleDiscard = () => {
    setPanelExclude(selected?.exclude_words ?? '');
    setPanelMaxResults(selected?.max_results ?? 15);
    const tr = selected?.time_range_hours ?? 24;
    setPanelTimeRange(tr);
    setIsCustomRange(tr !== 24 && tr !== 48);
  };

  const handleToggleActive = async (item: Keyword) => {
    try {
      const res = await fetch(`${API_BASE}/api/keywords/${item.id}`, {
        method: 'PATCH',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ is_active: !item.is_active }),
      });
      if (res.ok) {
        const updated: Keyword = await res.json();
        setKeywords(prev => prev.map(k => k.id === updated.id ? updated : k));
        if (selected?.id === updated.id) setSelected(updated);
        showToast('info', updated.is_active ? '분석 대상에 추가되었습니다' : '분석 대상에서 제외되었습니다', updated.word);
      } else {
        showToast('error', `상태 변경 실패: HTTP ${res.status}`);
      }
    } catch {
      showToast('error', '서버에 연결할 수 없습니다 (백엔드 실행 중인지 확인)');
    }
  };

  const initials = (word: string) => word.slice(0, 2).toUpperCase();

  return (
    <div className="flex h-full w-full">
      {/* Main Content */}
      <div className="flex-1 flex flex-col p-6 md:p-12 overflow-y-auto">

        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-6">
          <div>
            <h1 className="font-headline text-4xl md:text-5xl font-bold text-primary tracking-tight mb-2">{kw.title}</h1>
            <p className="text-on-surface-variant font-body text-lg">{kw.subtitle}</p>
          </div>
          <button
            onClick={() => setShowAddModal(true)}
            className="bg-primary-container text-on-primary rounded-xl px-6 py-3 font-label font-bold text-sm hover:bg-primary transition-colors flex items-center gap-2 shadow-sm shadow-primary/10"
          >
            <span className="material-symbols-outlined">add</span>
            {kw.addNew}
          </button>
        </div>

        {/* Keyword Cards */}
        {keywords.length === 0 ? (
          <div className="flex flex-col items-center justify-center flex-1 text-center py-24 opacity-60">
            <span className="material-symbols-outlined text-6xl text-outline mb-4">coffee</span>
            <p className="font-headline text-xl text-primary mb-1">{kw.noKeywords}</p>
            <p className="font-body text-sm text-on-surface-variant">{kw.noKeywordsSub}</p>
          </div>
        ) : (
          <div className="grid grid-cols-1 lg:grid-cols-2 gap-6 pb-24 md:pb-0">
            {keywords.map(item => (
              <div
                key={item.id}
                onClick={() => setSelected(item)}
                className={`bg-surface-container-low rounded-2xl p-6 relative group transition-all duration-300 hover:bg-surface-container-highest shadow-[0_8px_30px_rgb(51,33,13,0.02)] hover:shadow-[0_8px_30px_rgb(51,33,13,0.06)] border cursor-pointer ${
                  selected?.id === item.id ? 'border-primary/40' : 'border-outline-variant/10'
                }`}
              >
                <div className="flex justify-between items-start mb-6">
                  <div className="flex items-center gap-4">
                    <div className="w-12 h-12 rounded-full bg-primary-fixed flex items-center justify-center text-primary font-headline font-bold text-base">
                      {initials(item.word)}
                    </div>
                    <div>
                      <h3 className="font-headline text-xl font-bold text-primary">{item.word}</h3>
                      {item.exclude_words && (
                        <p className="text-xs text-outline mt-1 font-body">제외: {item.exclude_words}</p>
                      )}
                    </div>
                  </div>
                  <div className="flex gap-2 opacity-0 group-hover:opacity-100 transition-opacity">
                    <button
                      onClick={e => { e.stopPropagation(); handleDelete(item.id); }}
                      className="p-2 text-outline hover:text-error transition-colors rounded-full hover:bg-error-container/50"
                    >
                      <span className="material-symbols-outlined">delete</span>
                    </button>
                  </div>
                </div>
                <div className="flex items-center justify-between border-t border-outline-variant/20 pt-4">
                  <div className="flex items-center gap-3" onClick={e => e.stopPropagation()}>
                    <span className={`font-label text-sm font-bold uppercase tracking-widest ${item.is_active ? 'text-[#ff8c00]' : 'text-outline'}`}>
                      {item.is_active ? '분석 중' : '비활성'}
                    </span>
                    <label className="relative inline-flex items-center cursor-pointer">
                      <input
                        type="checkbox"
                        className="sr-only peer"
                        checked={item.is_active}
                        onChange={() => handleToggleActive(item)}
                      />
                      <div className="w-11 h-6 bg-surface-variant peer-focus:outline-none rounded-full peer peer-checked:after:translate-x-full peer-checked:after:border-white after:content-[''] after:absolute after:top-[2px] after:left-[2px] after:bg-white after:border-gray-300 after:border after:rounded-full after:h-5 after:w-5 after:transition-all peer-checked:bg-[#ff8c00]" />
                    </label>
                  </div>
                </div>
              </div>
            ))}
          </div>
        )}
      </div>

      {/* Detail Panel */}
      <aside className="w-[360px] xl:w-[420px] shrink-0 bg-surface-container-lowest border-l border-outline-variant/15 p-8 overflow-y-auto hidden md:flex flex-col relative z-10 shadow-[-10px_0_30px_rgb(51,33,13,0.02)]">
        {selected ? (
          <>
            <div className="mb-10">
              <span className="font-label text-xs font-bold uppercase tracking-widest text-tertiary mb-2 block">{kw.config}</span>
              <h2 className="font-headline text-3xl font-bold text-primary">{selected.word}</h2>
            </div>

            <div className="space-y-8 flex-grow">
              <div>
                <label className="font-label text-sm font-bold uppercase tracking-[0.05em] text-on-surface-variant mb-4 block">{kw.brewWindow}</label>
                <div className="flex bg-surface-container-low rounded-lg p-1 border border-outline-variant/10">
                  <button
                    onClick={() => { setPanelTimeRange(24); setIsCustomRange(false); }}
                    className={`flex-1 py-2 text-sm font-label rounded-md transition-all ${
                      !isCustomRange && panelTimeRange === 24
                        ? 'bg-surface-container-lowest shadow-sm text-primary font-bold'
                        : 'text-outline hover:text-primary font-medium'
                    }`}
                  >24h</button>
                  <button
                    onClick={() => { setPanelTimeRange(48); setIsCustomRange(false); }}
                    className={`flex-1 py-2 text-sm font-label rounded-md transition-all ${
                      !isCustomRange && panelTimeRange === 48
                        ? 'bg-surface-container-lowest shadow-sm text-primary font-bold'
                        : 'text-outline hover:text-primary font-medium'
                    }`}
                  >48h</button>
                  <button
                    onClick={() => {
                      setIsCustomRange(true);
                      if (panelTimeRange === 24 || panelTimeRange === 48) setPanelTimeRange(72);
                    }}
                    className={`flex-1 py-2 text-sm font-label rounded-md transition-all ${
                      isCustomRange
                        ? 'bg-surface-container-lowest shadow-sm text-primary font-bold'
                        : 'text-outline hover:text-primary font-medium'
                    }`}
                  >Custom</button>
                </div>
                {isCustomRange && (
                  <div className="mt-3 flex items-center gap-2">
                    <input
                      type="number"
                      min={1}
                      max={168}
                      value={panelTimeRange}
                      onChange={e => setPanelTimeRange(Math.max(1, Math.min(168, Number(e.target.value) || 1)))}
                      className="flex-1 bg-surface-container-low border border-outline-variant/30 rounded-lg px-3 py-2 font-body text-sm text-primary focus:border-primary focus:ring-0"
                    />
                    <span className="text-sm font-label text-outline">시간</span>
                  </div>
                )}
              </div>

              <div>
                <div className="flex justify-between items-end mb-4">
                  <label className="font-label text-sm font-bold uppercase tracking-[0.05em] text-on-surface-variant block">{kw.maxBeans}</label>
                  <span className="font-headline font-bold text-primary text-xl">{panelMaxResults}</span>
                </div>
                <input
                  type="range" min="10" max="100" step="5"
                  value={panelMaxResults}
                  onChange={e => setPanelMaxResults(Number(e.target.value))}
                  className="w-full h-2 bg-surface-variant rounded-lg appearance-none cursor-pointer accent-[#ff8c00]"
                />
                <div className="flex justify-between mt-2 text-xs font-label text-outline">
                  <span>10</span><span>100</span>
                </div>
              </div>

              <div>
                <label className="font-label text-sm font-bold uppercase tracking-[0.05em] text-on-surface-variant mb-2 block">{kw.excludeLabel}</label>
                <input
                  type="text"
                  value={panelExclude}
                  onChange={e => setPanelExclude(e.target.value)}
                  placeholder="e.g. 광고, PR, 홍보"
                  className="w-full bg-surface-container-low border-b border-outline-variant focus:border-[#ff8c00] focus:ring-0 px-2 py-3 font-body text-sm text-primary placeholder:text-outline transition-colors"
                />
              </div>

              <div className="pt-4 border-t border-outline-variant/20">
                <label className="font-label text-sm font-bold uppercase tracking-[0.05em] text-on-surface-variant mb-2 flex items-center gap-2">
                  <span className="material-symbols-outlined text-[18px]">psychology</span>
                  {kw.aiPrompt}
                </label>
                <p className="text-xs text-outline font-body mb-3">{kw.aiPromptSub}</p>
                <textarea rows={4} placeholder="E.g. Focus on breakthroughs in neural networks..." className="w-full bg-primary-container/10 border-b border-outline-variant focus:border-[#ff8c00] focus:ring-0 p-4 font-body text-sm text-primary placeholder:text-outline/70 transition-colors rounded-t-md resize-none" />
              </div>
            </div>

            <div className="pt-8 mt-auto flex gap-3">
              <button
                onClick={handleDiscard}
                className="flex-1 py-3 px-4 bg-transparent border border-outline-variant/30 text-primary rounded-xl font-label font-bold text-sm hover:bg-surface-variant transition-colors"
              >
                {kw.discard}
              </button>
              <button
                onClick={handleSaveConfig}
                disabled={saving}
                className="flex-[2] py-3 px-4 bg-primary-container text-on-primary rounded-xl font-label font-bold text-sm hover:bg-primary transition-colors shadow-sm shadow-primary/10 disabled:opacity-50"
              >
                {saving ? '저장 중...' : kw.saveConfig}
              </button>
            </div>
          </>
        ) : (
          <div className="flex-1 flex items-center justify-center text-center opacity-40">
            <div>
              <span className="material-symbols-outlined text-5xl text-outline mb-3 block">coffee</span>
              <p className="font-body text-sm text-on-surface-variant">키워드를 선택하면<br />설정이 표시됩니다</p>
            </div>
          </div>
        )}
      </aside>

      {/* Add Modal */}
      {showAddModal && (
        <div className="fixed inset-0 bg-black/40 z-50 flex items-center justify-center p-4" onClick={() => setShowAddModal(false)}>
          <div className="bg-surface-container-low rounded-2xl p-8 w-full max-w-md shadow-2xl" onClick={e => e.stopPropagation()}>
            <h2 className="font-headline text-2xl font-bold text-primary mb-6">{kw.addNew}</h2>
            <div className="space-y-4 mb-8">
              <div>
                <label className="font-label text-sm font-bold uppercase tracking-[0.05em] text-on-surface-variant mb-2 block">{kw.wordLabel}</label>
                <input
                  type="text"
                  value={newWord}
                  onChange={e => setNewWord(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAdd()}
                  placeholder="예: 인공지능, AI, ChatGPT"
                  className="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-3 font-body text-sm focus:border-primary focus:ring-1 focus:ring-primary/20 transition-all"
                  autoFocus
                />
              </div>
              <div>
                <label className="font-label text-sm font-bold uppercase tracking-[0.05em] text-on-surface-variant mb-2 block">{kw.excludeLabel}</label>
                <input
                  type="text"
                  value={newExclude}
                  onChange={e => setNewExclude(e.target.value)}
                  onKeyDown={e => e.key === 'Enter' && handleAdd()}
                  placeholder="예: 광고, 홍보, PR"
                  className="w-full bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-3 font-body text-sm focus:border-primary focus:ring-1 focus:ring-primary/20 transition-all"
                />
              </div>
            </div>
            <div className="flex gap-3">
              <button onClick={() => setShowAddModal(false)} className="flex-1 py-3 bg-transparent border border-outline-variant/30 text-primary rounded-xl font-label font-bold text-sm hover:bg-surface-variant transition-colors">
                {kw.discard}
              </button>
              <button onClick={handleAdd} disabled={adding || !newWord.trim()} className="flex-[2] py-3 bg-primary text-on-primary rounded-xl font-label font-bold text-sm hover:bg-primary/90 transition-colors disabled:opacity-50">
                {adding ? '...' : kw.add}
              </button>
            </div>
          </div>
        </div>
      )}
    </div>
  );
};

export default Keywords;
