// 실제 브라우저로 화면을 검증한다 — tsc·vite build 만으로는 "렌더링되는가"를 모른다.
//
// ## 왜 필요한가
// CI 는 `tsc -b` 와 `vite build` 만 돌린다. 둘 다 통과해도 런타임에 화면이 비거나 예외로
// 터질 수 있다(빈 화면은 컴파일 에러가 아니다). 백엔드는 tests/test_quickstart_smoke.py 가
// 실제 서버를 띄워 확인하는데, 프런트엔드에는 대응물이 없었다.
//
// ## CI 에서 돌지 않는다
// CI 에 브라우저 단계가 없고, 이걸 위해 무거운 의존성을 추가하지 않았다. 개발 중 손으로
// 돌리는 검증 도구다. Playwright 가 필요하다:
//     npm i -g playwright     (또는 npx playwright)
//
// ## 사용
//     node scripts/smoke_ui.mjs http://localhost:8000 [API_TOKEN]
// 종료코드 0 = 전부 통과. 실패는 무엇이 왜 틀렸는지 출력한다.
import { execSync } from "node:child_process";
import { createRequire } from "node:module";
import path from "node:path";

// playwright 를 로컬·전역 어디에 설치했든 찾아낸다.
// ESM 의 import 는 NODE_PATH 를 무시하고 전역 모듈도 해석하지 않으므로 createRequire 로
// 우회한다. 프로젝트 의존성에 넣지 않는 이유는 파일 상단 주석 참고.
function loadPlaywright() {
  const req = createRequire(import.meta.url);
  try {
    return req("playwright");
  } catch {
    try {
      const root = execSync("npm root -g", { encoding: "utf8" }).trim();
      return req(path.join(root, "playwright"));
    } catch {
      console.error(
        "✗ playwright 를 찾지 못했습니다. 설치 후 다시 실행하세요:\n" +
        "    npm i -g playwright\n" +
        "  (브라우저까지 필요하면  npx playwright install chromium)"
      );
      process.exit(2);
    }
  }
}

const { chromium } = loadPlaywright();

const BASE = process.argv[2] ?? "http://localhost:8000";
const TOKEN = process.argv[3] ?? "";

const failures = [];
const checks = [];

function check(name, ok, detail = "") {
  checks.push({ name, ok, detail });
  if (!ok) failures.push(`${name}${detail ? ` — ${detail}` : ""}`);
}

async function main() {
  const browser = await chromium.launch();
  const context = await browser.newContext({ viewport: { width: 430, height: 900 } });
  const page = await context.newPage();

  // 브라우저 콘솔 에러·미처리 예외를 모은다 — 빈 화면의 원인은 대개 여기 있다.
  //
  // 단, **외부 호스트 요청 실패는 세지 않는다.** 이 앱은 Google Fonts 를 링크하는데
  // 폰트가 막힌 네트워크에서도 폴백 폰트로 정상 렌더링된다. 그걸 실패로 세면 앱의
  // 결함이 아닌 것을 결함으로 보고하게 된다(실제로 그렇게 헛짚었다).
  const appOrigin = new URL(BASE).origin;
  const consoleErrors = [];
  page.on("console", (m) => {
    if (m.type() !== "error") return;
    const text = m.text();
    if (/fonts\.googleapis\.com|fonts\.gstatic\.com/.test(text)) return;
    // 리소스 로드 실패 메시지는 URL 을 담는다 — 앱 오리진이 아니면 무시한다.
    if (/Failed to load resource/.test(text) && !text.includes(appOrigin)) {
      const location = m.location?.().url ?? "";
      if (location && !location.startsWith(appOrigin)) return;
    }
    consoleErrors.push(text);
  });
  page.on("pageerror", (e) => consoleErrors.push(`pageerror: ${e.message}`));
  page.on("requestfailed", (r) => {
    if (r.url().startsWith(appOrigin)) {
      consoleErrors.push(`요청 실패 ${r.url()} — ${r.failure()?.errorText}`);
    }
  });

  // 토큰이 필요하면 localStorage 에 미리 심는다(TokenBanner 를 우회).
  if (TOKEN) {
    await context.addInitScript((t) => {
      window.localStorage.setItem("mystockbot_api_token", t);
    }, TOKEN);
  }

  try {
    for (const [label, path, expect] of [
      ["메인", "/", "코스피"],
      ["관심종목", "/watchlist", null],
      ["모의투자", "/paper", "총 평가자산"],
      ["알림", "/alerts", "알림 채널"],
    ]) {
      await page.goto(`${BASE}${path}`, { waitUntil: "domcontentloaded" });
      // SPA 가 실제로 마운트됐는지 — #root 가 비어 있으면 렌더 실패다.
      await page.waitForFunction(
        () => (document.querySelector("#root")?.childElementCount ?? 0) > 0,
        { timeout: 15000 }
      ).catch(() => {});
      const mounted = await page.evaluate(
        () => (document.querySelector("#root")?.childElementCount ?? 0) > 0
      );
      check(`${label}(${path}) 렌더`, mounted, "#root 가 비어 있다");

      // 탭바가 한 줄인지 — 탭을 추가하면 여기서 깨진다.
      //
      // 실제로 겪었다: `.tabbar` 가 `repeat(3, 1fr)` 로 탭 개수를 하드코딩하고 있어서
      // 4번째 탭(알림)을 넣자 2줄이 됐다. tsc·DOM 검사는 전부 통과했고 스크린샷에서만
      // 보였다. 높이 비율로 줄 수를 재서 자동으로 잡는다.
      const bar = await page.locator(".tabbar").boundingBox().catch(() => null);
      const tab = await page.locator(".tabbar__tab").first().boundingBox().catch(() => null);
      if (bar && tab) {
        const rows = Math.round(bar.height / tab.height);
        check(`${label} 탭바 1줄`, rows === 1, `${rows}줄로 줄바꿈됐다`);
      }

      if (expect) {
        // 한 번 읽고 끝내면 데이터 fetch 가 끝나기 전에 실패한다(플레이키). 나타날
        // 때까지 기다린다.
        const appeared = await page
          .getByText(expect, { exact: false })
          .first()
          .waitFor({ timeout: 15000 })
          .then(() => true)
          .catch(() => false);
        check(`${label} 내용에 "${expect}"`, appeared);
      }
    }

    // 알림 화면의 핵심 동작: 테스트 발송 버튼이 있고, 누르면 결과가 표시된다.
    await page.goto(`${BASE}/alerts`, { waitUntil: "domcontentloaded" });
    const button = page.getByRole("button", { name: /테스트 발송/ });
    const hasButton = (await button.count()) > 0;
    check("테스트 발송 버튼 존재", hasButton);

    if (hasButton) {
      // 채널이 하나도 설정되지 않은 서버에서는 버튼이 비활성인 게 **정상**이다.
      // 그걸 실패로 세지 않고, 대신 "왜 비활성인지"가 화면에 설명돼 있는지 본다.
      const enabled = await button.first().isEnabled();
      if (!enabled) {
        const body = (await page.textContent("body")) ?? "";
        check(
          "채널 없을 때 버튼 비활성 + 이유 안내",
          body.includes("인식된 채널이 없습니다"),
          "비활성인데 이유를 알려주지 않는다"
        );
        console.log(
          "  ⓘ 채널 미설정 서버라 발송 경로는 건너뜀 — " +
          "SLACK_WEBHOOK_URL 등을 준 서버로 다시 돌리면 검증된다"
        );
      } else {
        await button.first().click();
        const shown = await page
          .waitForSelector("[data-testid='alert-test-result']", { timeout: 25000 })
          .then(() => true)
          .catch(() => false);
        check("테스트 발송 결과 표시", shown, "결과 영역이 나타나지 않았다");
      }
    }

    check("브라우저 콘솔 에러 없음", consoleErrors.length === 0,
          consoleErrors.slice(0, 3).join(" | "));
  } finally {
    await browser.close();
  }

  for (const c of checks) {
    console.log(`${c.ok ? "✓" : "✗"} ${c.name}${c.ok || !c.detail ? "" : ` — ${c.detail}`}`);
  }
  if (failures.length) {
    console.error(`\n실패 ${failures.length}건`);
    process.exit(1);
  }
  console.log(`\n전부 통과 (${checks.length}건)`);
}

main().catch((e) => {
  console.error("스크립트 자체 실패:", e);
  process.exit(2);
});
