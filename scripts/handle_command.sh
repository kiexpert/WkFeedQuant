#!/usr/bin/env bash
set -euo pipefail

COMMENT_ID="${COMMENT_ID:-}"
ISSUE_NUMBER="${ISSUE_NUMBER:-1}"
COMMAND="${COMMENT_BODY:-${2:-}}"
GITHUB_TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
REPO="${GITHUB_REPOSITORY:-}"

API="https://api.github.com/repos/${REPO}"

#────────────────────────────────────────────
# 안전 JSON 생성 함수 (줄바꿈/따옴표 보호)
#────────────────────────────────────────────
json_escape() {
    python3 - << 'EOF'
import json,sys
data=sys.stdin.read()
print(json.dumps(data)[1:-1]) # strip quotes
EOF
}

#────────────────────────────────────────────
# 댓글 내용 가져오기
#────────────────────────────────────────────
orig_body=$(curl -sS \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  "${API}/issues/comments/${COMMENT_ID}" \
  | python3 -c "import sys, json; print(json.load(sys.stdin).get('body',''))" \
  || true)

#────────────────────────────────────────────
# 분석 함수
#────────────────────────────────────────────
run_analysis() {
    local market="$1"
    python3 scripts/analyze_market.py "$market" 2>&1 || true
}

cmd=$(echo "$COMMAND" | tr -d '[:space:]')

case "$cmd" in
    "쿡장분석")
        summary="$(run_analysis kr)"
        ;;
    "미쿡분석")
        summary="$(run_analysis us)"
        ;;
    "상태")
        summary="$(run_analysis all)"
        ;;
    *)
        summary="❓ 미확인 명령: ${COMMAND}"
        ;;
esac

divider="----------------------------------"
log_block="${divider}\n\`\`\`\n${summary}\n\`\`\`"

new_body="${orig_body}\n${log_block}"

escaped=$(printf "%s" "$new_body" | json_escape)

#────────────────────────────────────────────
# 명령 댓글 수정(PATCH)
#────────────────────────────────────────────
curl -sS \
  -H "Authorization: Bearer ${GITHUB_TOKEN}" \
  -H "Accept: application/vnd.github+json" \
  -X PATCH "${API}/issues/comments/${COMMENT_ID}" \
  --data-binary "{\"body\": \"${escaped}\"}" \
  >/dev/null
