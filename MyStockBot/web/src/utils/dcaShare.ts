import type { DcaResponse } from "../types";

/**
 * 적립식 백테스트 공유 카드(§15.2c) — 쇼츠·릴스 세로 포맷 렌더러.
 *
 * ## 왜 캔버스 하나인가
 * "화면 미리보기"와 "저장되는 이미지"를 각각 HTML/캔버스로 만들면 둘이 갈라진다
 * (미리보기엔 있는 면책이 저장한 이미지엔 없는 식으로). 그래서 **미리보기가 곧
 * 산출물**이다 — 화면에 붙는 그 캔버스를 그대로 PNG 로 내보낸다.
 *
 * 대가는 캔버스가 스크린리더에 안 보인다는 것. `buildShareModel().altText` 로
 * 대체 텍스트를 함께 만들어 `aria-label` 에 싣는다(스모크 검증도 이 경로로 한다 —
 * 캔버스 안의 글자는 DOM 으로 읽을 수 없다).
 *
 * ## 팔레트를 왜 고정하나
 * 앱은 라이트/다크를 따라가지만 카드는 **어디에 올려도 같아야 하는 브랜드 산출물**
 * 이라 고정 다크로 그린다. 상승/하락 색은 앱과 같은 값(#b91c1c / #1d4ed8 — 국내
 * 관행)을 쓴다.
 */

/** 1080×1920 = 9:16. 릴스·쇼츠·스토리가 공통으로 받는 해상도. */
export const CARD_W = 1080;
export const CARD_H = 1920;

const FONT_STACK =
  '"Inter", -apple-system, BlinkMacSystemFont, "Segoe UI", "Malgun Gothic", ' +
  '"Apple SD Gothic Neo", Roboto, Helvetica, Arial, sans-serif';

const C = {
  bg0: "#050a14",
  bg1: "#131c2f",
  panel: "rgba(255, 255, 255, 0.05)",
  text: "#f4f6fb",
  dim: "#8590a6",
  up: "#f0533f",
  down: "#5b8cff",
  cta: "#f4f6fb",
  ctaText: "#091426",
} as const;

// 카드 배경이 어두워서 앱의 #b91c1c/#1d4ed8 은 대비가 모자란다. 같은 계열에서
// 다크 배경용으로 밝힌 값(위 C.up/C.down)을 쓴다 — 색의 **의미**는 앱과 같다.

export interface ShareStat {
  k: string;
  v: string;
}

export interface ShareModel {
  title: string;
  subtitle: string;
  headline: string;
  up: boolean;
  heroLabel: string;
  stats: ShareStat[];
  meta: string;
  caveats: string[];
  altText: string;
  curve: DcaResponse["curve"];
  /** 저장 파일명(확장자 포함). */
  fileName: string;
}

const FREQ_WORD: Record<string, string> = {
  weekly: "매주",
  monthly: "매월",
  quarterly: "매분기",
};

/** 큰 금액 축약(억/만) — 카드 셀 넘침 방지. 화면 카드(DcaCard)와 공유 카드가
 *  **같은 함수**를 쓴다: 같은 수치가 두 곳에서 다르게 보이면 어느 쪽을 믿을지 알 수 없다. */
export function wonCompact(n: number): string {
  const a = Math.abs(Math.round(n));
  const s = n < 0 ? "-" : "";
  if (a >= 1e8) {
    return `${s}${a / 1e8 >= 10 ? (a / 1e8).toFixed(1) : (a / 1e8).toFixed(2)}억`;
  }
  if (a >= 1e4) return `${s}${Math.round(a / 1e4).toLocaleString("ko-KR")}만`;
  return `${s}${a.toLocaleString("ko-KR")}`;
}

const BRAND = "MyStockBot";
const TAGLINE = "판정하고, 증명한다";
const CTA = "내 종목으로 해보기";
const DISCLAIMER = "과거 성과는 미래를 보장하지 않습니다 · 투자 권유 아님";

/**
 * 응답 + 종목명 → 카드에 그릴 것 전부.
 *
 * `caveats` 는 응답의 `notes` 를 그대로 쓴다. 카드 문구를 여기서 새로 쓰지 않는
 * 이유: 어떤 가정이 깨졌는지(분기 근사·기간 잘림·배당 미반영)는 계산한 백엔드만
 * 안다. 프런트에 하드코딩하면 계산과 문구가 갈라진다.
 */
export function buildShareModel(d: DcaResponse, name: string): ShareModel {
  const up = d.return_pct >= 0;
  const headline = `${up ? "+" : ""}${d.return_pct.toFixed(1)}%`;
  const word = FREQ_WORD[d.freq] ?? d.freq;
  const perLabel =
    d.mode === "qty"
      ? `${d.per.toLocaleString("ko-KR")}주씩`
      : `${wonCompact(d.per)}원씩`;
  const period =
    d.start_date && d.end_date ? `${d.start_date} ~ ${d.end_date}` : "";

  const stats: ShareStat[] = [
    { k: "투자 원금", v: `${wonCompact(d.principal)}원` },
    { k: "평가금액", v: `${wonCompact(d.eval_value)}원` },
    { k: "수익", v: `${d.profit >= 0 ? "+" : ""}${wonCompact(d.profit)}원` },
  ];

  const avg = d.avg_price === null ? "—" : `${Math.round(d.avg_price).toLocaleString("ko-KR")}원`;
  const meta = `${word} ${perLabel} · ${d.buys}회 매수 · 평균단가 ${avg}`;

  const altText =
    `${name} 적립식 카드. ${period} 동안 ${word} ${perLabel} 매수 시 ` +
    `누적 수익률 ${headline}. 투자 원금 ${wonCompact(d.principal)}원, ` +
    `평가금액 ${wonCompact(d.eval_value)}원, 수익 ${wonCompact(d.profit)}원. ` +
    `${d.buys}회 매수, 평균단가 ${avg}. ${d.notes.join(". ")}. ${DISCLAIMER}`;

  return {
    title: name,
    subtitle: period ? `${word} ${perLabel} · ${period}` : `${word} ${perLabel}`,
    headline,
    up,
    heroLabel: "누적 수익률",
    stats,
    meta,
    caveats: d.notes,
    altText,
    curve: d.curve,
    // ★ ASCII 만 쓴다. 파일명에 한글이 섞이면 Chromium 이 `download` 속성을
    //   **통째로 무시**하고 확장자 없는 "download" 로 저장한다(실측: 같은 코드에서
    //   "plain.png" 는 그대로, "한글-파일.png" 는 "download" — http 오리진에서도 동일).
    //   확장자가 없으면 휴대폰 갤러리가 이미지로 인식하지 못한다.
    fileName: `mystockbot-dca-${d.code}-${(d.start_date ?? "").replace(/[^\w-]/g, "")}.png`,
  };
}

/** maxWidth 안에 들어가도록 줄바꿈. 한글은 단어 경계가 드물어 글자 단위로도 쪼갠다. */
function wrap(
  ctx: CanvasRenderingContext2D,
  text: string,
  maxWidth: number
): string[] {
  const lines: string[] = [];
  let line = "";
  for (const ch of text) {
    const next = line + ch;
    if (ctx.measureText(next).width > maxWidth && line) {
      lines.push(line);
      line = ch === " " ? "" : ch;
    } else {
      line = next;
    }
  }
  if (line) lines.push(line);
  return lines;
}

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number
): void {
  ctx.beginPath();
  ctx.moveTo(x + r, y);
  ctx.arcTo(x + w, y, x + w, y + h, r);
  ctx.arcTo(x + w, y + h, x, y + h, r);
  ctx.arcTo(x, y + h, x, y, r);
  ctx.arcTo(x, y, x + w, y, r);
  ctx.closePath();
}

function font(weight: number, size: number): string {
  return `${weight} ${size}px ${FONT_STACK}`;
}

/** 평가금액(면적) vs 누적 원금(점선). 축은 없다 — 카드는 형태만 전달한다. */
function drawCurve(
  ctx: CanvasRenderingContext2D,
  curve: DcaResponse["curve"],
  x: number,
  y: number,
  w: number,
  h: number,
  up: boolean
): void {
  if (curve.length < 2) return;
  const max = Math.max(...curve.map((p) => Math.max(p.value, p.principal)), 1);
  const px = (i: number) => x + (i / (curve.length - 1)) * w;
  const py = (v: number) => y + h - (v / max) * h;

  const grad = ctx.createLinearGradient(0, y, 0, y + h);
  const tint = up ? C.up : C.down;
  grad.addColorStop(0, `${tint}66`);
  grad.addColorStop(1, `${tint}05`);

  ctx.beginPath();
  ctx.moveTo(x, y + h);
  curve.forEach((p, i) => ctx.lineTo(px(i), py(p.value)));
  ctx.lineTo(x + w, y + h);
  ctx.closePath();
  ctx.fillStyle = grad;
  ctx.fill();

  ctx.beginPath();
  curve.forEach((p, i) => (i ? ctx.lineTo(px(i), py(p.value)) : ctx.moveTo(px(i), py(p.value))));
  ctx.strokeStyle = tint;
  ctx.lineWidth = 6;
  ctx.lineJoin = "round";
  ctx.stroke();

  ctx.save();
  ctx.setLineDash([12, 10]);
  ctx.beginPath();
  curve.forEach((p, i) =>
    i ? ctx.lineTo(px(i), py(p.principal)) : ctx.moveTo(px(i), py(p.principal))
  );
  ctx.strokeStyle = C.dim;
  ctx.lineWidth = 4;
  ctx.stroke();
  ctx.restore();
}

export interface DrawResult {
  /** 가정·한계 문구가 CTA/면책 블록을 침범하지 않고 다 들어갔는가. */
  fits: boolean;
  /** 본문이 끝난 y 와 침범 금지선 — fits=false 일 때 얼마나 넘쳤는지 알 수 있다. */
  contentBottom: number;
  limit: number;
}

/**
 * 모델을 캔버스에 그린다. 캔버스의 width/height 를 CARD_W/CARD_H 로 맞춰 호출한다.
 *
 * 웹폰트가 로드되기 전에 그리면 폴백 폰트로 픽셀이 굳는다(다시 그리지 않으면 그게
 * 저장된다). 호출부가 `document.fonts.ready` 를 기다린 뒤 호출한다.
 *
 * ## 아래쪽 블록(CTA·면책)은 고정, 가정·한계는 남는 공간에 맞춰 줄인다
 * caveat 개수는 조건에 따라 변한다(분기 근사·기간 잘림·배당 재투자 요청 → 최대 7줄).
 * 위에서부터 흘려보내면 마지막 줄이 CTA 알약에 잘린다 — 실제로 그렇게 잘렸고,
 * DOM·픽셀 검사로는 잡히지 않아 렌더한 이미지를 눈으로 봐서 발견했다. 그래서
 * **면책·CTA 가 쓸 영역을 먼저 떼어두고**, caveat 는 남은 밴드에 들어가는 크기로
 * 줄여 그린다. 그래도 안 들어가면 `fits: false` 로 알린다(조용히 잘리지 않는다).
 */
export function drawShareCard(canvas: HTMLCanvasElement, m: ShareModel): DrawResult {
  canvas.width = CARD_W;
  canvas.height = CARD_H;
  const ctx = canvas.getContext("2d");
  if (!ctx) return { fits: false, contentBottom: 0, limit: 0 };

  const PAD = 88;
  const inner = CARD_W - PAD * 2;

  const bg = ctx.createLinearGradient(0, 0, CARD_W, CARD_H);
  bg.addColorStop(0, C.bg1);
  bg.addColorStop(1, C.bg0);
  ctx.fillStyle = bg;
  ctx.fillRect(0, 0, CARD_W, CARD_H);

  ctx.textBaseline = "alphabetic";
  ctx.textAlign = "left";

  // ── 아래쪽 고정 블록의 자리를 먼저 확정한다(본문이 여기까지 내려오면 안 된다) ──
  const discY = CARD_H - PAD - 12;
  const ctaH = 108;
  const ctaW = 560;
  const ctaY = discY - 56 - ctaH;
  const CAVEAT_GAP = 40; // CTA 알약과 작은 글씨 사이 최소 여백
  const limit = ctaY - CAVEAT_GAP;

  // ── 브랜드 ──
  let y = PAD + 56;
  ctx.font = font(700, 44);
  ctx.fillStyle = C.text;
  ctx.fillText(BRAND, PAD, y);
  ctx.font = font(400, 32);
  ctx.fillStyle = C.dim;
  ctx.fillText(TAGLINE, PAD + ctx.measureText(BRAND).width + 130, y);

  // ── 종목·조건 ──
  y += 116;
  ctx.font = font(700, 84);
  ctx.fillStyle = C.text;
  ctx.fillText(m.title, PAD, y);
  y += 58;
  ctx.font = font(400, 38);
  ctx.fillStyle = C.dim;
  ctx.fillText(m.subtitle, PAD, y);

  // ── 히어로 ──
  y += 84;
  ctx.font = font(400, 36);
  ctx.fillStyle = C.dim;
  ctx.fillText(m.heroLabel, PAD, y);
  y += 158;
  ctx.font = font(800, 168);
  ctx.fillStyle = m.up ? C.up : C.down;
  ctx.fillText(m.headline, PAD, y);

  // ── 원금/평가/수익 ──
  y += 64;
  const rowH = 88;
  roundRect(ctx, PAD, y, inner, rowH * m.stats.length + 32, 28);
  ctx.fillStyle = C.panel;
  ctx.fill();
  let ry = y + 30;
  m.stats.forEach((s, i) => {
    ry += rowH * 0.62;
    ctx.font = font(400, 40);
    ctx.fillStyle = C.dim;
    ctx.textAlign = "left";
    ctx.fillText(s.k, PAD + 44, ry);
    ctx.font = font(700, 46);
    ctx.fillStyle = i === 2 ? (m.up ? C.up : C.down) : C.text;
    ctx.textAlign = "right";
    ctx.fillText(s.v, PAD + inner - 44, ry);
    ry += rowH * 0.38;
  });
  ctx.textAlign = "left";
  y += rowH * m.stats.length + 32;

  // ── 차트 + 범례 ──
  y += 40;
  const chartH = 240;
  drawCurve(ctx, m.curve, PAD, y, inner, chartH, m.up);
  y += chartH + 52;
  ctx.font = font(400, 32);
  const legend: [string, string][] = [
    ["평가금액", m.up ? C.up : C.down],
    ["누적 원금", C.dim],
  ];
  let lx = PAD;
  for (const [label, color] of legend) {
    ctx.fillStyle = color;
    ctx.fillRect(lx, y - 20, 28, 8);
    ctx.fillStyle = C.dim;
    ctx.fillText(label, lx + 44, y - 8);
    lx += 44 + ctx.measureText(label).width + 60;
  }

  // ── 매수 횟수·평균단가 ──
  y += 56;
  ctx.font = font(400, 34);
  ctx.fillStyle = C.text;
  for (const line of wrap(ctx, m.meta, inner)) {
    ctx.fillText(line, PAD, y);
    y += 46;
  }

  // ── 가정·한계(백엔드 notes) — 남은 밴드에 맞춰 크기를 줄여 그린다 ──
  const bandTop = y + 16;
  const band = limit - bandTop;
  let size = 28;
  let lines: string[] = [];
  for (const candidate of [28, 26, 24, 22, 20]) {
    ctx.font = font(400, candidate);
    const wrapped = m.caveats.flatMap((n) => wrap(ctx, `· ${n}`, inner));
    size = candidate;
    lines = wrapped;
    if (wrapped.length * Math.round(candidate * 1.36) <= band) break;
  }
  const lineH = Math.round(size * 1.36);
  ctx.font = font(400, size);
  ctx.fillStyle = C.dim;
  let cy = bandTop + size;
  for (const line of lines) {
    ctx.fillText(line, PAD, cy);
    cy += lineH;
  }
  const contentBottom = cy - lineH + Math.round(size * 0.3);

  // ── CTA + 면책 (아래 고정) ──
  ctx.font = font(400, 28);
  ctx.fillStyle = C.dim;
  ctx.textAlign = "center";
  ctx.fillText(DISCLAIMER, CARD_W / 2, discY);

  roundRect(ctx, (CARD_W - ctaW) / 2, ctaY, ctaW, ctaH, ctaH / 2);
  ctx.fillStyle = C.cta;
  ctx.fill();
  ctx.font = font(700, 44);
  ctx.fillStyle = C.ctaText;
  ctx.fillText(CTA, CARD_W / 2, ctaY + ctaH / 2 + 16);
  ctx.textAlign = "left";

  return { fits: contentBottom <= limit, contentBottom, limit };
}
