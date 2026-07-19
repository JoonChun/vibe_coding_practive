## 도화서 화원의 그림 — Phase 2 v2 "확정 판정 vs 실시간 참고 판정" 화면

> 종이 위에 두 개의 붓을 쓴다면, 하나는 먹으로 굵게 — 확정 판정.
> 다른 하나는 옅은 담채로 가늘게 — 실시간 참고. 두 선이 같은 굵기로 겨루면
> 보는 이의 눈이 흔들린다. 이 화면은 그 흔들림을 막기 위해 그린다.

### 0. 읽은 자료

- `web/src/components/StockCard.tsx`, `SignalChip.tsx`, `DecisionGauge.tsx`, `RealtimeBadge.tsx`
- `web/src/pages/StockDetailPage.tsx`, `DashboardPage.tsx`
- `web/src/components/CandleChart.tsx` (tf 바·범례 구조)
- `web/src/index.css` (`--surface*`, `--on-surface*`, `VIEW_COLORS`/`CHIP_STYLES` 팔레트, `.realtime-badge` 펄스, `.gauge-card`, `.signal-chip`, `prefers-reduced-motion` 블록)
- `web/src/types.ts` (`SnapshotItem`에 `live` 필드 아직 없음 — 백엔드 작업 중인 신규 계약)

### 1. 불변 원칙 (이 화면 설계 전체를 관통하는 규칙)

1. **확정 > 참고.** 크기·굵기·채도·상시노출 여부 어느 기준으로도 참고 판정이 확정 판정을 압도해선 안 된다.
2. **번복 연출 금지.** MACD/RSI가 봉 마감 전 흔들려도, 확정 칩·게이지 바늘은 절대 실시간으로 흔들리지 않는다(기존 그대로). 참고 판정도 20초 폴링 주기 안에서만 갱신되므로 그 자체로 이미 완충되어 있다 — 별도 디바운스 로직은 불필요.
3. **모호함보다 침묵.** 워밍업과 오류를 프론트가 구분할 근거 데이터가 없다면, 사용자를 불안하게 하는 단정적 문구("오류", "실패") 대신 중립적 "준비 중"으로 통일한다.
4. **새 색을 만들지 않는다.** 참고 판정 색은 기존 `VIEW_COLORS`/`CHIP_STYLES` 5단계 팔레트를 그대로 재사용하되, 칠(fill) 대신 외곽선(outline)만 써서 "같은 판정 언어, 낮은 확신"을 표현한다.

---

### 2. 상태 판정 규칙 (프론트에서 계산)

`live` 필드는 `/api/snapshot`의 `SnapshotItem.live: { short_view_live, short_score_live, long_view_live, long_score_live, updated_at } | null`로 온다. 이 필드 하나만으로는 "워밍업"과 "조용한 실패"를 구분할 수 없으므로, 이미 화면에 있는 실시간 연결 상태(`tickStream.connected && tickStream.kisConnected` — `RealtimeBadge`가 쓰는 바로 그 값)를 보조 신호로 함께 본다.

| 상태 | 판정 조건 | 의미 |
|---|---|---|
| **fresh (있음)** | `live !== null` 이고 `(지금 − live.updated_at) ≤ 120초` | 정상. 값 그대로 신뢰해 표시 |
| **stale (지연)** | `live !== null` 이고 `(지금 − live.updated_at) > 120초` | 한때 있었으나 갱신이 멈춤. 옛 값을 새 값처럼 보이면 안 되므로 값은 감추고 "지연 중"만 표시 |
| **warming_up (워밍업)** | `live === null` 이고 실시간 연결(`connected && kisConnected`)은 살아있음 | 파이프라인은 정상, 이 종목의 참고 판정만 아직 계산 전(서버 재시작 직후 · 방금 추가한 종목 등) |
| **unavailable (미가용)** | `live === null` 이고 실시간 연결이 끊김 | 원인은 이미 `RealtimeBadge`가 "지연"으로 안내 중 → 참고 판정 쪽은 그냥 침묵(중복 경고 금지) |

> 참고: 2분(120초)이라는 임계치는 스냅샷 폴링 20초의 6주기 분량 — 일시적 폴링 실패 한두 번으로 오判정하지 않을 정도의 여유를 둔 값. 실측 후 조정 가능.
> 향후 백엔드가 `live_status: "ok"|"warming_up"|"error"` 같은 명시적 사유 필드를 내려준다면 warming_up/unavailable을 더 정확히 나눌 수 있음 — 지금은 위 heuristic으로 낙관적 통일.

---

### 3. StockCard — 대시보드 카드

#### 3-1. 기본 상태 (live 없음 / stale / warmup / 확정과 일치 — 모두 "숨김")

```
┌──────────────────────────────────────┐
│ 삼성전자                    [KOSPI] ×│  ← head + 삭제(기존)
│ 005930                                │  ← code(기존)
│                                        │
│ 71,200원                    ▲ +1.24% │  ← price row(기존)
│ ⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇⌇ │  ← Sparkline(기존)
│                                        │
│ [단기: 매수]      [장기: 관망]        │  ← SignalChip 확정(기존, 무변경)
│                                        │  ← live-row 자리(높이만 예약, 내용 없음)
│ KIS                                    │  ← SourceBadge(기존)
└──────────────────────────────────────┘
```

#### 3-2. live 있음(fresh) + 확정과 다를 때만 — 유일하게 카드에 노출되는 케이스

```
│ [단기: 매수]      [장기: 관망]        │  ← 확정(불변, 칠 색·크기 그대로)
│ ○ LIVE 단기: 매도                     │  ← 신규, 외곽선 칩(작게), 단기만 상이
│ KIS                                    │
```

```
│ [단기: 매수]      [장기: 관망]        │
│ ○ LIVE 단기: 매도   LIVE 장기: 매수  │  ← 둘 다 상이하면 두 개 나란히(wrap)
│ KIS                                    │
```

**표시 조건(카드 한정, 아래 중 하나라도 아니면 live-row 미노출):**
- state === `fresh`
- **그리고** `short_view_live !== short_view` 또는 `long_view_live !== long_view` (상이한 쪽만 개별 렌더)

카드는 여러 종목을 훑어보는 목록 뷰이므로, stale/warmup까지 문구로 설명하면 카드마다 잡음이 쌓여 오히려 확정 판정을 덮는다. **카드에서는 "다를 때만, 조용히" 원칙**으로 좁힌다. stale/warmup 설명은 공간이 넉넉한 상세 페이지에서만 한다(3-3 절 아님, 4절 참조).

**live-row 스타일 규칙**
- 컨테이너: `.stock-card__live-row` — `min-height: 1.35rem` 고정(내용 없어도 높이 예약 → 카드 높이가 폴링마다 들썩이지 않게)
- 칩: `SignalChip`에 `variant="live"` prop 추가 → `.signal-chip--live` — 배경 `transparent`, 테두리 1px solid(해당 view의 `CHIP_STYLES.border`), 글자색 동일 컬러, `font-size: 0.65rem`(기존 `.signal-chip`의 0.75rem보다 작게), `padding: 0.15rem 0.45rem`
- 앞에 정적 점 `○`(`.stock-card__live-dot`, 6px, 애니메이션 없음 — 카드에서는 펄스 생략. 여러 카드가 동시에 깜빡이면 화면이 산만해짐)
- 라벨 순서: "LIVE {kind}: {view_live}" (kind = "단기"/"장기")
- `aria-label`: `"${kind} 관점 실시간 참고: ${view_live}로 전환 조짐, 확정 판정은 ${view}"` — 스크린리더가 확정값도 함께 읽도록 명시

---

### 4. StockDetailPage / DecisionGauge — 상세 페이지

**택1 권고: 게이지 밖(SVG·바늘 아래) 별도 스트립.** 바늘을 두 개 그리거나(보조 바늘) 호(arc) 위에 고스트 마커를 찍는 방식은 기각한다.

| 대안 | 기각/채택 사유 |
|---|---|
| A. 보조 바늘 2개 | 반원 게이지(viewBox 100×50)가 좁아 바늘이 겹치면 어느 쪽이 확정인지 즉각 식별 어려움. "두 판정이 경합"하는 것처럼 보여 원칙 1 위반 위험 최대 |
| B. 호 위 고스트 마커(점) | A보다는 가볍지만, 여전히 게이지 자체(사용자 시선이 가장 먼저 꽂히는 지점)에 두 번째 정보가 얹혀 확정의 "단일 결론" 인상이 흐려짐 |
| **C. 게이지 아래 별도 스트립(채택)** | 게이지·바늘은 100% 기존 그대로 — 확정 판정의 시각적 권위 유지. 참고 판정은 작은 텍스트 서브섹션으로 격하되어 "보조 정보"라는 위계가 구조적으로 강제됨. 폴링마다 갱신돼도 게이지 바늘이 다시 애니메이션되지 않으니 안정감 유지 |

#### 4-1. fresh, 확정과 일치

```
┌────────────────────────────┐
│      AI 종합 분석          │  ← gauge-card__title(기존)
│                            │
│        ╱────────╲          │
│       │    ↗     │         │  ← 반원 게이지 + 확정 바늘(기존, 완전 무변경)
│                            │
│          매수              │
│   판정 갱신 · 3분 전        │
│   스코어 +2 (임계 ±2)       │
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │  ← 신규 구분선(.gauge-card__divider)
│ ● LIVE 참고 · 매수 (+1.8)  │  ← 신규 스트립, 확정과 같은 색이지만 outline+소형
│   15초 전 갱신              │
└────────────────────────────┘
```

#### 4-2. fresh, 확정과 다름(전환 조짐)

```
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │
│ ● LIVE 참고 · 매도 (-0.6)  │  ← 값 색상만 다름(여전히 outline, 소형, 차분)
│   확정과 다름 · 8초 전 갱신 │  ← "다름"도 경고색 아님 — 같은 회색 캡션 톤
└────────────────────────────┘
```

#### 4-3. stale(지연)

```
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │
│ ○ LIVE 참고 판정 지연 중    │  ← 값·색 표시 안 함(오래된 값을 새 값처럼 보이지 않게)
│   마지막 갱신 4분 전        │
└────────────────────────────┘
```

#### 4-4. warming_up(준비 중)

```
│ ┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄┄  │
│ ○ LIVE 참고 판정 준비 중…   │  ← 회색, 점 없음/정적, 경고 아님
└────────────────────────────┘
```

#### 4-5. unavailable(미가용)

```
│      스코어 +2 (임계 ±2)   │  ← 구분선·스트립 자체가 없음. 오늘의 gauge-card와 완전히 동일
└────────────────────────────┘
```

**표시 규칙 요약**
- 상세 페이지는 카드와 달리 값이 같아도(4-1) 스트립을 보여준다 — "지금 확정과 같다"는 사실 자체가 안정감을 주는 정보이기 때문(사용자가 능동적으로 들어온 화면이라 정보 밀도를 높여도 됨).
- 현재 선택된 탭(`단기 · 60분봉` / `장기 · 일봉+재무`)에 대응하는 live 필드만 노출한다 — 탭이 "단기"면 `short_view_live`/`short_score_live`, "장기"면 `long_view_live`/`long_score_live`. 다른 쪽 탭의 live 값은 보여주지 않는다(탭 전환 시 자연히 교체 — 기존 `otherView` peek 버튼과 같은 패턴 재사용).
- 컬러: `view_live`가 확정과 같든 다르든 `VIEW_COLORS`를 텍스트/외곽선에만 적용, 배경은 항상 transparent. 채도·굵기 모두 확정 라벨(`.gauge-card__label`, 24px/700)보다 명백히 낮게(11~12px, 500).
- "확정과 다름" 캡션은 별도 색(경고색·빨강 등) 없이 스트립 내 다른 캡션과 같은 회색(`--on-surface-variant`) 톤 — 전환 조짐을 "알리되 겁주지 않는다".

**스타일 규칙**
- 신규 컴포넌트 제안: `LiveReferenceStrip.tsx` — `variant: "compact" | "full"` prop으로 StockCard(compact, 3절)와 상세 페이지(full, 본 절) 양쪽에서 재사용. 4-state 판정 로직을 한 곳에 캡슐화해 두 화면이 서로 다르게 구현되는 것을 방지(일관성 보장).
- 클래스: `.live-strip`, `.live-strip--full`, `.live-strip--compact`, `.live-strip__dot`(6px, `background: #f59e0b`), `.live-strip__value`, `.live-strip__caption`(`.gauge-card__caption`과 동일 톤 재사용)
- 펄스 애니메이션: fresh 상태에서만 점이 깜빡임(`@keyframes pulse-dot-amber`, 기존 `pulse-dot`과 동일 곡선이나 색만 앰버) — stale/warmup은 정적 점(`○`), `prefers-reduced-motion: reduce` 블록에 신규 keyframe도 추가해 정지시킬 것(기존 `.realtime-badge__dot` 처리와 동일 패턴).
- 구분선: `.gauge-card__divider` — `border-top: 1px solid var(--outline-variant); margin-top: 0.5rem; padding-top: 0.5rem; width: 100%`

---

### 5. CandleChart — "마지막 봉은 미마감" 표시

진행중 봉 자체의 실시간 갱신(2초 WS `bar_update`)은 차트가 알아서 하므로 그림을 새로 그릴 필요는 없다. 다만 **"지금 보이는 마지막 봉이 아직 마감되지 않은 잠정치"**라는 사실 하나는 툴바에 짧게 알린다.

```
┌ candle-chart__toolbar ─────────────────────────────┐
│ ● MA5  ● MA20  ● MA60  ● MA120        ○ LIVE   KIS │
└─────────────────────────────────────────────────────┘
  ↑ 기존 범례(무변경)                     ↑신규   ↑기존 SourceBadge
```

- 노출 조건(가정): `isMinuteTf(tf)`(1~240분봉일 때만) **그리고** 실시간 연결(`connected && kisConnected`)이 살아있을 때. 일/주/월/년봉은 봉 마감 개념이 하루 단위라 이번 1차 범위에서는 제외 권고 — 만약 백엔드가 일봉의 "오늘" 봉도 실시간 갱신한다면 이 조건에서 `isMinuteTf` 체크만 제거하면 됨(장영실 확인 필요 지점으로 표시해둠).
- 표시: 작은 앰버 점(펄스, `.live-strip__dot`과 동일 스타일 재사용) + "LIVE" 텍스트. 클릭 불가(정보성), `title`/`aria-label`: "마지막 봉은 미마감 상태로 실시간 갱신됩니다"
- `role`/`aria-live` 없음 — 2초마다 값이 바뀌는 게 아니라 "연결 여부"라는 이진 상태만 바뀌므로 상시 알림 불필요.
- 캔들 자체에 점선 테두리 등으로 마지막 봉을 강조하는 방식은 lightweight-charts 오버레이 작업이 필요해 구현 난이도 대비 효용이 낮음 — 1차 범위 제외, 툴바 표시로 충분하다고 판단.

---

### 6. 라벨 용어집 (문구 확정)

| 상황 | 문구 | 사용처 |
|---|---|---|
| 확정 판정 | (라벨 없음 — 기존 칩/게이지 그대로 유지) | StockCard 칩, DecisionGauge |
| 참고 판정, fresh | `LIVE 참고 · {view} ({score:+}) · {relativeTime}` | 상세 스트립(full) |
| 참고 판정, fresh + 카드 | `LIVE {단기\|장기}: {view_live}` | StockCard live-row(compact) |
| 확정과 다름 부기 | `확정과 다름` | 상세 스트립 캡션(회색, 경고색 아님) |
| stale | `LIVE 참고 판정 지연 중` + `마지막 갱신 {relativeTime}` | 상세 스트립만 |
| warming_up | `LIVE 참고 판정 준비 중…` | 상세 스트립만 |
| unavailable | (미노출 — RealtimeBadge "지연"이 이미 안내) | — |
| 차트 진행봉 | `LIVE` + 툴팁 "마지막 봉은 미마감 상태로 실시간 갱신됩니다" | CandleChart 툴바 |

톤: 어디에도 느낌표·굵은 경고색·"위험/에러/실패" 단어 사용 금지. "판정은 참고 정보이며 투자 권유가 아님"은 기존 푸터 고지문이 이미 전 페이지 커버 중 — 반복 불필요.

---

### 7. 컴포넌트별 변경 지점 표

| 파일 | 위치 | 추가 요소 | 스타일 규칙 |
|---|---|---|---|
| `web/src/types.ts` | `SnapshotItem` 옆 | `live: { short_view_live, short_score_live, long_view_live, long_score_live, updated_at } \| null` 타입 추가(백엔드 계약대로) | 없음(타입 전용) |
| `web/src/components/SignalChip.tsx` | prop 확장 | `variant?: "confirmed" \| "live"`(기본 confirmed) | live일 때 `.signal-chip--live` — 배경 transparent, 테두리/글자 `CHIP_STYLES[view].border`, `font-size: 0.65rem`, `padding: 0.15rem 0.45rem` |
| `web/src/components/LiveReferenceStrip.tsx` (신규) | — | 4-state(fresh/stale/warming_up/unavailable) 판정 + 렌더 로직 캡슐화. `variant: "compact" \| "full"` | `.live-strip`, `.live-strip--compact`, `.live-strip--full`, `.live-strip__dot`, `.live-strip__value`, `.live-strip__caption` |
| `web/src/components/StockCard.tsx` | `.stock-card__chips` 바로 아래, `SourceBadge` 위 | `<LiveReferenceStrip variant="compact" .../>` — 확정과 상이한 쪽만 표시, 높이 예약 컨테이너 | `.stock-card__live-row { min-height: 1.35rem }` |
| `web/src/pages/DashboardPage.tsx` | `StockCardData` 매핑(`rows` useMemo) | `live: snap?.live ?? null` 필드 매핑 추가 | 없음 |
| `web/src/pages/StockDetailPage.tsx` | `DecisionGauge` 아래, `detail-grid__gauge` 셀 내부 | `<LiveReferenceStrip variant="full" .../>` — 현재 탭(`short`/`long`)에 대응하는 live 필드만 전달 | `.gauge-card__divider`(구분선) |
| `web/src/components/CandleChart.tsx` | `.candle-chart__toolbar` 우측, `SourceBadge` 옆 | `wsConnected` prop 신규 추가(부모가 `tickStream.connected && tickStream.kisConnected` 전달) → 조건부 LIVE 태그 | `.candle-chart__live-tag`(펄스 점 + "LIVE" 텍스트, `.live-strip__dot` 스타일 재사용) |
| `web/src/index.css` | 기존 `.signal-chip`, `.gauge-card`, `.realtime-badge` 블록 근처 | 위 신규 클래스 전부 + `@keyframes pulse-dot-amber` | `prefers-reduced-motion: reduce` 블록에 `.live-strip__dot`, `.candle-chart__live-tag` 도 `animation: none` 추가 |

---

### 8. 상태 매트릭스 (한눈에 보기)

| 상태 | StockCard | DecisionGauge 스트립 | CandleChart LIVE 태그 |
|---|---|---|---|
| **fresh, 확정과 일치** | 미노출 | 노출 — `LIVE 참고 · {view} ({score:+}) · {relativeTime}` | 노출(연결 살아있으면) |
| **fresh, 확정과 다름** | 노출 — `LIVE {kind}: {view_live}`(상이한 쪽만) | 노출 — 값 + `확정과 다름`(회색) | 노출 |
| **stale** | 미노출 | 노출 — `LIVE 참고 판정 지연 중` + 마지막 갱신 시각(값 자체는 숨김) | 연결 여부로만 판단(무관) |
| **warming_up** | 미노출 | 노출 — `LIVE 참고 판정 준비 중…` | 연결 살아있으면 노출(bar_update와는 별개 신호) |
| **unavailable** | 미노출 | 미노출(구분선도 없음, 기존 gauge-card와 동일) | 미노출(연결 끊김 → RealtimeBadge가 이미 "지연" 안내) |

---

### 9. 사용자 흐름

```
[대시보드] 스냅샷 폴링(20s) 도착
   → 각 카드: live 상태 계산(fresh/stale/warmup/unavailable)
      → fresh & 확정과 다름? → live-row 노출(눈에 띄되 작게)
      → 그 외 → live-row 없음, 카드 외관 기존과 동일
   → 사용자, LIVE 표기 발견 → 카드 클릭
[상세 페이지] 진입
   → 게이지는 확정 그대로(기존 로딩·전환)
   → 게이지 아래 LiveReferenceStrip(full) 렌더 — 탭(단기/장기)에 맞는 live 값
   → 20초 후 폴링 재도착 → 스트립 값만 자연스럽게 갱신(게이지 바늘은 무관하게 정지)
   → 차트 영역: 분봉 탭 & 연결 정상 → 툴바 LIVE 점멸 태그로 "이 마지막 봉은 잠정치"임을 인지
```

---

### 10. 디자인 사유

- **왜 카드에서는 "다를 때만"인가**: 목록 뷰는 여러 종목을 빠르게 훑는 용도. 매 카드마다 참고 정보를 상시 노출하면 확정 판정과 시각적 경합이 생기고 스캔 속도가 떨어진다. 실질적으로 사용자에게 "새로운 정보"인 순간(확정과 어긋난 순간)에만 눈에 띄게 하는 것이 신호 대 잡음비를 지킨다.
- **왜 상세에서는 "같아도" 보여주는가**: 사용자가 이미 종목 하나에 집중하기로 결정한 화면이라 정보 밀도를 높여도 부담이 적고, "지금 확정과 같다"는 사실 자체가 "아직 안정적"이라는 안심 신호로 작동한다.
- **왜 게이지에 바늘을 더하지 않는가**: 반원 게이지는 이 앱에서 "가장 신뢰받는 단일 결론"을 상징하는 자리다. 두 번째 바늘이나 마커를 얹으면 그 자리의 권위가 분산된다. 참고 판정은 게이지 밖, 구분선 아래 텍스트로 격을 낮춰 배치한다.
- **왜 outline이고 채색 배경이 아닌가**: 배경을 채우면 크기가 작아도 눈에 먼저 들어온다(면 > 선). 외곽선+텍스트만 쓰면 같은 색 언어를 유지하면서도 "확신이 낮다"는 인상을 구조적으로 전달한다.
- **왜 "확정과 다름"도 회색인가**: 전환 조짐은 유용한 정보이지만, 경고색을 쓰는 순간 사용자는 그것을 확정 신호처럼 받아들여 성급히 반응할 수 있다. 이 앱의 목적은 "흔들지 않는 것"이므로 색으로 긴장감을 주지 않는다.
- **왜 워밍업/오류를 하나로 묶는가**: 현재 데이터 계약(`live: {...} | null`)만으로는 둘을 구분할 근거가 없다. 근거 없이 "오류"라 단정하면 실제로는 정상인 상황에서 사용자를 불안하게 만들 수 있다 — 모를 땐 더 겁주는 쪽이 아니라 더 차분한 쪽으로 낙관한다.

---

### 11. 접근성·반응형

- **스크린리더**: `LiveReferenceStrip`/카드 live-row는 `role="status"`를 쓰지 않는다 — 20초마다 갱신되는데 `role="status"`(암묵적 `aria-live="polite"`)를 걸면 값이 그대로여도 주기적으로 낭독되어 피로를 유발한다. 대신 정적 `aria-label`만 최신값으로 갱신하고, 사용자가 탐색 시 자연스럽게 읽히도록 DOM 순서를 "확정 라벨 → live 스트립" 순으로 유지한다. `RealtimeBadge`(연결 자체의 드문 상태 변화)는 기존처럼 `role="status"` 유지 — 이번 변경과 무관.
- **키보드 네비**: 신규 요소는 모두 순수 정보 표시(비대화형)이므로 별도 tab-stop을 만들지 않는다. 클릭/포커스 가능한 요소를 추가하지 않는다.
- **모션 최소화**: `prefers-reduced-motion: reduce` 블록에 `.live-strip__dot`, `.candle-chart__live-tag`의 `animation: none`을 추가(기존 `.realtime-badge__dot` 처리와 동일 패턴). 카드 live-row의 점(`○`)은 애초에 정적이라 영향 없음.
- **모바일(≤640px)**: `stock-card__live-row`는 `flex-wrap`으로 두 칩(단기+장기 모두 상이한 경우)이 필요 시 2줄로 자연스럽게 접히게 한다. 상세 페이지 `detail-grid`는 기존처럼 1열로 쌓이며, `LiveReferenceStrip(full)`은 `gauge-card` 폭에 맞춰 줄바꿈(`word-wrap`)만 되면 충분 — 별도 반응형 규칙 불필요.
- **레이아웃 흔들림 방지**: 카드 live-row는 내용이 없어도 `min-height`를 예약해, 폴링마다 상태가 바뀌어도(노출↔미노출) 카드 그리드 높이가 들썩이지 않게 한다.

---

### 다음 차례

이 설계는 백엔드 `live` 필드가 아직 구현 중인 상태를 전제로 한 선행 UI 설계입니다. `frontend-dancheong`께 이 문서를 그대로 넘겨 구현을 청하시되, 아래 두 지점은 시공 전 정도전 대감·backend-gigwan과 짧게 확인 권고드립니다.
1. CandleChart LIVE 태그의 `isMinuteTf` 한정 가정(일봉도 실시간 반영되는지 여부).
2. `live` stale 임계치 120초가 실제 폴링·계산 주기에 비춰 적절한지(백엔드 계산 지연 특성 확인 후 조정 가능).
