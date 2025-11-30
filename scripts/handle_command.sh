#!/bin/bash
set -e

ts=$(date -u +"%Y-%m-%d %H:%M:%S UTC")
out=""

if echo "${COMMENT_BODY}" | grep -q "미쿡"; then
  out=$(python3 scripts/us_analyze.py 2>&1)
elif echo "${COMMENT_BODY}" | grep -q "쿡장"; then
  out=$(python3 scripts/kr_analyze.py 2>&1)
elif echo "${COMMENT_BODY}" | grep -q "상태"; then
  out=$(python3 scripts/status.py 2>&1)
else
  out="No valid command found."
fi

payload=$(jq -R -s '.' <<< "────────────
${ts}
${out}")

json="{\"body\":${payload} , \"position\":999 }"

curl -s -X PATCH \
  -H "Authorization: token ${GITHUB_TOKEN}" \
  -H "Content-Type: application/json" \
  -d "${json}" \
  "https://api.github.com/repos/${GITHUB_REPOSITORY}/issues/comments/${COMMENT_ID}"

  
