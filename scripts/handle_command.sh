#!/usr/bin/env bash
set -euo pipefail

ISSUE_NUMBER="${1:-${ISSUE_NUMBER:-1}}"
COMMAND="${2:-${COMMENT_BODY:-}}"
GITHUB_TOKEN="${GITHUB_TOKEN:-${GH_TOKEN:-}}"
REPO="${GITHUB_REPOSITORY:-}"

API="https://api.github.com/repos/${REPO}"

post_comment() {
    local body="$1"
    export BODY="$body"
    local json
    json=$(python3 - << 'EOF'
import os, json
body = os.environ.get("BODY","")
if len(body) > 60000:
    body = body[:60000] + "\n...[truncated]..."
print(json.dumps({"body": body}))
EOF
)
    curl -sS \
      -H "Authorization: Bearer ${GITHUB_TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      -X POST "${API}/issues/${ISSUE_NUMBER}/comments" \
      --data-binary "$json" >/dev/null
}

run_analysis() {
    local market="$1"
    python3 scripts/analyze_market.py "$market" 2>&1 || true
}

cmd="$(echo "${COMMAND}" | tr -d '[:space:]')"

case "$cmd" in
    "쿡장분석")
        label="KR-Market"
        summary="$(run_analysis kr)"
        ;;
    "미쿡분석")
        label="US-Market"
        summary="$(run_analysis us)"
        ;;
    "상태")
        label="Market-Status"
        summary="$(run_analysis all)"
        ;;
    *)
        label="Unknown"
        summary="❓ 미확인 명령: ${COMMAND}"
        ;;
esac

encode() {
    python3 - <<EOF
import urllib.parse, sys
print(urllib.parse.quote(sys.argv[1]))
EOF
}

BTN_KR="$(encode "쿡장 분석")"
BTN_US="$(encode "미쿡 분석")"
BTN_ST="$(encode "상태")"

buttons=$(cat <<EOF
➡️ [쿡장 분석](https://github.com/${REPO}/issues/${ISSUE_NUMBER}/new?body=${BTN_KR})
➡️ [미쿡 분석](https://github.com/${REPO}/issues/${ISSUE_NUMBER}/new?body=${BTN_US})
➡️ [상태](https://github.com/${REPO}/issues/${ISSUE_NUMBER}/new?body=${BTN_ST})
EOF
)

result=$(cat <<EOF
[HQ] Operation COMPLETE (${label})
▰▰▰▰▰ 100%

\`\`\`
${summary}
\`\`\`

Awaiting next directive, Commander.
${buttons}
EOF
)

post_comment "$result"

