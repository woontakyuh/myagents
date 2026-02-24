#!/bin/bash
set -euo pipefail

SCRIPT_DIR="$(cd "$(dirname "$0")" && pwd)"
LOG_DIR="${SCRIPT_DIR}/logs"
LOG_FILE="${LOG_DIR}/$(date +%Y%m%d_%H%M%S).log"
mkdir -p "$LOG_DIR"

ENV_FILE="${HOME}/.journal_alert_env"
if [ -f "$ENV_FILE" ]; then
  source "$ENV_FILE"
fi

run_url="${SPINOSCOPY_DASHBOARD_JOURNAL_ALERT_URL:-}"
run_token="${SPINOSCOPY_DASHBOARD_JOURNAL_ALERT_TOKEN:-}"
run_days="${SPINOSCOPY_DASHBOARD_JOURNAL_ALERT_DAYS:-7}"

if [ -z "$run_url" ] || [ -z "$run_token" ]; then
  {
    echo "[$(date '+%Y-%m-%d %H:%M:%S')] legacy journal-alert disabled"
    echo "Set SPINOSCOPY_DASHBOARD_JOURNAL_ALERT_URL and SPINOSCOPY_DASHBOARD_JOURNAL_ALERT_TOKEN"
    echo "No local fetch/push/email tasks were executed"
  } | tee -a "$LOG_FILE"
  exit 0
fi

endpoint="${run_url}?days=${run_days}"

{
  echo "[$(date '+%Y-%m-%d %H:%M:%S')] forwarding run to dashboard endpoint"
  echo "POST ${endpoint}"
} | tee -a "$LOG_FILE"

curl -fsS -X POST "$endpoint" \
  -H "Authorization: Bearer ${run_token}" \
  -H "Content-Type: application/json" \
  | tee -a "$LOG_FILE"

echo "" | tee -a "$LOG_FILE"
echo "[$(date '+%Y-%m-%d %H:%M:%S')] completed via dashboard pipeline" | tee -a "$LOG_FILE"
