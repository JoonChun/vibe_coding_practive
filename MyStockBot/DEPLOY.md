# MyStockBot 백엔드 배포 가이드

개인용 단일 사용자 배포. Windows PC(WSL2 Docker) 로컬 실행 + Cloudflare Tunnel 공개 연결.

## 1. 홈PC(WSL2 Docker) 실행

### 사전 준비
- Docker Desktop 설치 (WSL2 백엔드 활성화)
- MyStockBot/.env 파일 작성 (KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO, CORS_ALLOWED_ORIGINS 등)

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

## 3. Cloudflare Tunnel (무료 HTTPS 고정 URL)

### 사전 준비
- Cloudflare 계정 (무료)
- cloudflared CLI 설치

### 터널 생성 및 설정
```bash
# cloudflared 로그인
cloudflared tunnel login

# 터널 생성 (예: mystockbot)
cloudflared tunnel create mystockbot

# 터널 설정 파일 작성
# ~/.cloudflare-warp/config.yml 또는 명령줄로:
cloudflared tunnel route dns mystockbot <your-domain.com>

# 터널 시작 (localhost:8000과 연결)
cloudflared tunnel run --url http://localhost:8000 mystockbot
```

**또는** systemd/Windows 서비스로 자동시작:
```bash
cloudflared service install
```

### 결과
- 고정 HTTPS URL 획득: `https://mystockbot.<your-domain.com>`
- 포트포워딩 불필요 (Cloudflare가 중개)
- 공유기 설정 변경 불필요

---

## 4. Vercel 프론트엔드 연결

### 프론트 배포
```bash
cd web/
vercel deploy
```

### 환경변수 설정 (Vercel)
Vercel 프로젝트 설정 → "Environment Variables":
```
VITE_API_BASE=https://mystockbot.<your-domain.com>
```

### 백엔드 CORS 설정 (MyStockBot/.env)
Vercel 도메인을 `CORS_ALLOWED_ORIGINS`에 추가:
```
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://<your-vercel-app>.vercel.app,https://mystockbot.<your-domain.com>
```

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

### Cloudflare Tunnel 연결 안 됨
```bash
cloudflared tunnel info mystockbot
```
터널 상태 확인. 인증서 갱신 필요 시 `cloudflared tunnel delete/create`.

---

마지막 업데이트: 2026-07-12
