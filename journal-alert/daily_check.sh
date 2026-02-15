#!/bin/bash
# ─── Journal Alert 자동 실행 스크립트 ────────────────────
# 매일 아침 cron으로 실행: 논문 수집 → Notion push → 이메일 알림
# Usage: ./daily_check.sh

# ─── 환경 설정 ──────────────────────────────────────────
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/$(date +%Y%m%d_%H%M%S).log"
YEAR=$(date +%Y)

# 환경변수 로드
ENV_FILE="${HOME}/.journal_alert_env"
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    echo "⚠️  ${ENV_FILE} 없음 — 환경변수 미로드" | tee -a "$LOG_FILE"
fi

# PATH 설정 (cron에서 python3 찾기 위해)
export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"

# 로그 디렉토리 생성
mkdir -p "$LOG_DIR"

# ─── 상태 추적 ──────────────────────────────────────────
STATUS=""

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

# ─── Step 1: 논문 수집 ─────────────────────────────────
log "=== Step 1: 논문 수집 ==="
if python3 "${SCRIPT_DIR}/fetch_papers.py" --all --year "$YEAR" >> "$LOG_FILE" 2>&1; then
    log "✅ 수집 완료"
    STATUS="${STATUS}fetch:ok "
else
    log "❌ 수집 실패 (exit: $?)"
    STATUS="${STATUS}fetch:fail "
fi

# ─── Step 2: Notion push ──────────────────────────────
log "=== Step 2: Notion push ==="
if python3 "${SCRIPT_DIR}/push_to_notion.py" --latest >> "$LOG_FILE" 2>&1; then
    log "✅ Push 완료"
    STATUS="${STATUS}push:ok "
else
    log "❌ Push 실패 (exit: $?)"
    STATUS="${STATUS}push:fail "
fi

# ─── Step 3: 이메일 알림 ──────────────────────────────
log "=== Step 3: 이메일 알림 ==="
if python3 "${SCRIPT_DIR}/notify_email.py" --latest --status "$STATUS" >> "$LOG_FILE" 2>&1; then
    log "✅ 이메일 완료"
else
    log "❌ 이메일 실패"
fi

# ─── 오래된 로그 정리 (30일) ──────────────────────────
find "$LOG_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null

log "=== 완료: ${STATUS}==="
