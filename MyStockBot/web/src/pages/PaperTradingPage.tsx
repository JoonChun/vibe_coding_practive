import { useCallback, useEffect, useState } from "react";
import {
  ApiError,
  getPaperAccount,
  getPaperTrades,
  placePaperOrder,
  resetPaperAccount,
} from "../api";
import { TokenBanner } from "../components/TokenBanner";
import type { PaperAccount, PaperHolding, PaperTrade } from "../types";

const won = (n: number | null | undefined) =>
  n === null || n === undefined ? "—" : `${Math.round(n).toLocaleString("ko-KR")}원`;

function pnlClass(n: number | null | undefined): string {
  if (n === null || n === undefined || n === 0) return "index-card__chg--flat";
  return n > 0 ? "index-card__chg--up" : "index-card__chg--down";
}

function signed(n: number | null | undefined): string {
  if (n === null || n === undefined) return "—";
  return `${n > 0 ? "+" : ""}${Math.round(n).toLocaleString("ko-KR")}`;
}

/**
 * 모의투자 페이지 — /paper
 * 가상 계좌(현금·평가손익), 매수/매도(현재가 즉시 체결), 보유 종목, 거래 내역.
 * 체결가는 관심종목 스냅샷의 현재가를 사용 → 시세가 수집된 종목만 거래 가능.
 */
export default function PaperTradingPage() {
  const [account, setAccount] = useState<PaperAccount | null>(null);
  const [trades, setTrades] = useState<PaperTrade[]>([]);
  const [unauthorized, setUnauthorized] = useState(false);
  const [loadError, setLoadError] = useState<string | null>(null);

  const [code, setCode] = useState("");
  const [qty, setQty] = useState("1");
  const [orderError, setOrderError] = useState<string | null>(null);
  const [pending, setPending] = useState(false);

  const loadAll = useCallback(async () => {
    try {
      const [acct, tr] = await Promise.all([getPaperAccount(), getPaperTrades()]);
      setAccount(acct);
      setTrades(tr.items);
      setUnauthorized(false);
      setLoadError(null);
    } catch (e) {
      if (e instanceof ApiError && e.status === 401) {
        setUnauthorized(true);
      } else {
        setLoadError(
          e instanceof ApiError ? e.message : "계좌 정보를 불러오지 못했습니다."
        );
      }
    }
  }, []);

  useEffect(() => {
    void loadAll();
  }, [loadAll]);

  async function submitOrder(side: "buy" | "sell") {
    setOrderError(null);
    const q = Number(qty);
    if (!code.trim()) {
      setOrderError("종목코드를 입력해주세요.");
      return;
    }
    if (!Number.isInteger(q) || q <= 0) {
      setOrderError("수량은 1 이상의 정수여야 합니다.");
      return;
    }
    setPending(true);
    try {
      const acct = await placePaperOrder({ code: code.trim(), side, qty: q });
      setAccount(acct);
      const tr = await getPaperTrades();
      setTrades(tr.items);
    } catch (e) {
      setOrderError(
        e instanceof ApiError ? e.message : "주문 처리에 실패했습니다."
      );
    } finally {
      setPending(false);
    }
  }

  async function handleReset() {
    if (!window.confirm("가상 계좌를 초기화할까요? 보유·거래내역이 모두 삭제됩니다.")) {
      return;
    }
    try {
      const acct = await resetPaperAccount();
      setAccount(acct);
      setTrades([]);
      setOrderError(null);
    } catch (e) {
      setOrderError(e instanceof ApiError ? e.message : "초기화에 실패했습니다.");
    }
  }

  if (unauthorized) {
    return (
      <div className="app">
        <TokenBanner onSaved={() => void loadAll()} />
        <header className="dash-header">
          <h1 className="dash-header__title">모의투자</h1>
        </header>
      </div>
    );
  }

  return (
    <div className="app">
      <header className="dash-header">
        <span className="dash-header__title">모의투자</span>
        <button type="button" className="paper-reset" onClick={() => void handleReset()}>
          초기화
        </button>
      </header>

      <main className="dash-main">
        {/* 다른 화면(대시보드·관심종목)은 폴링이 스스로 복구하지만 이 화면은 마운트
            시 1회만 불러오므로, 실패하면 사용자가 직접 재시도할 수단이 필요하다. */}
        {loadError ? (
          <p className="panel__error" role="alert">
            {loadError}
            <button
              type="button"
              className="banner__retry"
              onClick={() => void loadAll()}
            >
              다시 시도
            </button>
          </p>
        ) : null}

        {/* 계좌 요약 */}
        <section className="paper-hero" aria-label="가상 계좌 요약">
          <span className="paper-hero__label">총 평가자산</span>
          <span className="paper-hero__total">{won(account?.total_value)}</span>
          <span className={`paper-hero__pnl ${pnlClass(account?.total_pnl)}`}>
            {account
              ? `평가손익 ${signed(account.total_pnl)}원 (${account.total_pnl_pct > 0 ? "+" : ""}${account.total_pnl_pct.toFixed(2)}%)`
              : "—"}
          </span>
          <div className="paper-hero__split">
            <div>
              <span className="paper-hero__k">현금 잔액</span>
              <span className="paper-hero__v">{won(account?.cash)}</span>
            </div>
            <div>
              <span className="paper-hero__k">주식 평가금액</span>
              <span className="paper-hero__v">{won(account?.holdings_value)}</span>
            </div>
          </div>
          {/*
            총손익을 실현/미실현으로 쪼개 보여준다. 합계만 보면 "이미 확정된 손익"과
            "아직 팔지 않아 변할 수 있는 손익"이 뭉개진다 — 성적 해석에서 전혀 다른 값이다.
          */}
          <div className="paper-hero__split">
            <div>
              <span className="paper-hero__k">실현손익</span>
              <span className={`paper-hero__v ${pnlClass(account?.realized_pnl)}`}>
                {account ? `${signed(account.realized_pnl)}원` : "—"}
              </span>
            </div>
            <div>
              <span className="paper-hero__k">미실현손익</span>
              <span className={`paper-hero__v ${pnlClass(account?.unrealized_pnl)}`}>
                {account ? `${signed(account.unrealized_pnl)}원` : "—"}
              </span>
            </div>
          </div>
          {account && account.realized_unknown_trades > 0 ? (
            <p className="paper-hero__note">
              ⓘ 실현손익 기록 이전의 매도 {account.realized_unknown_trades}건이 있어
              실현·미실현 합이 총손익과 다를 수 있습니다.
            </p>
          ) : null}
        </section>

        {/* 주문 */}
        <section className="paper-order" aria-label="매수/매도 주문">
          <div className="paper-order__fields">
            <label className="paper-order__field">
              <span>종목코드</span>
              <input
                inputMode="numeric"
                placeholder="예: 005930"
                value={code}
                onChange={(e) => setCode(e.target.value)}
              />
            </label>
            <label className="paper-order__field paper-order__field--qty">
              <span>수량</span>
              <input
                inputMode="numeric"
                value={qty}
                onChange={(e) => setQty(e.target.value)}
              />
            </label>
          </div>
          <div className="paper-order__actions">
            <button
              type="button"
              className="paper-btn paper-btn--buy"
              disabled={pending}
              onClick={() => void submitOrder("buy")}
            >
              매수
            </button>
            <button
              type="button"
              className="paper-btn paper-btn--sell"
              disabled={pending}
              onClick={() => void submitOrder("sell")}
            >
              매도
            </button>
          </div>
          {orderError ? (
            <p className="panel__error" role="alert">
              {orderError}
            </p>
          ) : null}
          <p className="paper-order__hint">
            관심종목에 등록되어 시세가 수집된 종목만 현재가로 즉시 체결됩니다.
          </p>
        </section>

        {/* 보유 종목 */}
        <section aria-label="보유 종목">
          <h2 className="movers__title">보유 종목</h2>
          {account && account.holdings.length > 0 ? (
            <ul className="paper-holdings">
              {account.holdings.map((h: PaperHolding) => (
                <li key={h.code}>
                  <button
                    type="button"
                    className="paper-holding"
                    onClick={() => setCode(h.code)}
                    title="클릭 시 주문 종목코드로 채우기"
                  >
                    <span className="paper-holding__info">
                      <span className="paper-holding__name">{h.name}</span>
                      <span className="paper-holding__meta">
                        {h.qty}주 · 평단 {won(h.avg_cost)} → 현재 {won(h.price)}
                      </span>
                    </span>
                    <span className="paper-holding__right">
                      <span className="paper-holding__eval">{won(h.eval_amount)}</span>
                      <span className={`paper-holding__pnl ${pnlClass(h.pnl)}`}>
                        {h.pnl === null
                          ? "시세 없음"
                          : `${signed(h.pnl)}원 · ${(h.pnl_pct ?? 0) > 0 ? "+" : ""}${(h.pnl_pct ?? 0).toFixed(2)}%`}
                      </span>
                    </span>
                  </button>
                </li>
              ))}
            </ul>
          ) : (
            <p className="movers__empty">보유 종목이 없습니다.</p>
          )}
        </section>

        {/* 거래 내역 */}
        <section aria-label="거래 내역">
          <h2 className="movers__title">거래 내역</h2>
          {trades.length > 0 ? (
            <ul className="paper-trades">
              {trades.map((t) => (
                <li key={t.id} className="paper-trade">
                  <span
                    className={`paper-trade__side paper-trade__side--${t.side}`}
                  >
                    {t.side === "buy" ? "매수" : "매도"}
                  </span>
                  <span className="paper-trade__info">
                    <span className="paper-trade__name">
                      {t.name}
                      {/*
                        장부가 대체 체결은 시장가 체결과 반드시 구별해 보여준다 —
                        시세가 없어 평균단가로 청산한 것이므로 "그 값에 팔렸다"가 아니다.
                      */}
                      {t.price_source === "book" ? (
                        <span
                          className="paper-trade__flag"
                          title="현재 시세가 없어 장부가(평균단가)로 체결했습니다. 실제 시장가 체결이 아닙니다."
                        >
                          장부가
                        </span>
                      ) : null}
                      {t.market_status && t.market_status !== "open" ? (
                        <span
                          className="paper-trade__flag"
                          title="장 시간 외 체결입니다. 실제 시장에서는 불가능합니다."
                        >
                          장외
                        </span>
                      ) : null}
                    </span>
                    <span className="paper-trade__ts">{t.ts}</span>
                  </span>
                  <span className="paper-trade__qty">
                    {t.qty}주 @ {won(t.price)}
                    {t.realized_pnl !== null ? (
                      <span className={`paper-trade__pnl ${pnlClass(t.realized_pnl)}`}>
                        {signed(t.realized_pnl)}원
                      </span>
                    ) : null}
                  </span>
                </li>
              ))}
            </ul>
          ) : (
            <p className="movers__empty">거래 내역이 없습니다.</p>
          )}
        </section>
      </main>

      <footer className="app-footer">
        ⓘ 모의투자는 수수료·세금·슬리피지를 반영하지 않습니다 · 투자 권유 아님
      </footer>
    </div>
  );
}
