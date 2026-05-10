# BACKLOG — devDogam Phase 1 보류 항목

본 문서는 Week 2 검수(이순신·척후) 시 발견되었으나 Phase 1 범위 밖으로 결정된 위험·미흡 사항을 추적합니다. Phase 2 진입 또는 별도 작업 시 우선순위 순으로 재검토합니다.

---

## 보류 항목

| # | 항목명 | 발견 시점 | 위협 종류 | 영향 추정 | 완화 방향 | 우선순위 |
|---|---|---|---|---|---|---|
| **A** | `/tmp/dogam_task_id` TOCTOU 가능성 | Week 2 검수 (2026-05-10) | 보안 (race condition) | 다중 사용자 환경 또는 호스트 공유 시 symlink 공격으로 임의 파일 쓰기 가능. 현재 단일 사용자 dev 환경에서는 낮음. | (1) `${TMPDIR:-/tmp}/devDogam_${USER}_${RANDOM}` 방식 격리 명명, (2) `umask 0077` 적용 및 권한 600 강제, (3) taskId 세션 공유 폐기 및 매 훅 호출마다 신규 생성 | **P2** |
| **B** | Next.js 16.2.1 / PostCSS CVE (npm audit) | Week 2 검수 (2026-05-10) | 보안 (DoS, XSS) | Next.js 9.3.4 계열 DoS + PostCSS <8.5.10 XSS via Unescaped `</style>`. Dev 환경 내부 사용 시 노출 면 최소. 공개 호스팅 또는 외부 입력 처리 시 위험. | (1) `npm audit fix --force`로 next 16.2.x 최신 패치 적용, (2) PostCSS 직접 dependency 추가하여 8.5.10+ 강제, (3) Phase 2 배포 검토 전 일괄 업그레이드 | **P1** |
| **C** | `.claude/settings.local.json` 권한 과다 누적 | Week 2 검수 (2026-05-10) | 보안 (과다 권한) | 다른 vibe_ws 하위 프로젝트의 bash/read 권한 60+개 누적. devDogam 자체와 무관한 잔여물. 기능에는 영향 없음, 최소 권한 원칙 위반. | (1) 다른 프로젝트 활성도 확인 후 사용 안 하는 권한 제거, (2) 프로젝트별 settings 분리 검토 (devDogam/.claude/settings.local.json 내장 가능성), (3) 권한 카탈로그 문서화 후 정기 정리 | **P2** |

---

## 재검토 절차

1. **P0 항목 없음** — Phase 1 완료로 즉시 처리 대상 없음.
2. **P1 항목 (B)** — Phase 2 진입 시 또는 호스팅 계획 수립 시 재검토. npm audit 결과 최신화 후 upgrade 경로 수립.
3. **P2 항목 (A, C)** — Phase 2 이후 또는 다중 사용자/다중 프로젝트 확산 시 검토. A는 호스트 공유 환경 진입 시, C는 다른 프로젝트 권한 정리와 함께 추진.

---

## 기록 이력

| 날짜 | 작성자 | 행동 |
|---|---|---|
| 2026-05-10 | 사관 (docs-sagwan) | 신규 작성. Week 2 검수 3개 항목 기록 |
