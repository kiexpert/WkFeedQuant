#!/usr/bin/env bash
set -euo pipefail

# ──────────────────────────────────────
# 환경 변수 확인
# ──────────────────────────────────────
if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN missing"
  exit 1
fi

REPO="${REPO:-$GITHUB_REPOSITORY}"
COMMENT_ID="${COMMENT_ID:-}"
COMMENT_BODY="${COMMENT_BODY:-}"
ISSUE_NUMBER="${ISSUE_NUMBER:-}"

API="https://api.github.com/repos/$REPO/issues/comments/$COMMENT_ID"

# ──────────────────────────────────────
# 화면 버퍼 (전체 댓글 내용 유지)
# ──────────────────────────────────────
SCREEN=""
SCREEN_LAST=""

append() {
  SCREEN="${SCREEN}\n$1"
}

json_escape() {
  printf "%s" "$1" | sed 's/"/\\"/g'
}

flush() {
  if [[ "$SCREEN" == "$SCREEN_LAST" ]]; then return; fi
  local bodyEscaped
  bodyEscaped=$(json_escape "$SCREEN")

  curl -s -X PATCH "$API" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"body\":\"${bodyEscaped}\"}" \
    > /dev/null

  SCREEN_LAST="$SCREEN"
}

# 초기 메시지
TS=$(date -u +'%Y-%m-%d %H:%M:%S UTC')
append "$COMMENT_BODY"
append "────────────"
append "$TS"
append "HQ Received and processing..."
flush

# ──────────────────────────────────────
# 실행 작업
# ──────────────────────────────────────
if [[ "$COMMENT_BODY" == *"쿡장 분석"* ]]; then
  TARGET="KR"
elif [[ "$COMMENT_BODY" == *"미쿡 분석"* ]]; then
  TARGET="US"
else
  append "⚠️ Unknown command"
  flush
  exit 0
fi

append "▶ ${TARGET} Analysis Started..."
flush

# Python 실행 + 스트림 캡처
python3 <<EOF | while read -r line; do
import time
for i in range(1, 8):
    print(f"Processing item {i}/7 ...")
    time.sleep(0.4)
EOF
do
  append "$line"
  flush
done

# 완료 메시지
append "🎯 ${TARGET} Analysis Complete"
append "────────────"
flush

exit 0
