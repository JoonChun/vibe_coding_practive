# MyStockBot 배포 가이드

## A. 3인 공개 배포 (B안) — 추천 방식

친구 2명과 함께 사용하는 개방형 배포. **Vercel(프론트) + PC Docker(백엔드) + Cloudflare Tunnel(HTTPS 공개)**.

### A-0. 사전 준비

- ✅ Docker Desktop 설치 (WSL2 활성화)
- ✅ MyStockBot/.env 파일 준비 (KIS_APP_KEY, KIS_APP_SECRET, KIS_ACCOUNT_NO)
- ✅ Cloudflare 무료 계정
- ✅ Vercel 계정 (GitHub 연동)

**중요**: 이 가이드의 A-1~A-6 단계는 **모두 WSL(Ubuntu) 터미널에서 실행해야 합니다**. Windows 기본 터미널인 PowerShell에서 그대로 복사·붙여넣기하면 bash 문법 오류로 실패합니다. Windows Terminal을 열고 WSL 프로필을 선택하거나, PowerShell에서 `wsl` 명령으로 WSL에 진입한 후 다음 단계를 실행하세요.

이 가이드는 **사용자가 직접** 실행하는 단계를 기준.

### A-1. 백엔드 .env 준비 (사용자가 직접)

```bash
cd MyStockBot
cat > .env << EOF
# === KIS API 인증 ===
KIS_APP_KEY=<당신의 KIS앱키>
KIS_APP_SECRET=<당신의 KIS비밀키>
KIS_ACCOUNT_NO=<당신의 KIS계좌번호>

# === API 토큰 (공유) ===
MYSTOCKBOT_API_TOKEN=$(openssl rand -hex 32)

# === CORS (친구들이 접속할 도메인) ===
CORS_ALLOWED_ORIGINS=http://localhost:5173,https://<your-vercel-project>.vercel.app,https://mystockbot.<your-domain>

# === 기타 설정 ===
TIMEZONE=Asia/Seoul
COLLECTOR_INTERVAL_MARKET=30
COLLECTOR_INTERVAL_IDLE=600
EOF
```

**생성된 토큰 값을 기록해두세요** (친구들에게 공유할 때 필요).

### A-2. Docker 시작 (사용자가 직접)

```bash
cd MyStockBot
docker compose up -d --build
```

**확인**:
```bash
docker compose logs mystockbot-api | grep "API 토큰 인증 활성"
```

"API 토큰 인증 활성"이 로그에 보이면 성공. **PC를 켜둔 상태로 유지해야 함**.

### A-3. Cloudflare Tunnel 설정 (사용자가 직접)

1. **cloudflared 설치**
   - 다운로드: https://developers.cloudflare.com/cloudflare-one/connections/connect-networks/downloads/
   - 또는 `choco install cloudflared` (Windows Chocolatey)

2. **터널 생성 및 실행**
   ```bash
   cloudflared tunnel login
   cloudflared tunnel create mystockbot
   cloudflared tunnel route dns mystockbot <your-domain>
   cloudflared tunnel run mystockbot
   ```

3. **시스템 서비스로 등록 (자동시작, 선택)**
   ```bash
   cloudflared service install
   ```

**확인**: `https://mystockbot.<your-domain>` 접속 → 401 오류(토큰 미입력은 정상)

### A-4. Vercel 프론트 배포 (사용자가 직접)

```bash
cd web
vercel env add VITE_API_BASE
# 프롬프트: https://mystockbot.<your-domain>
vercel deploy --prod
```

### A-5. 친구 온보딩 (사용자가 직접)

친구 2명에게 다음 전달:
1. **링크**: `https://mystockbot.<your-domain>`
2. **토큰**: A-1 단계에서 생성한 값 (개별 전달, 단체 채팅 X)

친구 접속 순서:
1. 링크 접속 → 초록 배너에서 토큰 입력
2. PWA 설치: Android(Chrome "앱 설치") / iOS(Safari "홈화면에 추가")
3. 완료!

### A-6. 권장: Cloudflare Access (2단계 인증, 선택)

Cloudflare 계정에서:
1. Tunnel → mystockbot → Access 탭 → 정책 추가
2. "이메일 주소 포함" → 3명의 이메일 입력
3. 저장

이후 친구들이 이메일로도 인증 가능.

---

## B. 개인용: 모바일에서만 보기

공개 배포 없이 본인 폰에서만 확인/설치하고 싶을 때.

### B-1. 같은 와이파이

PC와 폰이 같은 공유기에 물려 있으면, PC의 LAN IP로 바로 접속 가능.

```bash
cd web
npm run dev -- --host
```

Windows에서 `ipconfig`로 PC의 IPv4 주소 확인 (예: `192.168.0.15`) 후,
폰 브라우저에서 `http://192.168.0.15:5173` 접속.

**주의**: 이 방식은 **HTTP**라서 서비스워커(오프라인 캐시)는 동작하지 않음.

### B-2. Tailscale (권장 — HTTPS로 PWA 완전 설치)

[Tailscale](https://tailscale.com)은 무료 사설망. `tailscale serve`로 자동 HTTPS 인증서.

**설치**
- PC: https://tailscale.com/download → 설치 후 로그인
- 폰: App Store/Play Store Tailscale 앱 → 같은 계정으로 로그인

**PC에서 서비스 노출**
```bash
# 백엔드
tailscale serve --bg --https=8443 http://localhost:8000

# 프론트
cd web
npm run build
npm run preview -- --host --port 4173
tailscale serve --bg --https=443 http://localhost:4173
```

프론트가 백엔드를 호출하려면 `web/.env.local` 수정:
```
VITE_API_BASE=https://<pc-이름>.<tailnet>.ts.net:8443
```

다시 빌드 후 폰에서 `https://<pc-이름>.<tailnet>.ts.net` 접속.

### B-3. PWA 설치법

- **Android (Chrome)**: 우측 상단 메뉴 → "앱 설치"
- **iOS (Safari)**: 공유 버튼 → "홈 화면에 추가"

---

## C. 보안 및 인증

### API 토큰 (MYSTOCKBOT_API_TOKEN)

외부 공개 시 **반드시 토큰을 설정**할 것. 설정하지 않으면 누구나 watchlist 조작 가능.

**토큰 생성 및 설정**
```bash
openssl rand -hex 32  # 토큰 생성
# MyStockBot/.env에 추가
MYSTOCKBOT_API_TOKEN=<위 결과>

# 재시작
docker compose restart mystockbot-api
```

**동작**
- 모든 `/api/*` 요청에 `Authorization: Bearer <토큰>` 헤더 필수
- 예외: `GET /api/health`, CORS preflight(OPTIONS)
- WS `/ws/ticks`는 `?token=` 쿼리로 전달 (헤더 제약)

**프론트엔드 입력**
- 빌드 환경변수(`VITE_*`)로 토큰을 넣지 말 것 (공개 노출)
- 대신: 브라우저 접속 후 초록 배너에 입력 → `localStorage` 저장

### 추가 방안 (병행 권장)

1. **Cloudflare Access**: 이메일 인증 (A-6 참고)
2. **Tailscale 사설망**: 신뢰 네트워크만 접근 (B-2 참고)

---

## D. 운영

### Docker 기본 명령

```bash
# 재시작 (코드/설정 반영)
docker compose down
docker compose up -d --build

# 로그 (실시간)
docker compose logs -f mystockbot-api

# DB 초기화
rm -rf data/mystockbot.db
docker compose restart mystockbot-api

# 중지
docker compose down
```

### Stock Master 갱신

```bash
# 자동 (평일 매일 16:00 실행, APScheduler cron, 7일 stale 조건)
# 또는 수동:
python3 -c "import sys; sys.path.insert(0, 'src'); import stock_master; stock_master.refresh_stock_master()"
```

### 성능 점검

**응답시간 목표**:
- `/api/snapshot`: < 5ms
- `/api/stocks/search`: < 50ms
- `/api/stocks/{code}/candles`: 신선(600s) < 50ms, 아니면 < 2초

```bash
# 확인
time curl -H "Authorization: Bearer $TOKEN" http://localhost:8000/api/snapshot
```

### Cloudflare Tunnel 상태

```bash
cloudflared tunnel info mystockbot
cloudflared tunnel logs mystockbot
```

### Vercel 재배포

```bash
cd web
vercel deploy --prod
```

### DB 백업

```bash
cp data/mystockbot.db data/mystockbot.db.$(date +%Y%m%d).bak
```

### 자동시작 설정 (PC 재부팅 후)

1. Docker Desktop → Settings → "Start Docker Desktop when you log in" 체크
2. cloudflared를 Windows 서비스로 등록 (A-3 참고)

---

## E. VPS 이사 (향후)

Oracle Cloud Always Free(서울), AWS EC2 등으로 이사 시:

```bash
# 1. DB + .env 백업
cp data/mystockbot.db ./mystockbot.db.bak

# 2. VPS로 복사 후
docker compose up -d --build

# 3. Cloudflare Tunnel IP 갱신
```

---

## F. 트러블슈팅

### Docker 실행 안 됨
```bash
docker compose logs mystockbot-api
```
에러 메시지 확인. 주로 .env 파일 누락 또는 KIS API 키 오류.

### Tunnel 연결 안 됨
```bash
cloudflared tunnel info mystockbot
cloudflared tunnel restart mystockbot
```

### 토큰 재생성
```bash
NEW_TOKEN=$(openssl rand -hex 32)
echo "MYSTOCKBOT_API_TOKEN=$NEW_TOKEN" >> .env
docker compose restart mystockbot-api
# 브라우저: TokenBanner에서 새 토큰 입력
```

---

## G. 배포 불가능한 이유: Vercel 백엔드

- **서버리스 제약**: Cold start, 실행시간 제한
- **상시 프로세스 불가**: APScheduler 자동실행 불가
- **SQLite 부적합**: 임시 파일시스템
- **WebSocket 제한**: KIS 실시간 WS 불가능

→ 완전한 서버(로컬 Docker 또는 VPS) 필수.

---

**마지막 갱신**: 2026-07-18
**다음 검토**: A-1~A-6 공개 배포 실제 운영 후
