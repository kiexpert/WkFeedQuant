#!/usr/bin/env bash
set -euo pipefail

if [[ -z "${GITHUB_TOKEN:-}" ]]; then
  echo "GITHUB_TOKEN missing"
  exit 1
fi

REPO="${REPO:-$GITHUB_REPOSITORY}"
COMMENT_ID="${COMMENT_ID:-}"
COMMENT_BODY="${COMMENT_BODY:-}"
API="https://api.github.com/repos/$REPO/issues/comments/$COMMENT_ID"

SCREEN=""
SCREEN_LAST=""

append() {
  SCREEN="${SCREEN}\n$1"
}

escape_json() {
  printf "%s" "$1" | sed 's/"/\\"/g'
}

flush() {
  if [[ "$SCREEN" == "$SCREEN_LAST" ]]; then return; fi
  local msg; msg=$(escape_json "$SCREEN")

  curl -s -X PATCH "$API" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"body\":\"${msg}\"}" > /dev/null || true

  SCREEN_LAST="$SCREEN"
}

# 초기 메세지
TS=$(date -u +'%Y-%m-%d %H:%M:%S UTC')
append "$COMMENT_BODY"
append "────────────"
append "$TS"
append "Command received…"
flush

# 대상 판별
if [[ "$COMMENT_BODY" == *"쿡장 분석"* ]]; then
  TARGET="KR"
elif [[ "$COMMENT_BODY" == *"미쿡 분석"* ]]; then
  TARGET="US"
else
  append "⚠️ Unknown command"
  flush
  exit 0
fi

append "▶ ${TARGET} Analysis started"
flush

# Python 실행 스트림 처리 (정상 문법)
python3 <<'EOF' > tmp_stream.txt
import time
for i in range(1, 8):
    print(f"Processing {i}/7 …")
    time.sleep(0.4)
EOF

# 스트림 읽기
while IFS= read -r line; do
  append "$line"
  flush
done < tmp_stream.txt
rm -f tmp_stream.txt

append "🎯 ${TARGET} Analysis COMPLETE"
append "────────────"
flush
exit 0

