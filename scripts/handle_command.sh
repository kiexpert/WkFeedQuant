#!/usr/bin/env bash
set -euo pipefail

trim() { echo "$1" | xargs; }

COMMENT_BODY=$(trim "${COMMENT_BODY:-}")
if [[ -z "$COMMENT_BODY" ]]; then exit 0; fi

REPO="${REPO:-$GITHUB_REPOSITORY}"
COMMENT_ID="${COMMENT_ID:-}"
API="https://api.github.com/repos/$REPO/issues/comments/$COMMENT_ID"
TARGET=""

if [[ "$COMMENT_BODY" == *"쿡장 분석"* ]]; then TARGET="KR"; fi
if [[ "$COMMENT_BODY" == *"미쿡 분석"* ]]; then TARGET="US"; fi
if [[ "$TARGET" == "" ]]; then exit 0; fi

SCREEN=""
SCREEN_LAST=""

append() { SCREEN="${SCREEN}\n$1"; }

escape_json() {
  printf "%s" "$1" | sed 's/"/\\"/g'
}

flush() {
  if [[ "$SCREEN" == "$SCREEN_LAST" ]]; then return; fi
  local msg; msg=$(escape_json "$SCREEN")
  curl -s -X PATCH "$API" \
    -H "Authorization: token $GITHUB_TOKEN" \
    -H "Content-Type: application/json" \
    -d "{\"body\":\"$msg\"}" > /dev/null || true
  SCREEN_LAST="$SCREEN"
}

TS=$(date -u +'%Y-%m-%d %H:%M:%S UTC')
append "$COMMENT_BODY"
append "────────────"
append "$TS"
append "HQ Processing… ($TARGET)"
flush

# Python 분석 실행 → 스트림 파일
python3 scripts/hq_analysis.py "$TARGET" > tmp.log 2>&1 &

PID=$!
SECONDS=0

while kill -0 $PID 2>/dev/null; do
  if [[ -s tmp.log ]]; then
    NEW=$(tail -n 10 tmp.log)
    append "$NEW"
    > tmp.log
    flush
  fi
  sleep 1
done

# 종료 후 마지막 로그 반영
if [[ -s tmp.log ]]; then
  append "$(cat tmp.log)"
  > tmp.log
  flush
fi

append "🎯 ${TARGET} 분석 완료"
append "────────────"
flush

rm -f tmp.log
exit 0
