import { useState } from 'react';
import { useLanguage } from '../contexts/LanguageContext';

const StepCard = ({ icon, title, body }: { icon: string; title: string; body: string }) => (
  <div className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/10 shadow-[0_8px_30px_rgb(51,33,13,0.02)]">
    <div className="flex items-start gap-3">
      <div className="w-10 h-10 shrink-0 rounded-xl bg-primary-container/40 text-primary flex items-center justify-center">
        <span className="material-symbols-outlined text-[22px]">{icon}</span>
      </div>
      <div>
        <h3 className="font-headline font-bold text-primary text-base mb-1">{title}</h3>
        <p className="font-body text-sm text-on-surface-variant leading-relaxed">{body}</p>
      </div>
    </div>
  </div>
);

const FeatureCard = ({ icon, title, body }: { icon: string; title: string; body: string }) => (
  <div className="bg-surface-container-low rounded-2xl p-5 border border-outline-variant/10 hover:shadow-[0_8px_30px_rgb(51,33,13,0.06)] transition-shadow">
    <div className="w-10 h-10 rounded-xl bg-primary-fixed/20 text-primary flex items-center justify-center mb-3">
      <span className="material-symbols-outlined text-[22px]">{icon}</span>
    </div>
    <h3 className="font-headline font-bold text-primary text-base mb-1">{title}</h3>
    <p className="font-body text-sm text-on-surface-variant leading-relaxed">{body}</p>
  </div>
);

const FaqItem = ({ q, a, isOpen, onToggle }: { q: string; a: string; isOpen: boolean; onToggle: () => void }) => (
  <div className="bg-surface-container-low rounded-2xl border border-outline-variant/10 overflow-hidden">
    <button
      type="button"
      onClick={onToggle}
      className="w-full flex items-center justify-between gap-4 p-5 text-left hover:bg-surface-container transition-colors"
    >
      <span className="font-headline font-bold text-primary text-sm md:text-base">{q}</span>
      <span
        className="material-symbols-outlined text-outline shrink-0 transition-transform"
        style={{ transform: isOpen ? 'rotate(180deg)' : 'rotate(0deg)' }}
      >
        expand_more
      </span>
    </button>
    {isOpen && (
      <div className="px-5 pb-5 -mt-1">
        <p className="font-body text-sm text-on-surface-variant leading-relaxed">{a}</p>
      </div>
    )}
  </div>
);

const Help = () => {
  const { t } = useLanguage();
  const h = t.help;
  const [openFaq, setOpenFaq] = useState<number | null>(0);

  const steps = [
    { icon: 'key', title: h.step1Title, body: h.step1Body },
    { icon: 'temp_preferences_custom', title: h.step2Title, body: h.step2Body },
    { icon: 'schedule', title: h.step3Title, body: h.step3Body },
    { icon: 'task_alt', title: h.step4Title, body: h.step4Body },
  ];

  const features = [
    { icon: 'dashboard', title: h.featDashboardTitle, body: h.featDashboardBody },
    { icon: 'temp_preferences_custom', title: h.featKeywordsTitle, body: h.featKeywordsBody },
    { icon: 'auto_stories', title: h.featArchiveTitle, body: h.featArchiveBody },
    { icon: 'settings', title: h.featSettingsTitle, body: h.featSettingsBody },
  ];

  const faqs = [
    { q: h.faq1Q, a: h.faq1A },
    { q: h.faq2Q, a: h.faq2A },
    { q: h.faq3Q, a: h.faq3A },
    { q: h.faq4Q, a: h.faq4A },
  ];

  return (
    <div className="flex h-full w-full">
      <div className="flex-1 flex flex-col p-6 md:p-12 overflow-y-auto pb-24 md:pb-12">

        {/* Page Header */}
        <div className="mb-10">
          <h1 className="font-headline text-4xl md:text-5xl font-bold text-primary tracking-tight mb-2">{h.title}</h1>
          <p className="text-on-surface-variant font-body text-lg">{h.subtitle}</p>
        </div>

        <div className="flex flex-col gap-12 max-w-5xl">

          {/* Getting Started */}
          <section>
            <h2 className="font-label text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-4 px-1">
              {h.gettingStartedTitle}
            </h2>
            <p className="font-body text-on-surface-variant leading-relaxed mb-5 px-1">
              {h.gettingStartedBody}
            </p>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {steps.map((s, i) => (
                <StepCard key={i} icon={s.icon} title={s.title} body={s.body} />
              ))}
            </div>
          </section>

          {/* Features */}
          <section>
            <h2 className="font-label text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-4 px-1">
              {h.featuresTitle}
            </h2>
            <div className="grid grid-cols-1 md:grid-cols-2 gap-4">
              {features.map((f, i) => (
                <FeatureCard key={i} icon={f.icon} title={f.title} body={f.body} />
              ))}
            </div>
          </section>

          {/* FAQ */}
          <section>
            <h2 className="font-label text-xs font-bold uppercase tracking-widest text-on-surface-variant mb-4 px-1">
              {h.faqTitle}
            </h2>
            <div className="flex flex-col gap-3">
              {faqs.map((f, i) => (
                <FaqItem
                  key={i}
                  q={f.q}
                  a={f.a}
                  isOpen={openFaq === i}
                  onToggle={() => setOpenFaq(openFaq === i ? null : i)}
                />
              ))}
            </div>
          </section>

          {/* Contact */}
          <section className="bg-primary-container/30 rounded-2xl p-6 border border-primary/15">
            <div className="flex items-start gap-4">
              <div className="w-10 h-10 shrink-0 rounded-xl bg-primary text-on-primary flex items-center justify-center">
                <span className="material-symbols-outlined text-[22px]">support_agent</span>
              </div>
              <div>
                <h3 className="font-headline font-bold text-primary text-base mb-1">{h.contactTitle}</h3>
                <p className="font-body text-sm text-on-surface-variant leading-relaxed">{h.contactBody}</p>
              </div>
            </div>
          </section>

        </div>
      </div>
    </div>
  );
};

export default Help;
