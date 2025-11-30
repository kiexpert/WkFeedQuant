#!/usr/bin/env bash
set -u  # -e 제거 (에러도 보고 댓글 달기 위해)

COMMENT_BODY="${COMMENT_BODY:-}"
COMMENT_ID="${COMMENT_ID:-}"
ISSUE_NUMBER="${ISSUE_NUMBER:-}"
REPO="${REPO:-}"
RUN_URL="${RUN_URL:-}"

# GitHub API 댓글 함수(공통)
post_comment() {
    local message="$1"
    echo "💬 댓글 등록: $message"
    gh api \
      --method POST \
      "/repos/${REPO}/issues/${ISSUE_NUMBER}/comments" \
      -f body="$message" >/dev/null 2>&1 || \
      echo "⚠️ 댓글 전송 실패"
}

post_reply() {
    local message="$1"
    if [[ -z "$COMMENT_ID" ]]; then
        post_comment "$message"
        return
    fi
    echo "↩️ 답글 등록: $message"
    gh api \
      --method POST \
      "/repos/${REPO}/issues/comments/${COMMENT_ID}/replies" \
      -f body="$message" >/dev/null 2>&1 || \
      post_comment "$message"
}

ack() {
    local msg="$1"
    echo "🫡 명령 수신: \"$msg\""
    post_reply "🫡 명령 수신: \"$msg\"\n임무 확인 중…"
}

# 실패 표시 파일
rm -f .hq_failed

ack "$COMMENT_BODY"

handle_analyze() {
    local target="$1"
    local script="scripts/cmd_${target}.py"

    if [[ ! -f "$script" ]]; then
        post_reply "❌ 잘못된 명령 또는 미지원 대상: $target"
        echo "script not found: $script"
        echo "fail" > .hq_failed
        return
    fi

    # 실행
    local TMP_OUT
    TMP_OUT=$(mktemp)

    echo "▶ ${target} 분석 시작"
    if python "$script" >"$TMP_OUT" 2>&1; then
        post_comment "$(cat "$TMP_OUT")"$'\n\n'"🎯 임무 완료"
        echo "SUCCESS"
    else
        post_reply "🚨 분석 실패: 로그를 확인해 주세요.\n\n$(sed 's/^/> /' "$TMP_OUT")"
        echo "fail" > .hq_failed
    fi
    rm -f "$TMP_OUT"
}

case "$COMMENT_BODY" in
    *"미쿡 분석"*)
        handle_analyze "us"
        ;;
    *"국장 분석"*)
        handle_analyze "kr"
        ;;
    *)
        post_reply "❓ 인식 불가: \"$COMMENT_BODY\"\n지원 명령: 미쿡 분석 / 국장 분석"
        echo "fail" > .hq_failed
        ;;
esac
