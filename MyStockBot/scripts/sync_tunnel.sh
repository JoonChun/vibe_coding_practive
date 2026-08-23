#!/bin/bash
# sync_tunnel.sh — Cloudflare quick tunnel을 자동 감지·관리하고 Vercel 프로덕션과 동기화
# 요구사항: cloudflared, vercel, curl, nslookup(또는 getent), ss

set -euo pipefail

###############################################################################
# 설정
###############################################################################
PROJECT_ROOT="/home/joon/vibe_ws/MyStockBot"
LOG_FILE="${PROJECT_ROOT}/data/cloudflared.log"
WEB_DIR="${PROJECT_ROOT}/web"
TUNNEL_METRICS_PORTS="20241 20242 20243 20244 20245 20246 20247 20248 20249 20250"
TUNNEL_TIMEOUT=30        # hostname 획득 대기 (메트릭 서버 기동)
PROPAGATION_TIMEOUT=180  # 신규 터널 공개 도달 대기 — DNS·엣지 전파에 수십 초~수 분 걸림(실측)
VERCEL_PRODUCTION_URL="https://mystockbot.vercel.app"

DRY_RUN=false

###############################################################################
# 유틸리티 함수
###############################################################################

log() {
    local level="$1"
    shift
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] [$level] $*" >&2
}

die() {
    log ERROR "$*"
    exit 1
}

check_dependencies() {
    local missing=()

    for cmd in cloudflared vercel curl nslookup ss; do
        if ! command -v "$cmd" &>/dev/null; then
            missing+=("$cmd")
        fi
    done

    if [ ${#missing[@]} -gt 0 ]; then
        die "필요한 명령을 찾을 수 없음: ${missing[*]}"
    fi
}

###############################################################################
# 터널 탐지 및 검증
###############################################################################

# 주어진 메트릭 포트에서 hostname 을 얻는다. 응답 없음/빈 hostname 은 실패(1) 처리
# — 빈 문자열을 성공으로 흘리면 호출부가 유령 터널을 발견한 것으로 오판한다.
get_hostname_from_metrics_port() {
    local port="$1"
    local response hostname
    response=$(curl -s --max-time 2 "http://127.0.0.1:${port}/quicktunnel" 2>/dev/null) || return 1
    hostname=$(echo "$response" | grep -o '"hostname":"[^"]*"' | cut -d'"' -f4)
    [ -n "$hostname" ] || return 1
    echo "$hostname"
}

# hostname이 DNS 해석 가능한지 확인
is_hostname_resolvable() {
    local hostname="$1"
    nslookup "$hostname" &>/dev/null
}

# hostname의 health 엔드포인트가 살아있는지 확인
# 본문 유무가 아니라 HTTP 200 을 요구한다 — Cloudflare 530 에러 페이지(본문 있음)를
# healthy 로 오판하면 죽은 터널로 동기화해버린다.
is_tunnel_healthy() {
    local hostname="$1"
    local status
    status=$(curl -s -o /dev/null -w '%{http_code}' --max-time 5 "https://${hostname}/api/health" 2>/dev/null) || return 1
    [ "$status" = "200" ]
}

# 살아있는 터널 찾기
find_active_tunnel() {
    log INFO "활성 터널 탐지 중..."

    for port in $TUNNEL_METRICS_PORTS; do
        local hostname
        if hostname=$(get_hostname_from_metrics_port "$port"); then
            log DEBUG "포트 $port에서 hostname 발견: $hostname"

            if is_hostname_resolvable "$hostname"; then
                log DEBUG "hostname $hostname은 DNS 해석 가능"

                if is_tunnel_healthy "$hostname"; then
                    log INFO "활성 터널 발견: $hostname (메트릭 포트: $port)"
                    echo "$hostname"
                    return 0
                else
                    log DEBUG "hostname $hostname의 health 체크 실패 (좀비 터널)"
                fi
            else
                log DEBUG "hostname $hostname은 DNS 해석 불가 (좀비 터널)"
                # 죽은 터널 정리
                cleanup_zombie_tunnel "$port"
            fi
        fi
    done

    log INFO "활성 터널을 찾을 수 없음"
    return 1
}

# 죽은 터널 정리
cleanup_zombie_tunnel() {
    local metrics_port="$1"

    # DRY_RUN 모드에서는 실행하지 않음
    if [ "$DRY_RUN" = true ]; then
        log INFO "[DRY RUN] 좀비 터널 정리 생략 (메트릭 포트: $metrics_port)"
        return 0
    fi

    log INFO "좀비 터널 정리 중 (메트릭 포트: $metrics_port)..."

    # ss를 사용해 메트릭 포트를 바인드한 PID 찾기
    local pid
    if pid=$(ss -tlnp 2>/dev/null | grep ":${metrics_port}" | grep -o 'pid=[0-9]*' | cut -d'=' -f2 | head -1); then
        if [ -n "$pid" ] && kill -0 "$pid" 2>/dev/null; then
            log INFO "PID $pid 종료 중..."
            kill "$pid" || true
            sleep 1
            # SIGKILL이 필요하면 시도
            kill -9 "$pid" 2>/dev/null || true
            log INFO "좀비 프로세스 정리 완료"
        fi
    fi
}

###############################################################################
# 터널 기동
###############################################################################

start_new_tunnel() {
    # DRY_RUN 모드에서는 실제 기동하지 않음
    if [ "$DRY_RUN" = true ]; then
        log INFO "[DRY RUN] 새로운 cloudflared tunnel 기동이 필요합니다 (실제 기동 없음)"
        return 1
    fi

    log INFO "새로운 cloudflared tunnel 기동 중..."

    # 로그 디렉토리 생성
    mkdir -p "$(dirname "$LOG_FILE")"

    # 사용 가능한 첫 번째 메트릭 포트 찾기 (set -u 대비 빈 값으로 초기화)
    local metrics_port=""
    for port in $TUNNEL_METRICS_PORTS; do
        if ! curl -s --max-time 1 "http://127.0.0.1:${port}/quicktunnel" &>/dev/null; then
            metrics_port="$port"
            break
        fi
    done

    if [ -z "$metrics_port" ]; then
        die "사용 가능한 메트릭 포트를 찾을 수 없음"
    fi

    log INFO "메트릭 포트로 $metrics_port 사용"

    # cloudflared 기동
    nohup cloudflared tunnel --url http://localhost:8000 --no-autoupdate --metrics "127.0.0.1:${metrics_port}" >"$LOG_FILE" 2>&1 &
    local pid=$!
    log INFO "cloudflared PID: $pid (로그: $LOG_FILE)"

    # 1단계: hostname 획득 (메트릭 서버 기동 대기)
    # ((elapsed++)) 는 값이 0일 때 상태 1을 반환해 set -e 로 즉사한다 — SECONDS 사용
    local hostname=""
    local start_ts=$SECONDS
    while [ $((SECONDS - start_ts)) -lt $TUNNEL_TIMEOUT ]; do
        if hostname=$(get_hostname_from_metrics_port "$metrics_port"); then
            log INFO "tunnel hostname 획득: $hostname"
            break
        fi
        sleep 1
    done
    [ -n "$hostname" ] || die "hostname 획득 실패 (${TUNNEL_TIMEOUT}초 타임아웃) — 로그 확인: $LOG_FILE"

    # 2단계: 공개 도달 대기 — 갓 만든 quick tunnel 은 DNS·엣지 전파 전까지
    # 외부에서 NXDOMAIN/530 이 뜬다 (30초로는 부족함이 실측으로 확인됨).
    log INFO "터널 전파 대기 중 (최대 ${PROPAGATION_TIMEOUT}초)..."
    start_ts=$SECONDS
    while [ $((SECONDS - start_ts)) -lt $PROPAGATION_TIMEOUT ]; do
        if is_tunnel_healthy "$hostname"; then
            log INFO "tunnel health 체크 완료 ($((SECONDS - start_ts))초 경과)"
            echo "$hostname"
            return 0
        fi
        sleep 5
    done

    die "터널이 ${PROPAGATION_TIMEOUT}초 내에 공개 도달 가능해지지 않음 — 백엔드(localhost:8000) 기동 여부와 $LOG_FILE 을 확인하시오"
}

###############################################################################
# Vercel 배포 번들에서 URL 추출
###############################################################################

get_deployed_tunnel_url() {
    log INFO "Vercel 프로덕션 번들에서 tunnel URL 추출 중..."

    # index.html에서 assets 번들 파일 찾기
    local bundle_path
    bundle_path=$(curl -s "$VERCEL_PRODUCTION_URL/index.html" 2>/dev/null | grep -o 'assets/index-[^"]*\.js' | head -1)

    if [ -z "$bundle_path" ]; then
        log WARN "번들 파일을 찾을 수 없음"
        return 1
    fi

    log DEBUG "번들 파일: $bundle_path"

    # 번들에서 trycloudflare URL 패턴 추출
    local deployed_url
    deployed_url=$(curl -s "$VERCEL_PRODUCTION_URL/${bundle_path}" 2>/dev/null | grep -o 'https://[a-z0-9\-]*\.trycloudflare\.com' | head -1)

    if [ -z "$deployed_url" ]; then
        log WARN "번들에서 trycloudflare URL을 찾을 수 없음"
        return 1
    fi

    echo "$deployed_url"
    return 0
}

###############################################################################
# Vercel 환경변수 동기화
###############################################################################

sync_vercel_env() {
    local new_url="$1"

    log INFO "Vercel 환경변수 동기화 중..."
    log INFO "새로운 API URL: $new_url"

    if [ "$DRY_RUN" = true ]; then
        log INFO "[DRY RUN] vercel env rm VITE_API_BASE production --yes"
        log INFO "[DRY RUN] printf '%s' \"$new_url\" | vercel env add VITE_API_BASE production --sensitive"
        log INFO "[DRY RUN] vercel redeploy $VERCEL_PRODUCTION_URL"
        return 0
    fi

    # web 디렉토리로 이동
    cd "$WEB_DIR" || die "web 디렉토리로 이동 실패"

    # VITE_API_BASE 제거 (이전 버전 정리)
    log DEBUG "이전 VITE_API_BASE 환경변수 제거 중..."
    vercel env rm VITE_API_BASE production --yes || log WARN "환경변수 제거 실패 (이미 없을 수 있음)"

    # VITE_API_BASE 추가 (새 URL 설정)
    log DEBUG "VITE_API_BASE 환경변수 추가 중..."
    printf '%s' "$new_url" | vercel env add VITE_API_BASE production --sensitive || die "환경변수 추가 실패"

    # 배포
    log DEBUG "vercel redeploy 실행 중..."
    vercel redeploy "$VERCEL_PRODUCTION_URL" --target production || die "vercel redeploy 실패"

    log INFO "Vercel 배포 완료"
}

###############################################################################
# 최종 검증
###############################################################################

verify_deployment() {
    local expected_url="$1"

    log INFO "배포 검증 중..."

    if [ "$DRY_RUN" = true ]; then
        log INFO "[DRY RUN] 배포 검증 생략"
        return 0
    fi

    # 배포 후 약간의 지연 (Vercel CDN 캐시 새로고침 대기)
    sleep 5

    local deployed_url
    if ! deployed_url=$(get_deployed_tunnel_url); then
        die "배포된 URL 추출 실패"
    fi

    if [ "$deployed_url" = "$expected_url" ]; then
        log INFO "검증 성공: $deployed_url"
        return 0
    else
        die "검증 실패: 배포된 URL($deployed_url) ≠ 예상 URL($expected_url)"
    fi
}

###############################################################################
# 메인 로직
###############################################################################

main() {
    # 플래그 파싱
    if [ "${1:-}" = "--dry-run" ]; then
        DRY_RUN=true
        log INFO "드라이런 모드 활성화"
    fi

    check_dependencies

    log INFO "=== Cloudflare quick tunnel 동기화 시작 ==="

    # 활성 터널 찾기 또는 새로 기동
    local tunnel_url
    if ! tunnel_url=$(find_active_tunnel); then
        if [ "$DRY_RUN" = true ]; then
            log WARN "[DRY RUN] 활성 터널이 없습니다 (새 터널 기동은 DRY RUN 모드에서 불가능)"
            log INFO "=== 드라이런 완료 ==="
            return 0
        fi
        tunnel_url=$(start_new_tunnel)
    fi

    log INFO "현재 터널: $tunnel_url"

    # Vercel에 배포된 URL 확인
    local deployed_url
    if ! deployed_url=$(get_deployed_tunnel_url); then
        log WARN "배포된 URL을 확인할 수 없음, 강제 재배포"
        deployed_url=""
    fi

    # URL 비교
    if [ "$deployed_url" = "https://${tunnel_url}" ]; then
        log INFO "이미 동기화됨: $deployed_url"
        log INFO "=== 터널 동기화 완료 (재배포 없음) ==="
        return 0
    fi

    log INFO "동기화 필요: 배포된 URL이 현재 터널과 다름"
    if [ -n "$deployed_url" ]; then
        log INFO "  배포됨: $deployed_url"
    fi
    log INFO "  현재:   https://${tunnel_url}"

    if [ "$DRY_RUN" = true ]; then
        log INFO "[DRY RUN] Vercel 재배포가 필요합니다"
        log INFO "=== 드라이런 완료 ==="
        return 0
    fi

    # Vercel 동기화
    sync_vercel_env "https://${tunnel_url}"

    # 최종 검증
    verify_deployment "https://${tunnel_url}"

    log INFO "=== 터널 동기화 완료 ==="
}

###############################################################################

main "$@"
