#!/bin/bash
set -euo pipefail

ts=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
out=""

if echo "${COMMENT_BODY}" | grep -q "미쿡"; then
  out=$(python3 scripts/us_analyze.py 2>&1)
elif echo "${COMMENT_BODY}" | grep -q "쿡장"; then
  out=$(python3 scripts/kr_analyze.py 2>&1)
elif echo "${COMMENT_BODY}" | grep -q "상태"; then
  out=$(python3 scripts/status.py 2>&1)
else
  out="⚠️ 지원되지 않는 명령"
fi

# 🔥 기존 댓글 Body 확보
orig=$(curl -s -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  "https://api.github.com/repos/${GITHUB_REPOSITORY}/issues/comments/${COMMENT_ID}" \
  | jq -r '.body')

# 🔥 아래쪽에 누적 Append
new="${orig}\n\n────────────\n${ts}\n${out}"

json=$(jq -Rn --arg body "$new" '{"body": $body}')

# 댓글 업데이트 (Append 결과 반영)
curl -s -X PATCH \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "${json}" \
  "https://api.github.com/repos/${GITHUB_REPOSITORY}/issues/comments/${COMMENT_ID}"
