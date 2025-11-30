#!/usr/bin/env bash
set -euo pipefail

echo "::group::ENV CHECK"
echo "REPO=${GITHUB_REPOSITORY}"
echo "COMMENT_ID=${COMMENT_ID:-}"
echo "COMMAND=${COMMENT_BODY:-}"
echo "TOKEN_SET=$( [ -n "${GITHUB_TOKEN:-}" ] && echo yes || echo no )"
echo "::endgroup::"

API="https://api.github.com/repos/${GITHUB_REPOSITORY}"
CID="${COMMENT_ID:-}"
CMD="$(echo "${COMMENT_BODY:-}" | tr -d '[:space:]')"

json_escape() {
python3 - << 'EOF'
import json,sys
print(json.dumps(sys.stdin.read())[1:-1])
EOF
}

get_body() {
    curl -sS \
      -H "Authorization: Bearer ${GITHUB_TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      "${API}/issues/comments/${CID}" \
      | python3 -c "import sys,json;print(json.load(sys.stdin).get('body',''))"
}

orig_body="$(get_body || true)"

case "$CMD" in
  "쿡장분석")      python_cmd="kr" ;;
  "미쿡분석")      python_cmd="us" ;;
  "상태")          python_cmd="all" ;;
  *)
      python_cmd=""
      summary="❓ Unsupported Command: ${CMD}"
      ;;
esac

if [ -n "$python_cmd" ]; then
    echo "::group::RUN PYTHON ANALYSIS"
    summary="$(python3 scripts/analyze_market.py "${python_cmd}" 2>&1)" || true
    echo "::endgroup::"
fi

timestamp="$(date -u '+%Y-%m-%d %H:%M:%S UTC')"
append="----------------------------------\n${timestamp}\n\`\`\`\n${summary}\n\`\`\`"
new_body="${orig_body}\n${append}"
escaped="$(printf "%s" "$new_body" | json_escape)"

RESPONSE=$(curl -sS \
  -w "%{http_code}" \
  -o /tmp/resp.txt \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -X PATCH "${API}/issues/comments/${CID}" \
  --data-binary "{\"body\": \"${escaped}\"}"
)

if [ "$RESPONSE" != "200" ]; then
    echo "::error title=PATCH FAILED::HTTP $RESPONSE"
    cat /tmp/resp.txt
else
    echo "::notice title=PATCH SUCCESS::HTTP 200"
fi

echo "::group::RESPONSE RAW"
cat /tmp/resp.txt
echo "::endgroup::"

