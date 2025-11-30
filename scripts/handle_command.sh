#!/usr/bin/env bash
set -euo pipefail

#────────────────────────────────────────────
# 환경 변수(GitHub Actions가 자동 주입)
#────────────────────────────────────────────
ISSUE_NUMBER="$1"  # 입력받은 Issue 번호
COMMAND="$2"       # 댓글 내용(명령)
GITHUB_TOKEN="$GITHUB_TOKEN"
REPO="$GITHUB_REPOSITORY"

API="https://api.github.com/repos/${REPO}"

#────────────────────────────────────────────
# GitHub 댓글 업데이트 함수
#────────────────────────────────────────────
update_comment() {
    local body="$1"
    # comment 제거 없이 'HQ' 라벨 댓글만 갱신
    COMMENT_ID=$(gh api "${API}/issues/${ISSUE_NUMBER}/comments" \
        --jq 'map(select(.body | contains("[HQ]")))[0].id' || true)

    if [[ -n "${COMMENT_ID}" && "${COMMENT_ID}" != "null" ]]; then
        gh api \
            --method PATCH \
            -H "Content-Type: application/json" \
            -X PATCH "${API}/issues/comments/${COMMENT_ID}" \
            -f body="$body" >/dev/null
    else
        gh api \
            --method POST \
            -H "Content-Type: application/json" \
            -X POST "${API}/issues/${ISSUE_NUMBER}/comments" \
            -f body="$body" >/dev/null
    fi
}

#────────────────────────────────────────────
# 분석 실행기 (Python 호출)
#────────────────────────────────────────────

analyze_market() {
    local market="$1"
    python3 scripts/analyze_market.py "$market"
}

#────────────────────────────────────────────
# 명령 분기 처리
# COMMAND의 공백 제거해서 매칭
#────────────────────────────────────────────
cmd=$(echo "$COMMAND" | tr -d '[:space:]')

case "$cmd" in
    "쿡장분석")
        label="KR-Market"
        summary="$(analyze_market kr)"
        ;;
    "미쿡분석")
        label="US-Market"
        summary="$(analyze_market us)"
        ;;
    "상태")
        label="Market-Status"
        summary="$(analyze_market all)"
        ;;
    *)
        label="Unknown"
        summary="❓ 미확인 명령: $COMMAND"
        ;;
esac

#────────────────────────────────────────────
# 액션 버튼 (댓글 POST 링크)
#────────────────────────────────────────────
BUTTONS=$(cat <<EOF
➡️ [쿡장 분석](https://github.com/${REPO}/issues/${ISSUE_NUMBER}#issuecomment-new)
➡️ [미쿡 분석](https://github.com/${REPO}/issues/${ISSUE_NUMBER}#issuecomment-new)
➡️ [상태](https://github.com/${REPO}/issues/${ISSUE_NUMBER}#issuecomment-new)
EOF
)

#────────────────────────────────────────────
# HQ 출력 생성
#────────────────────────────────────────────
RESULT=$(cat <<EOF
[HQ] Operation COMPLETE (${label})
▰▰▰▰▰ 100%

${summary}

Awaiting next directive, Commander.
${BUTTONS}
EOF
)

#────────────────────────────────────────────
# 댓글 갱신(또는 생성)
#────────────────────────────────────────────
update_comment "$RESULT"
