/**
 * 모의투자 페이지 — /paper
 * M1(구조 뼈대) 단계에서는 자리표시자. 실제 가상 계좌·주문·포트폴리오는
 * 후속 마일스톤에서 구현한다(PRD §12 · §14 참조).
 */
export default function PaperTradingPage() {
  return (
    <div className="app">
      <header className="dash-header">
        <span className="dash-header__title">모의투자</span>
      </header>

      <main className="dash-main">
        <section className="coming-soon" aria-label="모의투자 준비 중">
          <div className="coming-soon__icon" aria-hidden="true">
            <svg viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.8" strokeLinecap="round" strokeLinejoin="round">
              <rect x="3" y="4" width="18" height="16" rx="2" />
              <path d="M3 9h18M8 14h4" />
            </svg>
          </div>
          <h2 className="coming-soon__title">모의투자 준비 중</h2>
          <p className="coming-soon__desc">
            가상 자본으로 실시간 시세 기반 매수·매도를 연습하는 화면입니다.
            <br />
            보유 포트폴리오·거래 내역·자산 추이를 곧 제공할 예정입니다.
          </p>
        </section>
      </main>

      <footer className="app-footer">
        ⓘ 모의투자는 수수료·세금·슬리피지를 반영하지 않습니다
      </footer>
    </div>
  );
}
