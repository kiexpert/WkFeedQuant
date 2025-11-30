#!/usr/bin/env bash
set -euo pipefail

# ────────────────────────────────────────────
# 환경변수 (워크플로가 설정함)
# ────────────────────────────────────────────
# GITHUB_TOKEN
# COMMENT_ID
# COMMENT_BODY
# ISSUE_NUMBER
# REPO (owner/repo)
# ────────────────────────────────────────────

BUFFER_FILE=".hq_buffer.log"
> "$BUFFER_FILE"

COMMENT_URL="/repos/${REPO}/issues/comments/${COMMENT_ID}"

# 명령 추출 (앞뒤 공백 제거 후 스페이스를 _로)
COMMAND=$(echo "$COMMENT_BODY" \
  | sed 's/^[ \t]*//;s/[ \t]*$//' \
  | tr ' ' '_' \
  | tr -d '"')

CMD_FILE="cmd_${COMMAND}.py"

# ────────────────────────────────────────────
# 0) 명령 확인
# ────────────────────────────────────────────
if [[ ! -f "$CMD_FILE" ]]; then
  gh api -X PATCH "$COMMENT_URL" \
    -f body="❌ Unknown command: ${COMMAND}
지원되지 않는 명령입니다. 다시 입력해주세요."
  exit 1
fi

# ────────────────────────────────────────────
# 1) 초기 댓글 출력
# ────────────────────────────────────────────
gh api -X PATCH "$COMMENT_URL" \
  -f body="▶ ${COMMENT_BODY} 처리 시작… (Streaming Mode)"

# ────────────────────────────────────────────
# 2) 명령 실행 (stdout을 버퍼로 저장 + 워크플로에도 출력)
# 백그라운드 실행
# ────────────────────────────────────────────
python3 "$CMD_FILE" | tee "$BUFFER_FILE" &
PID=$!

LAST_SIZE=0

# ────────────────────────────────────────────
# 3) 실시간 댓글 업데이트 루프
# ────────────────────────────────────────────
while kill -0 $PID 2>/dev/null; do
  CUR_SIZE=$(stat -c%s "$BUFFER_FILE" 2>/dev/null || echo 0)

  if [ "$CUR_SIZE" -ne "$LAST_SIZE" ]; then
    LAST_SIZE="$CUR_SIZE"
    CONTENT=$(cat "$BUFFER_FILE")
    gh api -X PATCH "$COMMENT_URL" \
      -f body="$CONTENT\n\n(진행 중…)"
  fi

  sleep 1
done

# ────────────────────────────────────────────
# 4) 종료 후 최종 출력 반영
# ────────────────────────────────────────────
CONTENT=$(cat "$BUFFER_FILE")

if wait $PID; then
  gh api -X PATCH "$COMMENT_URL" \
    -f body="$CONTENT\n\n🎯 작업 완료"
else
  gh api -X PATCH "$COMMENT_URL" \
    -f body="$CONTENT\n\n⚠️ 오류 발생 (워크플로 로그 참고)"
fi

exit 0

