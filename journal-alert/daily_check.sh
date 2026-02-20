#!/bin/bash
SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/$(date +%Y%m%d_%H%M%S).log"
YEAR=$(date +%Y)

ENV_FILE="${HOME}/.journal_alert_env"
if [ -f "$ENV_FILE" ]; then
    source "$ENV_FILE"
else
    echo "⚠️  ${ENV_FILE} 없음 — 환경변수 미로드" | tee -a "$LOG_FILE"
fi

export PATH="/opt/homebrew/bin:/usr/local/bin:$PATH"
mkdir -p "$LOG_DIR"

STATUS=""
NEW_COUNT=0

log() {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] $1" | tee -a "$LOG_FILE"
}

log "=== Step 1: 논문 수집 ==="
if python3 "${SCRIPT_DIR}/fetch_papers.py" --all --year "$YEAR" >> "$LOG_FILE" 2>&1; then
    log "✅ 수집 완료"
    STATUS="${STATUS}fetch:ok "
else
    log "❌ 수집 실패 (exit: $?)"
    STATUS="${STATUS}fetch:fail "
fi

log "=== Step 2: Notion push ==="
PUSH_OUTPUT=$(python3 "${SCRIPT_DIR}/push_to_notion.py" --latest 2>&1)
PUSH_EXIT=$?
echo "$PUSH_OUTPUT" >> "$LOG_FILE"

if [ $PUSH_EXIT -eq 0 ]; then
    NEW_COUNT=$(echo "$PUSH_OUTPUT" | grep -o '새로 추가 [0-9]*' | grep -o '[0-9]*' || echo "0")
    log "✅ Push 완료 (신규 ${NEW_COUNT}건)"
    STATUS="${STATUS}push:ok "
elif [ $PUSH_EXIT -eq 2 ]; then
    log "ℹ️  신규 논문 없음"
    STATUS="${STATUS}push:ok(no_new) "
    NEW_COUNT=0
else
    log "❌ Push 실패 (exit: $PUSH_EXIT)"
    STATUS="${STATUS}push:fail "
fi

log "=== Step 3: 이메일 알림 ==="
if [ "$NEW_COUNT" -gt 0 ] 2>/dev/null; then
    if python3 "${SCRIPT_DIR}/notify_email.py" --latest --status "$STATUS" >> "$LOG_FILE" 2>&1; then
        log "✅ 이메일 완료 (신규 ${NEW_COUNT}건 알림)"
    else
        log "❌ 이메일 실패"
    fi
    find "${SCRIPT_DIR}/data" -name "new_*.json" -mtime +7 -delete 2>/dev/null
else
    log "ℹ️  신규 논문 없음 — 이메일 생략"
fi

log "=== Step 4: 빈 Summary 자동 채움 (PubMed abstract 업데이트 반영) ==="
if python3 "${SCRIPT_DIR}/update_existing.py" --fill-summary >> "$LOG_FILE" 2>&1; then
    log "✅ Summary 보완 완료"
    STATUS="${STATUS}summary:ok "
else
    log "⚠️  Summary 보완 일부 실패 (exit: $?)"
    STATUS="${STATUS}summary:partial "
fi

log "=== Step 5: Vol/Issue 보완 (CrossRef + PubMed 재조회) ==="
if python3 "${SCRIPT_DIR}/resolve_vol_issue.py" >> "$LOG_FILE" 2>&1; then
    log "✅ Vol/Issue 보완 완료"
    STATUS="${STATUS}vol_issue:ok "
else
    log "⚠️  Vol/Issue 보완 일부 실패 (exit: $?)"
    STATUS="${STATUS}vol_issue:partial "
fi

find "$LOG_DIR" -name "*.log" -mtime +30 -delete 2>/dev/null

log "=== 완료: ${STATUS}==="
