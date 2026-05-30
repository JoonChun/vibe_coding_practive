# PIXEL-TOOLS.md — 도제 12인 픽셀아트 제작 도구 결정

> Phase 2 F: 도제 12인 placeholder SVG → 매니저급 32×32 픽셀아트 승격
> 작성: 정약용 (ideator-yagyong) + 제자 (research-jeja) 리서치 통합
> 정리: 메인 Claude (사관 Write 권한 우회)
> 기준일: 2026-05-17

---

## 1. 레퍼런스 명세 (매니저 SVG 역분석)

| 항목 | 명세 |
|---|---|
| 파일 형식 | SVG (`<rect>` 기반, 순수 좌표 명세) |
| 캔버스 | `viewBox="0 0 32 32"` |
| 렌더링 | `shape-rendering="crispEdges"`, display 64×64 (2× CSS 스케일) |
| rect 수 | 캐릭터당 약 20~30개 |
| 레이어 구조 | 모자 → 얼굴+음영 → 목+깃 → 몸통+소매 → 흉배 → 신발 |
| 팔레트 | 캐릭터 고유 베이스 hex 1개 + 어두운 음영 1개 (2-tone) + 살색 #F0CFA0 + 검정 #1A1410 |
| 표정 | 눈 2×2 검정 rect, 입 4×1 직선 (결연·차분) |
| 신물(소품) | 캐릭터별 1~2개 (망치, 두루마리, 학 흉배 등) |

**핵심 제약**: 최종 산출물은 PNG가 아니라 **SVG `<rect>` 집합**이어야 한다.
CSS `image-rendering: pixelated`와 정합하고, SVG 내 주석·컬러 변수 유지 가능하기 때문.

---

## 2. 후보 도구 비교 매트릭스

| 평가 기준 | PixelLab.ai | Aseprite (수공) | Retro Diffusion | Piskel (수공) | SVG 직접 편집 |
|---|---|---|---|---|---|
| **일관성** | ★★★★☆ style ref 64장 업로드 | ★★★★★ 작가 통제 | ★★★☆☆ char ref 미지원 | ★★★★☆ 수작업 통제 | ★★★★★ 완전 통제 |
| **32×32 직접 출력** | ★★★★☆ 32px 지원, $0.0073/장 | ★★★★★ 직접 지정 | ★★★★☆ 32~276px | ★★★★★ 직접 지정 | ★★★★★ viewBox 직접 |
| **SVG rect 출력** | ★☆☆☆☆ PNG → 후처리 | ★★☆☆☆ PNG → 변환 | ★☆☆☆☆ PNG → 변환 | ★★☆☆☆ PNG → 변환 | ★★★★★ 바로 SVG |
| **idle 4-frame 애니** | ★★★★☆ Pro 플랜 | ★★★★★ 타임라인+어니언 | ★★★☆☆ 기본 애니 | ★★★★☆ 프레임 편집 | ★★★☆☆ SMIL/CSS |
| **라이선스·비용** | $9~22/월, 상업 OK, 모델 재학습 금지 | $20 일회성, 완전 소유 | $65 (Aseprite 확장), 상업 OK | 무료 오픈소스 | 무료, 완전 소유 |
| **시간 비용 (12개)** | 2~4시간 (수정 포함) | 24~36시간 | 6~10시간 | 30~40시간 | 6~12시간 |
| **매니저 톤 정합** | AI 출력 → rect 변환 손실 | 수공 톤 맞춤 | 모델 스타일 불일치 가능 | 수공 통제 | 동일 구조·팔레트 |

---

## 3. 핵심 장벽: PNG → SVG rect 변환

PixelLab·Retro Diffusion·Piskel은 모두 **PNG 출력**이 기본이다.
매니저 SVG는 `<rect x y width height fill>` 구조이므로, PNG를 그대로 `<img src>`로 넣으면:
- `shape-rendering: crispEdges` 효과 없음
- CSS 컬러 오버라이드 불가
- 코드 내 주석·팔레트 명세 소멸

PNG → SVG rect 변환 도구 (Sprite-AI, GLORP, Scalable Pixels) 존재하지만 **변환 품질이 컬러 수·디더링에 민감**, 매니저 SVG의 의미 레이어(모자/얼굴/몸통) 재현 불가.

---

## 4. 추천 도구

### 추천: **SVG `<rect>` 직접 편집** (매니저 SVG를 템플릿으로 활용)

**사유:**

1. **일관성 완벽 보장** — 매니저 4명이 이미 `<rect>` 구조·팔레트·레이어 순서를 확립. 템플릿 복사 + `fill` 값과 모자 형태만 교체하면 자동 동일 미감.
2. **SVG rect 출력이 유일한 방식** — PNG 기반 도구는 모두 후변환 단계 필요, 변환 품질 보장 불가. 매니저와 동일한 파일 구조를 가장 빠르게 얻는 방법은 직접 작성.
3. **시간 비용 최소** — 매니저 SVG 1개 기반으로 `fill` hex + 모자 + 소품 rect 3~5개만 변경 → 도제 1개 완성. 도제당 30~60분 × 12 = 6~12시간.
4. **비용 제로** — 도구 비용·라이선스 없음.
5. **인스타 콘텐츠 자산화** — SVG 코드 자체가 "조선왕조 개발실록" 아카이브의 일부. AI 생성물이 아닌 직접 설계 자산임을 명시 가능.

**단점:**
- 미술 감각이 아닌 **좌표 감각** 필요. 그러나 매니저 템플릿이 이미 있어 좌표 탐색 비용 최소.
- idle 4-frame 애니는 SMIL 또는 CSS animation으로 직접 작성 필요.

---

## 5. 폴백 옵션

### 폴백: **PixelLab.ai (style reference) + GLORP 변환 + 수동 정제**

PixelLab.ai style reference로 매니저 SVG → PNG → 32×32 PNG 생성 → GLORP(로컬 변환, 서버 미전송)로 SVG rect 변환 → Aseprite/텍스트 에디터에서 팔레트 정제.

**사용 시점**: SVG 직접 편집 중 특정 캐릭터의 자세·소품이 너무 복잡해 시각적 착안점 필요 시 초안 생성용.

**비용**: PixelLab.ai 월 $9 (Starter) + 12캐릭터 × 약 40 크레딧.
**라이선스**: 유료 플랜 상업 OK, 모델 재학습 금지.

---

## 6. Aseprite·Retro Diffusion 미채택 사유

| 도구 | 미채택 사유 |
|---|---|
| **Aseprite** | 출력물 PNG. SVG rect 변환 필수, 수공 드로잉 시간(캐릭터당 2~3시간) 비효율. |
| **Retro Diffusion** | Character reference 부재. 28개 내장 스타일 중 매니저 SVG의 "rect 미감"과 일치 없음. |
| **Piskel** | 무료이나 Aseprite보다 기능 부족. SVG 출력 미지원. |
| **Nano Banana / Gemini** | 픽셀 프롬프트 가능하나 32×32 rect 구조 출력 미보장. 캐릭터 일관성 미확인. |

---

## 7. 12개 작업 워크플로 (SVG 직접 편집 기준)

### 7-1. 준비 (0.5시간)

1. `planner-dojeon.svg` → `_template-doje.svg` 복사
2. 템플릿에서 **모자·흉배·소품 rect**를 주석 태그로 분리
3. 도제 12명의 `hex` + `parent` 매핑 테이블 작성 (`characters.ts` 기준)

### 7-2. 배치 생산 (캐릭터당 30~60분, 총 6~12시간)

각 캐릭터당:
1. 템플릿 복사 → 파일명 `{character-key}.svg`
2. **관복 베이스 hex 교체** (`fill` 전체 치환, 2곳: 베이스·음영)
3. **모자 교체** — 직위에 따라 사모/두건/정자관/갓/전립/복두/패랭이 중 택일
4. **소품 추가** — 직무 상징 1~2개 rect
5. **흉배 교체** — 도제 등급(레벨 0/1/2)에 따라

### 7-3. 매핑 우선순위 (빠른 순)

| 그룹 | 사유 |
|---|---|
| 정도전 휘하 3명 | 문관 사모 구조 → 팔레트 교체만으로 빠른 완성 |
| 장영실 휘하 4명 | 두건(패랭이/공장건) 구조 재사용 |
| 이순신 휘하 3명 | 무관 전립/벙거지 구조 신규 설계 |
| 정약용 휘하 2명 | 정자관 구조 재사용 |

### 7-4. idle 4-frame 애니 (선택, 캐릭터당 30분)

SVG SMIL 또는 CSS animation으로:
- `frame 0`: 기본 자세
- `frame 1`: 소매 rect y+1 (숨쉬는 느낌)
- `frame 2`: 기본 자세 복귀
- `frame 3`: 눈 rect height=1 (깜빡임)

```svg
<animate attributeName="y" values="20;21;20;20" dur="1.2s" repeatCount="indefinite"/>
```

(Phase 2 F에서는 정적 1-frame 우선, 4-frame은 후속.)

---

## 8. 캐릭터별 모자·소품 제안 (DOJE-CONCEPT-SHEET.md 화공 발산과 통합)

| key | displayName | hex | 모자 형태 | 소품 |
|---|---|---|---|---|
| planning-hojo | 호조낭청 | #06B6D4 | 복두 (각 1px) | 두루마리 + 붓 |
| uiux-hwawon | 도화서 화원 | #7C3AED | 복두 | 그림 붓 + 팔레트 점 |
| docs-sagwan | 사관 | #3B82F6 | 복두 (각 없음) | 붓 + 책 |
| frontend-dancheong | 단청도제 | #D97706 | 패랭이 | 채색 붓 + 물감 단지 |
| backend-gigwan | 기관도제 | #C2660A | 공장건 | 망치 + 톱니 1px |
| infra-tomok | 토목도제 | #DB2777 | 패랭이 (챙 넓게) | 삽 + 돌 덩이 |
| integration-tongsin | 통신도제 | #0891B2 | 패랭이 | 봉수 깃발 + 파발 끈 |
| security-chukhu | 척후 | #DC2626 | 벙거지 | 단도 + 망원경 |
| perf-uiwon | 의원 | #EC4899 | 벙거지 (낮은) | 약사발 + 약병 |
| test-gungwan | 군관 | #B91C1C | 전립 (둥근) | 창 + 깃발 |
| research-jeja | 제자 | #16A34A | 정자관 (격자) | 두루마리 + 붓 |
| visual-hwagong | 화공 | #15803D | 정자관 | 화필 + 종이 |

상세 픽셀 묘사·표정 코드·흉배 등급은 [`DOJE-CONCEPT-SHEET.md`](./DOJE-CONCEPT-SHEET.md) 참조.

---

## 9. 라이선스 및 출처 기록 형식

SVG 직접 편집 시 저작권·라이선스 이슈 없음 (100% 자체 제작).
각 SVG 파일 상단 주석에 다음 형식으로 기록 권장:

```svg
<!--
  Character: {displayName} ({key})
  Version: 1.0 / Phase 2 F
  Author: devDogam pixel team
  License: MIT (devDogam project internal)
  Based on: planner-dojeon.svg template (32×32 rect-based pixel art)
  Palette: base #{hex}, shadow #{shadow-hex}, skin #F0CFA0, outline #1A1410
-->
```

폴백(PixelLab.ai) 사용 시:
```
Source: PixelLab.ai (paid plan, commercial OK)
Restriction: DO NOT use for AI model training
Generated: {YYYY-MM-DD}
Post-processed: GLORP SVG conversion + manual rect refinement
```

---

## 10. 결정 요약

| 항목 | 결정 |
|---|---|
| **추천 도구** | SVG `<rect>` 직접 편집 (매니저 템플릿 활용) |
| **폴백** | PixelLab.ai style ref → GLORP SVG 변환 → 수동 정제 |
| **미채택** | Aseprite, Retro Diffusion, Piskel, Nano Banana |
| **예상 소요** | 12캐릭터 × 45분 = 9시간 (± idle 애니 +6시간) |
| **비용** | $0 (폴백 시 PixelLab $9/월 일시적) |
| **라이선스** | 완전 자체 소유, 출처 표기 의무 없음 |

---

*결정: 정약용(ideator-yagyong). 집행: 장영실 휘하 단청도제(frontend-dancheong).*

## Sources (제자 리서치)

- [PixelLab — Consistent Style Docs](https://www.pixellab.ai/docs/tools/consistent-style)
- [PixelLab AI Review (2026)](https://www.jonathanyu.xyz/2025/12/31/pixellab-review-the-best-ai-tool-for-2d-pixel-art-games/)
- [PixelLab FAQ](https://www.pixellab.ai/docs/faq)
- [PixelLab Terms of Service](https://www.pixellab.ai/termsofservice)
- [Retro Diffusion Pixel Art Generator](https://astropulse.itch.io/retrodiffusionai)
- [12 best pixel art generators in 2026 — Sprite-AI](https://www.sprite-ai.art/blog/best-pixel-art-generators-2026)
- [Pixel art PNG to SVG converter — Sprite-AI](https://www.sprite-ai.art/tools/png-to-svg)
- [GLORP Pixel Art to SVG Converter](https://glorp.art/)
- [Piskel — Free online sprite editor](https://www.piskelapp.com/)
- [Scalable Pixels — Bitmap to SVG converter](https://www.scalablepixels.com/)
