import { useEffect, useRef, useState } from 'react';
import { useNavigate } from 'react-router-dom';
import { useLanguage } from '../contexts/LanguageContext';
import { useBrewContext } from '../contexts/BrewContext';

const Dashboard = () => {
  const { t } = useLanguage();
  const dash = t.dashboard;
  const common = t.common;
  const navigate = useNavigate();

  const { logs, isBrewing, currentStepIndex, emailStatus, emailError, clearLogs, clearEmailStatus, startBrew } = useBrewContext();

  const [showErrorModal, setShowErrorModal] = useState(false);
  const [showSuccessToast, setShowSuccessToast] = useState(false);
  const consoleRef = useRef<HTMLDivElement>(null);

  // 이메일 상태 감지
  useEffect(() => {
    if (emailStatus === 'success') {
      setShowSuccessToast(true);
      const t = setTimeout(() => {
        setShowSuccessToast(false);
        clearEmailStatus();
      }, 4000);
      return () => clearTimeout(t);
    }
    if (emailStatus === 'error') {
      setShowErrorModal(true);
    }
  }, [emailStatus]);

  useEffect(() => {
    if (consoleRef.current) {
      consoleRef.current.scrollTop = consoleRef.current.scrollHeight;
    }
  }, [logs]);

  const steps = [
    { id: 'collect', label: dash.stepCollect, icon: 'travel_explore' },
    { id: 'sheet', label: dash.stepSheet, icon: 'table_view' },
    { id: 'summary', label: dash.stepSummary, icon: 'psychology' },
    { id: 'mail', label: dash.stepMail, icon: 'forward_to_inbox' },
  ];

  return (
    <div className="flex h-full w-full">
      <div className="flex-1 flex flex-col p-6 md:p-12 overflow-y-auto">

        <header className="flex flex-col md:flex-row justify-between items-start md:items-center mb-10 gap-6">
          <div>
            <h1 className="font-headline text-4xl md:text-5xl font-bold text-primary tracking-tight mb-2">{dash.title}</h1>
            <p className="text-on-surface-variant font-body text-lg">{dash.subtitle}</p>
          </div>
        </header>

        <div className="flex flex-col gap-10">
          <section className="grid grid-cols-1 md:grid-cols-3 gap-6">
            {[
              { label: dash.todaysBrews, icon: 'local_cafe', sub: dash.todaysBrewsSub },
              { label: dash.activeKeywords, icon: 'vpn_key', sub: dash.activeKeywordsSub },
              { label: dash.nextBrew, icon: 'schedule', sub: dash.nextBrewSub },
            ].map(({ label, icon, sub }) => (
              <div key={label} className="bg-surface-container-high rounded-xl p-6 flex flex-col justify-between hover:bg-surface-container-highest hover:shadow-md transition-all duration-300 relative overflow-hidden group">
                <div className="absolute -right-4 -top-4 w-24 h-24 bg-surface-variant rounded-full opacity-50 group-hover:scale-110 transition-transform duration-500" />
                <div className="relative z-10">
                  <div className="flex items-center gap-2 mb-4">
                    <span className="material-symbols-outlined text-tertiary-container" style={{ fontVariationSettings: "'FILL' 1" }}>{icon}</span>
                    <span className="font-label text-sm uppercase tracking-widest text-on-surface-variant">{label}</span>
                  </div>
                  <div className="font-headline text-5xl font-bold text-primary">—</div>
                  <p className="font-body text-sm text-on-surface-variant mt-2">{sub}</p>
                </div>
              </div>
            ))}
          </section>

          <div className="grid grid-cols-1 lg:grid-cols-3 gap-10 items-start pb-24 md:pb-0">
            <section className="lg:col-span-2 flex flex-col gap-6">
              <div className="flex items-center justify-between px-2">
                <h3 className="font-headline font-bold text-2xl text-primary">{dash.pipeline}</h3>
                <span className="flex items-center gap-2 font-label text-xs uppercase tracking-widest text-on-surface-variant">
                  <span className={`w-2 h-2 rounded-full ${isBrewing ? 'bg-tertiary-fixed-dim animate-pulse' : 'bg-outline'}`} />
                  {isBrewing ? dash.live : dash.idle}
                </span>
              </div>

              <div className="bg-surface-container-low rounded-2xl p-6 flex flex-wrap sm:flex-nowrap justify-between items-center relative overflow-hidden shadow-sm border border-outline-variant/10">
                <div className="absolute left-10 right-10 top-[2.5rem] sm:top-1/2 -translate-y-1/2 h-0.5 bg-outline-variant/30 z-0 hidden sm:block" />
                {steps.map((step, idx) => {
                  const isActive = idx === currentStepIndex;
                  const isPast = idx < currentStepIndex;
                  return (
                    <div key={idx} className="relative z-10 flex flex-col items-center gap-3 flex-1">
                      <div className={`w-12 h-12 rounded-full flex justify-center items-center shadow-sm transition-all duration-300
                        ${isPast ? 'bg-primary text-on-primary scale-95' :
                          isActive ? 'bg-tertiary-container text-on-primary ring-4 ring-tertiary-container/30 scale-110' :
                          'bg-surface-container-high text-on-surface-variant'}`}>
                        <span className="material-symbols-outlined text-[20px]" style={{ fontVariationSettings: (isPast || isActive) ? "'FILL' 1" : "'FILL' 0" }}>{step.icon}</span>
                      </div>
                      <span className={`font-label text-xs uppercase tracking-wide ${(isPast || isActive) ? 'text-primary font-bold' : 'text-outline font-medium'}`}>
                        {step.label}
                      </span>
                    </div>
                  );
                })}
              </div>

              {/* 콘솔 */}
              <div className="bg-primary-container/95 rounded-2xl p-6 h-[260px] overflow-hidden relative shadow-lg flex flex-col border border-primary/20">
                <div className="absolute top-0 left-0 w-full h-8 bg-gradient-to-b from-primary-container to-transparent pointer-events-none z-10" />
                {/* 로그 삭제 버튼 */}
                {logs.length > 0 && !isBrewing && (
                  <button
                    onClick={clearLogs}
                    className="absolute top-3 right-4 z-20 flex items-center gap-1 text-[10px] font-label font-bold text-[#c4a882]/70 hover:text-[#c4a882] transition-colors"
                  >
                    <span className="material-symbols-outlined text-[14px]">delete_sweep</span>
                    초기화
                  </button>
                )}
                <div ref={consoleRef} className="flex-1 overflow-y-auto font-[JetBrains_Mono] text-sm space-y-2 pt-4 pb-4 pr-2 scrollbar-hide">
                  {logs.length === 0 ? (
                    <div className="flex gap-4 opacity-50">
                      <span className="text-[#c4a882]">--:--:--</span>
                      <span className="text-surface-variant">{dash.waitingText}</span>
                    </div>
                  ) : (
                    logs.map((log, i) => (
                      <div key={i} className="flex gap-4 animate-in fade-in slide-in-from-bottom-2 duration-300">
                        <span className="text-[#c4a882] shrink-0">{log.time}</span>
                        <span className={
                          log.level === 'ERROR' ? 'text-red-400' :
                          log.level === 'WARN' ? 'text-yellow-400' :
                          log.msg.includes('완료') || log.msg.includes('✅') || log.msg.includes('✉️') || log.msg.includes('🎉') ? 'text-[#a3e635]' :
                          log.msg.includes('AI') || log.msg.includes('🤖') ? 'text-[#ffb77d]' :
                          'text-secondary-fixed-dim'
                        }>
                          {log.msg}
                        </span>
                      </div>
                    ))
                  )}
                </div>
              </div>
            </section>

            <section className="lg:col-span-1 flex flex-col gap-6">
              <div className="bg-surface-container-low rounded-2xl p-6 flex flex-col gap-6 border border-outline-variant/10">
                <h3 className="font-headline font-bold text-xl text-primary border-b border-outline-variant/15 pb-4">Actions</h3>
                <button
                  onClick={startBrew}
                  disabled={isBrewing}
                  className="w-full py-4 px-6 bg-gradient-to-r from-primary to-primary-container text-on-primary rounded-xl font-headline font-bold text-base shadow-[0_8px_30px_rgba(51,33,13,0.12)] hover:-translate-y-0.5 transition-all duration-300 flex items-center justify-center gap-3 active:scale-95 disabled:opacity-50 disabled:pointer-events-none"
                >
                  <span className="material-symbols-outlined text-[20px]" style={{ fontVariationSettings: "'FILL' 1" }}>{isBrewing ? 'sync' : 'local_cafe'}</span>
                  {isBrewing ? common.brewing : dash.startNow}
                </button>

                <button
                  onClick={() => navigate('/archive')}
                  className="w-full py-3 px-6 border border-outline-variant/30 text-primary rounded-xl font-headline font-bold text-sm hover:bg-surface-variant transition-colors duration-300 flex items-center justify-center gap-3"
                >
                  <span className="material-symbols-outlined text-[20px]">description</span>
                  {dash.viewReport}
                </button>
              </div>

              <div className="bg-surface-container-highest/50 rounded-xl p-5 border border-outline-variant/10 relative overflow-hidden">
                <div className="absolute right-0 top-0 w-16 h-16 bg-tertiary-fixed/30 blur-xl rounded-full" />
                <div className="flex items-start gap-3 relative z-10">
                  <span className="material-symbols-outlined text-[#ff8c00] mt-1" style={{ fontVariationSettings: "'FILL' 1" }}>lightbulb</span>
                  <div>
                    <p className="font-label text-xs uppercase tracking-widest text-[#ff8c00] mb-1">{dash.aiInsight}</p>
                    <p className="font-body text-sm text-on-surface-variant font-medium">{dash.aiInsightText}</p>
                  </div>
                </div>
              </div>
            </section>
          </div>
        </div>
      </div>

      {/* 이메일 성공 토스트 */}
      {showSuccessToast && (
        <div className="fixed bottom-8 right-8 z-50 flex items-center gap-3 bg-[#1a2e1a] border border-[#a3e635]/30 text-[#a3e635] px-5 py-4 rounded-2xl shadow-2xl animate-in slide-in-from-bottom-4 duration-300">
          <span className="material-symbols-outlined text-[20px]" style={{ fontVariationSettings: "'FILL' 1" }}>mark_email_read</span>
          <div>
            <p className="font-label font-bold text-sm">이메일 발송 완료</p>
            <p className="font-body text-xs opacity-70 mt-0.5">리포트가 수신함으로 전송되었습니다</p>
          </div>
        </div>
      )}

      {/* 이메일 실패 모달 */}
      {showErrorModal && (
        <div className="fixed inset-0 bg-black/50 z-50 flex items-center justify-center p-4">
          <div className="bg-surface-container-low rounded-2xl p-8 max-w-md w-full shadow-2xl border border-error/20">
            <div className="flex items-center gap-3 mb-4">
              <span className="material-symbols-outlined text-error text-[28px]" style={{ fontVariationSettings: "'FILL' 1" }}>mail_lock</span>
              <h3 className="font-headline text-xl font-bold text-primary">이메일 발송 실패</h3>
            </div>
            <p className="font-body text-sm text-on-surface-variant leading-relaxed mb-6 bg-surface-container-highest/50 rounded-xl p-4 font-mono">
              {emailError}
            </p>
            <button
              onClick={() => { setShowErrorModal(false); clearEmailStatus(); }}
              className="w-full py-3 bg-primary text-on-primary rounded-xl font-label font-bold text-sm hover:bg-primary/90 transition-colors"
            >
              확인
            </button>
          </div>
        </div>
      )}
    </div>
  );
};

export default Dashboard;
