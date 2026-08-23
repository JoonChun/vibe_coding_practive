# MyStockBot 백엔드 배포 가이드

개인용 단일 사용자 배포. Windows PC(WSL2 Docker) 로컬 실행 + Cloudflare Tunnel 공개 연결.

## 1. 홈PC(WSL2 Docker) 실행

### 사전 준비
- Docker Desktop 설치 (WSL2 백엔드 활성화)
- MyStockBot/.env 파일 작성 (KIS_APP_KEY, KIS_APP_SECRET, CORS_ALLOWED_ORIGINS 등 — KIS_ACCOUNT_NO 는 불필요, 조회 전용이라 읽는 코드가 없다)

### 실행
```bash
cd MyStockBot
docker compose up -d --build
```

이미지 하나에 **API + 웹 UI** 가 다 들어 있다. 빌드가 끝나면 `http://localhost:8000` 에서
화면이 바로 뜬다(별도 프런트엔드 배포 없이). Vercel 배포도 그대로 유효한 경로다 — 그때는
프런트에 `VITE_API_BASE` 로 백엔드 공개 URL 을 주면 된다.

#### 알아둘 것
- **non-root 로 돈다.** 이미지는 `uid 10001` 사용자를 만들고 쓰기가 필요한 `/app/data`
  (SQLite DB + KIS 토큰 캐시)만 그 사용자 소유로 둔다. 코드는 root 소유 읽기전용이라
  앱이 자기 코드를 고칠 수 없다.
- **`user:` 로 실행 uid 를 호스트에 맞춘다.** `./data` 를 바인드 마운트하므로 호스트
  사용자(보통 `1000`) 소유 디렉터리에 써야 한다. compose 가 `${UID:-1000}:${GID:-1000}`
  으로 넘긴다. uid 가 1000 이 아니면:
  ```bash
  UID=$(id -u) GID=$(id -g) docker compose up -d --build
  ```
  이걸 안 맞추면 `unable to open database file` 로 죽는다.
- **의존성은 `requirements.lock.txt` 로 고정한다.** `requirements.txt` 는 하한만 있는
  느슨한 스펙이라, 같은 커밋을 다시 빌드해도 상위 버전이 딸려 들어와 어제 되던 이미지가
  오늘 깨질 수 있다. 락파일은 테스트가 통과한 버전 집합이다.
- 워커는 1개다. APScheduler 와 KIS 실시간 WS 가 프로세스 내 단일 인스턴스를 전제한다.

### 자동시작 설정
재부팅 후 자동으로 서버가 실행되도록:
1. Docker Desktop 설정 → "General" → "Start Docker Desktop when you log in" 체크
2. Windows 작업 스케줄러에 docker compose 자동실행 태스크 추가 (선택사항)

### 주의
PC 절전/수면 모드 해제 필요. Sleep에서 복귀할 때 Docker 재시작 필요할 수 있음.

### 로그 확인
```bash
docker compose logs -f mystockbot-api
```

### 중지
```bash
docker compose down
```

---

## 2. 모바일에서 보기 (개인용)

공개 배포 없이 내 폰에서 확인/설치만 하고 싶을 때.

### ① 같은 와이파이
PC와 폰이 같은 공유기에 물려 있으면, PC의 LAN IP로 바로 접속 가능.

```bash
cd web
npm run dev -- --host
```

Windows에서 `ipconfig`로 PC의 IPv4 주소 확인 (예: `192.168.0.15`) 후,
폰 브라우저에서 `http://192.168.0.15:5173` 접속.

정직하게 밝히면: 이 방식은 **HTTP**라서 "보안 컨텍스트"가 아니므로 서비스워커(오프라인 캐시)는
동작하지 않는다. 그래도 홈 화면에 바로가기 아이콘을 추가해 앱처럼 켤 수는 있음(오프라인 지원 없이).

### ② Tailscale (권장 — HTTPS로 PWA 완전 설치)
[Tailscale](https://tailscale.com)은 무료 사설망(mesh VPN). `tailscale serve`를 쓰면
유효한 HTTPS 인증서가 자동 발급되어(`https://<pc-이름>.<tailnet>.ts.net`) 서비스워커·
standalone 설치까지 완전하게 동작한다.

**설치**
- PC: https://tailscale.com/download → 설치 후 로그인
- 폰: App Store/Play Store에서 Tailscale 앱 설치 → 같은 계정으로 로그인

**PC에서 서비스 노출** (예시 명령)
```bash
# 백엔드(FastAPI, 8000번 포트)를 HTTPS로 노출
tailscale serve --bg --https=8443 http://localhost:8000

# 프론트를 빌드해서 정적으로 노출 (vite preview 사용)
cd web
npm run build
npm run preview -- --host --port 4173
tailscale serve --bg --https=443 http://localhost:4173
```

프론트가 다른 오리진(443)에서 백엔드(8443)를 호출하려면 `web/.env.local`에
`VITE_API_BASE=https://<pc-이름>.<tailnet>.ts.net:8443`을 지정한 뒤 다시 빌드.
(같은 오리진으로 합치고 싶다면 `tailscale serve`의 path 라우팅으로 `/api`만 백엔드로
넘기는 구성도 가능 — Tailscale 문서 참고.)

이후 폰에서 `https://<pc-이름>.<tailnet>.ts.net` 접속.

### ③ 설치법
- **Android (Chrome)**: 우측 상단 메뉴 → "앱 설치" 또는 "홈 화면에 추가"
- **iOS (Safari)**: 공유 버튼 → "홈 화면에 추가"

설치하면 standalone 모드(주소창 없이 전체화면)로 실행되고, 서비스워커가 정적 자산을
프리캐시해 재실행이 빨라진다. (API 응답은 캐시하지 않으므로 시세는 항상 최신 요청.)

> 공개 배포(Vercel/Cloudflare Tunnel)까지 갈 필요 없이, 개인용은 Tailscale로 충분하다.

---

## 3. 백엔드 HTTPS 공개 (터널)

**현재 운영: 3-1(Quick Tunnel) + `scripts/sync_tunnel.sh` 자동 동기화.**
터널이 죽거나 PC를 재부팅하면 URL이 바뀌므로 `sync_tunnel.sh`를 한 번 실행하면
터널 기동→Vercel env 갱신→재배포→검증까지 자동 처리된다.

| 방식 | 도메인 | URL 고정 | 비고 |
|---|---|---|---|
| **3-1. Cloudflare Quick Tunnel + sync 스크립트** | 불필요 | 변경되지만 자동 동기화 | **현 운영 방식** |
| 3-0. Tailscale Funnel | 불필요 | 고정 | 재배포 자체가 불필요해지는 대안 |
| Cloudflare Named Tunnel | **필요** | 고정 | 도메인 보유 시 |

### 3-0. Tailscale Funnel (무도메인 고정 URL 대안)

Windows에 Tailscale 앱을 설치하고(https://tailscale.com/download, 구글 로그인 가능),
PowerShell에서:

```powershell
# Docker 백엔드(8000)를 인터넷에 고정 HTTPS URL로 공개
tailscale funnel --bg 8000
# 첫 실행 시 관리 콘솔 링크가 뜨면 열어서 Funnel 허용 1회 승인
# 출력 예: https://<PC이름>.<테일넷이름>.ts.net  ← 재시작해도 동일(고정)
```

- 이 URL을 Vercel 환경변수 `VITE_API_BASE`에 넣고 Redeploy (URL이 고정이라 1회로 끝)
- 중지: `tailscale funnel --bg off` / 상태: `tailscale funnel status`
- WebSocket(/ws/ticks)도 같은 URL로 통과됨
- ⚠ Funnel은 인터넷 공개다 — `MYSTOCKBOT_API_TOKEN` 활성이 전제(§C 참고)

### 3-1. Quick Tunnel (구 운영 방식)

도메인을 소유하지 않은 개인용 배포에 적합합니다. 다만 프로세스 재시작마다 URL이 바뀌므로, 프론트 빌드에 박힌 `VITE_API_BASE` 환경변수가 무효화되는 문제가 있습니다. 이 문제를 해결하려면 **sync_tunnel.sh 스크립트**를 사용합니다.

#### Quick Tunnel의 한계

- **프로세스 재시작 시 URL 회전**: PC 재부팅, 프로세스 충돌 등이 발생하면 새로운 `*.trycloudflare.com` URL 할당
- **프론트 재배포 필요**: Vercel에 배포된 프론트 번들에 박힌 `VITE_API_BASE`가 구 URL을 가리켜 연결 불가
- **수동 재배포의 번거로움**: 매번 Vercel 환경변수를 수정하고 redeploy 필요

#### 기동

```bash
# 백엔드 Docker 실행 (8000번 포트)
cd MyStockBot
docker compose up -d --build

# Quick tunnel 시작 (메트릭 포트 자동 선택)
cloudflared tunnel --url http://localhost:8000
# 출력 예: https://dsc-mardi-guides-harbor.trycloudflare.com
```

nohup으로 백그라운드 실행:
```bash
nohup cloudflared tunnel --url http://localhost:8000 --metrics 127.0.0.1:20241 > data/cloudflared.log 2>&1 &
```

#### 자동 동기화 스크립트

**`scripts/sync_tunnel.sh`** 는 다음을 자동으로 수행합니다:

1. **터널 탐지**: 127.0.0.1:20241~20250 메트릭 포트에서 활성 터널 검색
2. **터널 기동**: 활성 터널이 없으면 cloudflared 자동 시작 (hostname 획득 최대 30초 + 신규 터널 DNS·엣지 전파 대기 최대 180초)
3. **좀비 정리**: DNS NXDOMAIN인 죽은 터널 종료
4. **Vercel 번들 분석**: mystockbot.vercel.app의 assets/*.js에서 현재 박힌 URL 추출
5. **URL 비교**: 현재 터널과 배포된 URL이 다르면 Vercel 재배포
6. **최종 검증**: 배포 후 번들 재추출로 동기화 확인

**사용법**

```bash
# 정상 실행 (필요시 Vercel 환경변수 갱신 및 재배포)
/home/joon/vibe_ws/MyStockBot/scripts/sync_tunnel.sh

# 드라이런 (동기화 필요 여부 판단만, Vercel 변경 없음)
/home/joon/vibe_ws/MyStockBot/scripts/sync_tunnel.sh --dry-run
```

**로그 위치**

```
/home/joon/vibe_ws/MyStockBot/data/cloudflared.log
```

#### 복구 절차 (PC 재부팅 / 터널 재시작 후)

1. **Docker 실행 확인**
   ```bash
   cd MyStockBot
   docker compose ps
   # mystockbot-api가 실행 중이어야 함
   ```

2. **동기화 스크립트 실행**
   ```bash
   /home/joon/vibe_ws/MyStockBot/scripts/sync_tunnel.sh
   ```
   스크립트가 다음을 자동으로 처리합니다:
   - 기존 터널이 살아있으면 재사용
   - 없으면 새로운 quick tunnel 기동
   - Vercel에 배포된 URL 확인
   - 필요하면 `VITE_API_BASE` 갱신 및 프론트 재배포

3. **배포 완료 대기** (약 1~2분)

4. **확인**
   ```bash
   curl https://mystockbot.vercel.app/api/health
   # 200 응답 → 정상
   ```

---

### 3-2. Named Tunnel (고정 URL, 권장 고려사항)

도메인을 소유한 경우, Cloudflare Named Tunnel을 사용해 고정 URL을 얻을 수 있습니다. 이 방식은 `sync_tunnel.sh` 자동화 불필요 (URL 고정).

#### 사전 준비
- Cloudflare 계정 (무료)
- cloudflared CLI 설치
- **도메인 소유** (Cloudflare 또는 타 DNS 제공자에 등록된 도메인)

#### 설정

```bash
# cloudflared 로그인
cloudflared tunnel login

# 터널 생성 (예: mystockbot)
cloudflared tunnel create mystockbot

# DNS 레코드 추가 (Cloudflare DNS에 위임된 도메인이어야 함)
cloudflared tunnel route dns mystockbot api.example.com

# 터널 시작 (localhost:8000과 연결)
cloudflared tunnel run --url http://localhost:8000 mystockbot
```

**또는** systemd/Windows 서비스로 자동시작:
```bash
cloudflared service install
```

#### 결과
- 고정 HTTPS URL 획득: `https://api.example.com`
- 프론트 배포 후 URL 변경 없음
- 포트포워딩 불필요

---

### 3-3. Tailscale Funnel (대안: 사설망 + 고정 URL)

도메인 없이 고정 URL과 HTTPS를 원한다면, **Tailscale Funnel**도 선택지입니다 (자세한 사항은 § 2-② 참고).

---

## 4. Vercel 프론트엔드 연결

### 초기 배포

```bash
cd web/
vercel deploy
```

### 환경변수 설정 (Vercel)

**Quick Tunnel 사용 시**
- `VITE_API_BASE` 초기값 설정 불필요
- `scripts/sync_tunnel.sh`가 실행될 때마다 자동으로 환경변수 갱신 및 재배포
- 수동 개입 불필요

**Named Tunnel 또는 고정 URL 사용 시**
- Vercel 프로젝트 설정 → "Environment Variables"에서:
  ```
  VITE_API_BASE=https://api.example.com
  ```
- URL이 고정되므로 추가 조치 불필요

### 백엔드 CORS 설정 (MyStockBot/.env)

**프론트엔드 오리진**(브라우저에서 페이지를 여는 주소)을 `CORS_ALLOWED_ORIGINS`에 추가:

```
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://<your-vercel-app>.vercel.app
```

**주의**: CORS가 검사하는 것은 *요청을 보내는 쪽*(프론트 페이지) 오리진이지, API 호스트가 아니다.
따라서 **터널 URL은 여기에 넣을 필요가 없고, Quick Tunnel URL이 회전해도 CORS 설정은 바꿀 필요 없다.**
(참고: 백엔드는 FastAPI `CORSMiddleware`의 정확 문자열 매칭이라 `https://*.trycloudflare.com` 같은
서브도메인 와일드카드는 어차피 동작하지 않는다.)

변경 후 docker compose 재시작:
```bash
docker compose restart mystockbot-api
```

---

## 5. 보안 주의 ⚠️

### API 토큰 인증 (MYSTOCKBOT_API_TOKEN)
Cloudflare Tunnel 등으로 외부 공개 시 **반드시 토큰을 설정**할 것. 설정하지 않으면
누구나 watchlist 조작·조회가 가능한 무인증 상태로 동작한다 (서버 시작 로그에
"⚠ API 토큰 미설정 — 인증 비활성" 경고가 출력됨).

**1) 토큰 생성**
```bash
openssl rand -hex 32
```

**2) MyStockBot/.env 에 설정**
```
MYSTOCKBOT_API_TOKEN=<위에서 생성한 값>
```
설정 후 `docker compose restart mystockbot-api` (또는 `up -d --build`)로 재시작.
서버 로그에 "API 토큰 인증 활성"이 출력되면 정상 적용된 것.

**3) 동작 방식**
- 토큰이 설정되면 모든 `/api/*` 요청에 `Authorization: Bearer <토큰>` 헤더가 필요하다.
- 예외: `GET /api/health` (헬스체크용, 항상 무인증), CORS preflight(OPTIONS).
- 헤더 누락/불일치 시 `401 {"detail": "인증이 필요합니다"}` 반환.

**4) 프론트엔드에서 토큰 입력 — 빌드에 토큰을 넣지 말 것**
토큰을 Vite 빌드 환경변수(`VITE_*`)로 넣으면 브라우저에 배포되는 공개 번들에
그대로 노출된다 (프론트 정적 파일은 누구나 열람 가능). 대신:
- 브라우저로 접속 후 최초 1회 토큰 입력 UI에서 입력
- `localStorage` 키 `mystockbot_api_token` 에 저장, 이후 모든 요청에 자동 첨부
- 401 응답 수신 시 토큰 입력 UI를 다시 노출

### 추가 방안 (선택, 병행 권장)
1. **Tailscale (사설망)**: 무료. 본인과 신뢰 사용자만 접근
   - `https://mystockbot.tailnet-abc.ts.net`으로 접근
   - Cloudflare 대신 Tailscale MagicDNS 사용

2. **Cloudflare Access (무료 계층)**: Cloudflare 계정으로 인증
   - Tunnel 설정 시 "Access" 정책 추가

토큰 인증만으로도 공개 노출 시 최소한의 보호는 되지만, Tailscale/Cloudflare Access와
병행하면 이중 방어가 된다.

---

## 6. VPS/서버 이사 (향후)

Oracle Cloud Always Free(서울), AWS EC2 등으로 이사 시:
```bash
# 이 docker-compose.yml을 그대로 사용
docker compose up -d --build
```

- DB 백업: `cp data/mystockbot.db ./mystockbot.db.bak`
- 환경변수 파일(`.env`) 복사 후 비밀값 갱신
- Cloudflare Tunnel 재설정 (IP 변경)

---

## 7. Vercel에 백엔드를 배포할 수 없는 이유

- **서버리스 제약**: Vercel은 함수형 서버리스(AWS Lambda 유사). 요청 당 cold start, 최대 실행 시간 제한
- **상시 프로세스 불가**: APScheduler 평일 16:00 자동실행 불가
- **SQLite 부적합**: 임시 파일시스템. 데이터 영속성 보장 없음
- **WebSocket 제한**: Phase 2 KIS WebSocket 상시 연결 불가능

→ 완전한 서버가 필요하므로 로컬 Docker 또는 VPS 필수.

---

## 트러블슈팅

### Docker 컨테이너 실행 안 됨
```bash
docker compose logs mystockbot-api
```
에러 메시지 확인. 주로 .env 파일 누락 또는 KIS API 키 오류.

### 데이터베이스 초기화 필요
```bash
rm -rf data/mystockbot.db
docker compose restart mystockbot-api
```

### Cloudflare Quick Tunnel 재시작 후 웹 접속 불가

**현상**: mystockbot.vercel.app 접속 시 "Cannot GET /api/..." 오류

**원인**: quick tunnel URL이 바뀌었는데 Vercel의 `VITE_API_BASE`가 구 URL을 가리킴

**해결**:
```bash
/home/joon/vibe_ws/MyStockBot/scripts/sync_tunnel.sh
```
스크립트가 다음을 자동으로 처리합니다:
- 현재 활성 터널 탐지 (또는 새로 기동)
- Vercel 번들에서 박힌 URL 추출
- 필요하면 환경변수 갱신 및 재배포

**배포 진행 상황 확인**:
```bash
# 로그 확인
tail -f /home/joon/vibe_ws/MyStockBot/data/cloudflared.log

# 드라이런으로 필요 여부만 확인 (재배포 없음)
/home/joon/vibe_ws/MyStockBot/scripts/sync_tunnel.sh --dry-run
```

### Cloudflare Named Tunnel 연결 안 됨

Named Tunnel 사용 중 문제 발생 시:
```bash
cloudflared tunnel info <tunnel-name>
```
터널 상태 확인. 인증서 갱신 필요 시 `cloudflared tunnel delete/create`.

---

## 7. 운영 — 백업·모니터링·연간 체크리스트

### 7-1. DB 백업 (자동)
서버가 매일 17:00(KST)에 `data/backups/mystockbot-YYYYMMDD.db` 스냅샷을 만든다
(sqlite3 backup API — WAL 쓰기 중에도 일관 스냅샷, 최근 14개 보존, scheduler `daily_db_backup`).

**복구**: 컨테이너 중지 → `cp data/backups/mystockbot-<날짜>.db data/mystockbot.db` → 재시작.

**주의**: 백업이 같은 디스크에 있다 — 디스크가 통째로 죽는 시나리오는 못 막는다.
분기 1회 정도 `data/backups/` 최신 파일을 다른 기기·클라우드에 복사해 둘 것.

### 7-2. 모니터링 (서버 다운·데이터 강등 감지)
`/api/health` 는 무인증이다. 외부 uptime 체커(Healthchecks.io, UptimeRobot 등 무료 플랜)에
터널 URL 기준으로 등록하면 서버·터널이 죽었을 때 메일/푸시를 받는다:

```bash
curl -s https://<터널URL>/api/health
```

응답 필드:
- `status: ok` — 프로세스 생존 (liveness)
- `ready: true` — 첫 수집 사이클 완료 (readiness)
- `kis.ok: false` — **KIS 토큰 발급 실패 상태.** 앱키 만료·폐기로 전 종목이 yfinance
  지연 데이터로 강등됐다는 뜻이다(서버는 살아 있으므로 status 는 ok 로 유지된다).
  `kis.detail` 에 사유가 담긴다.

토큰 발급이 3사이클 연속 실패하면 서버가 알림 채널(Discord/Slack — 켜져 있는 것)로
시스템 경보를 1회 보낸다(6시간 쿨다운, collector `_note_kis_token_result`).

### 7-3. 배포 후 점검 (수동 체크리스트)
프론트 재배포·터널 전환·컨테이너 재빌드 후에는 브라우저 스모크를 한 번 돌린다:

```bash
node scripts/smoke_ui.mjs <배포 URL> <API 토큰>
```

(캔버스 렌더·탭바·푸터 겹침 등 실제로 겪은 회귀를 잡도록 설계된 스크립트다 —
CI 에는 없으므로 이 체크리스트가 유일한 실행 지점이다.)

### 7-4. 연간 체크리스트 (조용히 썩는 것들)
| 주기 | 항목 | 방법 |
|------|------|------|
| **매년 (발급일 기준)** | KIS 앱키 만료(1년) 재발급 | KIS 개발자센터 재발급 → `.env` 의 `KIS_APP_KEY`/`KIS_APP_SECRET` 교체 + GitHub Secrets 갱신 → 컨테이너 재시작. 만료일을 캘린더에 기록해 둘 것 |
| **매년 12월** | 휴장일 하드코딩 표 갱신 | `src/market_calendar.py` 의 `TABLE_MAX_YEAR`·다음 해 휴장일 추가 (KRX 휴장일 공시 참조). 서버 런타임은 KIS 캐시가 우선이라 안전하지만 GitHub Actions 크론은 이 표만 본다 |
| **분기 1회** | 백업 오프사이트 복사 | 7-1 참고 |
| **분기 1회** | 의존성 lock 재생성 | `pip install -r requirements.txt && pip freeze > requirements.lock.txt` 후 테스트 통과 확인 |

---

마지막 업데이트: 2026-08-23
