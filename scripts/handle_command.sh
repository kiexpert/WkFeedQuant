#!/usr/bin/env bash
set -euo pipefail

ISSUE_NUMBER="${1:-1}"
COMMAND="${2:-""}"
GITHUB_TOKEN="${GITHUB_TOKEN:-}"
REPO="${GITHUB_REPOSITORY:-}"

API="https://api.github.com/repos/${REPO}"

#────────────────────────────────────────────
# POST comment helper
#────────────────────────────────────────────
post_comment() {
    local body="$1"
    curl -sS \
      -H "Authorization: Bearer ${GITHUB_TOKEN}" \
      -H "Accept: application/vnd.github+json" \
      -X POST "${API}/issues/${ISSUE_NUMBER}/comments" \
      -d "{\"body\": \"${body}\"}" >/dev/null
}

#────────────────────────────────────────────
# RUN analyzer
#────────────────────────────────────────────
run_analysis() {
    local market="$1"
    python3 scripts/analyze_market.py "$market" 2>&1
}

cmd=$(echo "$COMMAND" | tr -d '[:space:]')

case "$cmd" in
    "쿡장분석") label="KR-Market"; summary="$(run_analysis kr)" ;;
    "미쿡분석") label="US-Market"; summary="$(run_analysis us)" ;;
    "상태")     label="Market-Status"; summary="$(run_analysis all)" ;;
    *)
        label="Unknown"
        summary="❓ 미확인 명령: $COMMAND"
        ;;
esac

# Buttons
BUTTONS=$(
cat <<EOF
➡️ 명령: 쿡장 분석 / 미쿡 분석 / 상태
EOF
)

#────────────────────────────────────────────
# HQ Report
#────────────────────────────────────────────
RESULT=$(cat <<EOF
[HQ] Operation COMPLETE (${label})
▰▰▰▰▰ 100%

\`\`\`
${summary}
\`\`\`

Awaiting next directive, Commander.
${BUTTONS}
EOF
)

#────────────────────────────────────────────
# REPORT BACK TO GITHUB ISSUE
#────────────────────────────────────────────
post_comment "$RESULT"

