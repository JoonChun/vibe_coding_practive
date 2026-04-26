import { useState, useEffect } from 'react';
import { useLanguage } from '../contexts/LanguageContext';
import { useToast } from '../contexts/ToastContext';

const API_BASE = 'http://localhost:8000';

const SECRET_KEYS = new Set(['serpapi_key', 'openai_key', 'resend_key', 'google_service_account_json', 'gemini_api_key', 'naver_client_secret']);

interface FormState {
  schedule_time: string;
  news_provider: string;
  serpapi_key: string;
  naver_client_id: string;
  naver_client_secret: string;
  ai_provider: string;
  openai_key: string;
  gemini_api_key: string;
  gemini_model: string;
  resend_key: string;
  recipient_emails: string;
  google_sheet_id: string;
  google_service_account_json: string;
}

const DEFAULT_FORM: FormState = {
  schedule_time: '08:00',
  news_provider: 'serpapi',
  serpapi_key: '',
  naver_client_id: '',
  naver_client_secret: '',
  ai_provider: 'openai',
  openai_key: '',
  gemini_api_key: '',
  gemini_model: 'gemini-2.0-flash-preview-04-17',
  resend_key: '',
  recipient_emails: '',
  google_sheet_id: '',
  google_service_account_json: '',
};

type KeyStatus = Record<string, boolean>; // true = 키가 서버에 설정되어 있음

const ProviderTab = ({ value, current, onClick, children }: { value: string; current: string; onClick: (v: string) => void; children: React.ReactNode }) => (
  <button
    type="button"
    onClick={() => onClick(value)}
    className={`flex-1 py-2 px-4 rounded-lg font-label text-sm font-bold transition-all ${
      current === value
        ? 'bg-primary text-on-primary shadow'
        : 'text-on-surface-variant hover:bg-surface-variant'
    }`}
  >
    {children}
  </button>
);

const Field = ({ label, children, hint }: { label: string; children: React.ReactNode; hint?: string }) => (
  <div>
    <label className="font-label text-sm font-bold uppercase tracking-[0.05em] text-on-surface-variant mb-2 block">{label}</label>
    {children}
    {hint && <p className="text-xs text-on-surface-variant/60 mt-1">{hint}</p>}
  </div>
);

const inputClass = 'w-full bg-surface-container-lowest border border-outline-variant/30 rounded-xl p-3 font-body text-sm focus:border-primary focus:ring-1 focus:ring-primary/20 transition-all';

const SCHEDULE_TIME_RE = /^([01]\d|2[0-3]):([0-5]\d)$/;

const Settings = () => {
  const { t } = useLanguage();
  const st = t.settings;
  const { showToast } = useToast();

  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  // 취소 시 서버에서 로드한 값으로 복원하기 위해 별도로 보관
  const [savedForm, setSavedForm] = useState<FormState>(DEFAULT_FORM);
  const [keyStatus, setKeyStatus] = useState<KeyStatus>({});
  const [saveState, setSaveState] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle');
  const [scheduleError, setScheduleError] = useState('');

  useEffect(() => {
    let cancelled = false;
    (async () => {
      try {
        const res = await fetch(`${API_BASE}/api/settings`);
        if (!res.ok) throw new Error(`HTTP ${res.status}`);
        const data: Record<string, string> = await res.json();
        if (cancelled) return;

        const status: KeyStatus = {};
        const next: FormState = { ...DEFAULT_FORM };
        for (const [k, v] of Object.entries(data)) {
          if (SECRET_KEYS.has(k) && v === '***') {
            // 서버에 키 설정됨 → 플레이스홀더만 표시, form 값은 빈 문자열 유지
            status[k] = true;
          } else if (k in DEFAULT_FORM) {
            (next as Record<string, string>)[k] = v ?? '';
          }
        }
        setKeyStatus(status);
        setForm(next);
        setSavedForm(next);
      } catch {
        if (!cancelled) showToast('error', '설정을 불러올 수 없습니다 (백엔드 실행 중인지 확인)');
      }
    })();
    return () => { cancelled = true; };
  }, [showToast]);

  const set = (key: keyof FormState) => (e: React.ChangeEvent<HTMLInputElement | HTMLTextAreaElement>) =>
    setForm(prev => ({ ...prev, [key]: e.target.value }));

  const handleSave = async () => {
    // schedule_time 형식 검증
    if (!SCHEDULE_TIME_RE.test(form.schedule_time)) {
      setScheduleError('HH:MM 형식으로 입력하세요 (예: 08:00)');
      return;
    }
    setScheduleError('');
    setSaveState('saving');
    const body: Record<string, string | null> = {};
    for (const [k, v] of Object.entries(form)) {
      if (SECRET_KEYS.has(k)) {
        // 빈 문자열이면 기존 값 유지 (null = 서버에서 스킵)
        body[k] = v === '' ? null : v;
      } else {
        body[k] = v;
      }
    }
    try {
      const res = await fetch(`${API_BASE}/api/settings`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify(body),
      });
      if (!res.ok) throw new Error(`HTTP ${res.status}`);
      setSavedForm(form);
      setSaveState('saved');
      showToast('success', '설정이 저장되었습니다');
      setTimeout(() => setSaveState('idle'), 2000);
    } catch {
      setSaveState('error');
      showToast('error', '설정 저장에 실패했습니다');
      setTimeout(() => setSaveState('idle'), 3000);
    }
  };

  const handleCancel = () => {
    setForm(savedForm);
    setScheduleError('');
  };

  const secretPlaceholder = (key: string) => keyStatus[key] ? st.keySet : '';

  return (
    <div className="flex h-full w-full">
      <div className="flex-1 flex flex-col p-6 md:p-12 overflow-y-auto max-w-4xl mx-auto">

        <div className="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-6">
          <div>
            <h1 className="font-headline text-4xl md:text-5xl font-bold text-primary tracking-tight mb-2">{st.title}</h1>
            <p className="text-on-surface-variant font-body text-lg">{st.subtitle}</p>
          </div>
        </div>

        <div className="flex flex-col gap-8 pb-24 md:pb-0">

          {/* 뉴스 수집 API */}
          <section className="bg-surface-container-low rounded-2xl p-6 md:p-8 border border-outline-variant/10 shadow-[0_4px_20px_rgb(51,33,13,0.02)]">
            <h3 className="font-headline text-xl font-bold text-primary mb-1 flex items-center gap-2">
              <span className="material-symbols-outlined text-outline">travel_explore</span>
              {st.newsSource}
            </h3>
            <p className="text-on-surface-variant text-sm mb-6">{st.newsSourceDesc}</p>
            <div className="space-y-5">
              <div className="flex gap-2 bg-surface-container-highest/40 rounded-xl p-1">
                <ProviderTab value="serpapi" current={form.news_provider} onClick={v => setForm(p => ({ ...p, news_provider: v }))}>SerpAPI</ProviderTab>
                <ProviderTab value="naver" current={form.news_provider} onClick={v => setForm(p => ({ ...p, news_provider: v }))}>네이버</ProviderTab>
              </div>

              {form.news_provider === 'serpapi' ? (
                <Field label={st.serpApiKey}>
                  <input type="password" className={inputClass} value={form.serpapi_key} onChange={set('serpapi_key')} placeholder={secretPlaceholder('serpapi_key')} />
                </Field>
              ) : (
                <>
                  <Field label={st.naverClientId}>
                    <input type="text" className={inputClass} value={form.naver_client_id} onChange={set('naver_client_id')} />
                  </Field>
                  <Field label={st.naverClientSecret}>
                    <input type="password" className={inputClass} value={form.naver_client_secret} onChange={set('naver_client_secret')} placeholder={secretPlaceholder('naver_client_secret')} />
                  </Field>
                </>
              )}
            </div>
          </section>

          {/* AI 요약 엔진 */}
          <section className="bg-surface-container-low rounded-2xl p-6 md:p-8 border border-outline-variant/10 shadow-[0_4px_20px_rgb(51,33,13,0.02)]">
            <h3 className="font-headline text-xl font-bold text-primary mb-1 flex items-center gap-2">
              <span className="material-symbols-outlined text-outline">smart_toy</span>
              {st.aiEngine}
            </h3>
            <p className="text-on-surface-variant text-sm mb-6">{st.aiEngineDesc}</p>
            <div className="space-y-5">
              <div className="flex gap-2 bg-surface-container-highest/40 rounded-xl p-1">
                <ProviderTab value="openai" current={form.ai_provider} onClick={v => setForm(p => ({ ...p, ai_provider: v }))}>OpenAI</ProviderTab>
                <ProviderTab value="gemini" current={form.ai_provider} onClick={v => setForm(p => ({ ...p, ai_provider: v }))}>Gemini</ProviderTab>
              </div>

              {form.ai_provider === 'openai' ? (
                <Field label={st.openAiKey}>
                  <input type="password" className={inputClass} value={form.openai_key} onChange={set('openai_key')} placeholder={secretPlaceholder('openai_key')} />
                </Field>
              ) : (
                <>
                  <Field label={st.geminiApiKey}>
                    <input type="password" className={inputClass} value={form.gemini_api_key} onChange={set('gemini_api_key')} placeholder={secretPlaceholder('gemini_api_key')} />
                  </Field>
                  <Field label={st.geminiModel}>
                    <input type="text" className={inputClass} value={form.gemini_model} onChange={set('gemini_model')} />
                  </Field>
                </>
              )}
            </div>
          </section>

          {/* 이메일 발송 */}
          <section className="bg-surface-container-low rounded-2xl p-6 md:p-8 border border-outline-variant/10 shadow-[0_4px_20px_rgb(51,33,13,0.02)]">
            <h3 className="font-headline text-xl font-bold text-primary mb-6 flex items-center gap-2">
              <span className="material-symbols-outlined text-outline">mail</span>
              {st.emailApi}
            </h3>
            <div className="space-y-5">
              <Field label={st.resendKey}>
                <input type="password" className={inputClass} value={form.resend_key} onChange={set('resend_key')} placeholder={secretPlaceholder('resend_key')} />
              </Field>
              <Field label={st.recipientEmails}>
                <input type="text" className={inputClass} value={form.recipient_emails} onChange={set('recipient_emails')} placeholder="user@example.com, other@example.com" />
              </Field>
            </div>
          </section>

          {/* Google Sheets */}
          <section className="bg-surface-container-low rounded-2xl p-6 md:p-8 border border-outline-variant/10 shadow-[0_4px_20px_rgb(51,33,13,0.02)]">
            <h3 className="font-headline text-xl font-bold text-primary mb-6 flex items-center gap-2">
              <span className="material-symbols-outlined text-outline">table_chart</span>
              {st.googleSheets}
            </h3>
            <div className="space-y-5">
              <Field label={st.sheetId}>
                <input type="text" className={inputClass} value={form.google_sheet_id} onChange={set('google_sheet_id')} />
              </Field>
              <Field label={st.serviceAccountJson}>
                <textarea rows={4} className={inputClass + ' resize-none font-mono text-xs'} value={form.google_service_account_json} onChange={set('google_service_account_json')} placeholder={secretPlaceholder('google_service_account_json') || '{ "type": "service_account", ... }'} />
              </Field>
            </div>
          </section>

          {/* 일반 + 스케줄 */}
          <section className="bg-surface-container-low rounded-2xl p-6 md:p-8 border border-outline-variant/10 shadow-[0_4px_20px_rgb(51,33,13,0.02)]">
            <h3 className="font-headline text-xl font-bold text-primary mb-6 flex items-center gap-2">
              <span className="material-symbols-outlined text-outline">schedule</span>
              {st.schedule}
            </h3>
            <Field label={st.scheduleTime}>
              <input
                type="text"
                className={inputClass + (scheduleError ? ' border-error focus:border-error focus:ring-error/20' : '')}
                value={form.schedule_time}
                onChange={set('schedule_time')}
                placeholder="08:00"
              />
              {scheduleError && <p className="text-xs text-error mt-1">{scheduleError}</p>}
            </Field>
          </section>

          <div className="flex justify-end gap-3 mt-4">
            <button type="button" onClick={handleCancel} className="py-3 px-6 bg-transparent text-primary rounded-xl font-label font-bold text-sm hover:bg-surface-variant transition-colors">
              {st.cancel}
            </button>
            <button
              type="button"
              onClick={handleSave}
              disabled={saveState === 'saving'}
              className={`py-3 px-6 rounded-xl font-label font-bold text-sm transition-colors shadow-lg disabled:opacity-60 min-w-[120px] ${
                saveState === 'error'
                  ? 'bg-error text-on-error shadow-error/20'
                  : 'bg-primary text-on-primary hover:bg-primary/90 shadow-primary/20'
              }`}
            >
              {saveState === 'saving' ? st.saving : saveState === 'saved' ? st.saveSuccess : saveState === 'error' ? '저장 실패' : st.saveChanges}
            </button>
          </div>
        </div>
      </div>
    </div>
  );
};

export default Settings;
