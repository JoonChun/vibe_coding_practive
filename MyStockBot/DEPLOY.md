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

## 2. Cloudflare Tunnel (무료 HTTPS 고정 URL)

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

## 3. Vercel 프론트엔드 연결

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

## 4. 보안 주의 ⚠️

### 현재 상태
API에 인증 메커니즘 없음. Cloudflare Tunnel로 공개하면 **누구나 watchlist 조작 가능**.

### 권장 방안 (우선순위)
1. **Tailscale (사설망)**: 무료. 본인과 신뢰 사용자만 접근
   - `https://mystockbot.tailnet-abc.ts.net`으로 접근
   - Cloudflare 대신 Tailscale MagicDNS 사용

2. **Cloudflare Access (무료 계층)**: Cloudflare 계정으로 인증
   - Tunnel 설정 시 "Access" 정책 추가

3. **토큰 인증 (추후)**: FastAPI에 Bearer token 추가
   - 프론트/백엔드 모두 토큰 관리 필요

### 임시 조치
현재 개발 단계면 localhost(Tailscale) 또는 IP 화이트리스트 권장.

---

## 5. VPS/서버 이사 (향후)

Oracle Cloud Always Free(서울), AWS EC2 등으로 이사 시:
```bash
# 이 docker-compose.yml을 그대로 사용
docker compose up -d --build
```

- DB 백업: `cp data/mystockbot.db ./mystockbot.db.bak`
- 환경변수 파일(`.env`) 복사 후 비밀값 갱신
- Cloudflare Tunnel 재설정 (IP 변경)

---

## 6. Vercel에 백엔드를 배포할 수 없는 이유

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
