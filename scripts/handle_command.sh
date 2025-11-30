#!/usr/bin/env bash
set -euo pipefail

BUFFER_FILE="stream_buffer.log"
> "$BUFFER_FILE"

# 환경변수
COMMENT=$(echo "$COMMENT_BODY" | sed 's/^[ \t]*//;s/[ \t]*$//')
COMMAND_ID=$(echo "$COMMENT" | tr ' ' '_' | tr -d '"')
CMD_FILE="scripts/cmd_${COMMAND_ID}.py"

# 복명복창 즉시 댓글 새로 생성
RESP=$(gh api -X POST "/repos/${REPO}/issues/${ISSUE_NUMBER}/comments" \
  -f body="🫡 명령 수신: \"${COMMENT_BODY}\"\n준비 중…")
COMMENT_ID_NEW=$(echo "$RESP" | jq -r '.id')
COMMENT_URL="/repos/${REPO}/issues/comments/${COMMENT_ID_NEW}"

# 명령 존재 확인
if [[ ! -f "$CMD_FILE" ]]; then
  CMDS=$(ls scripts/cmd_*.py 2>/dev/null \
    | sed 's#scripts/cmd_##' | sed 's/.py$//' \
    | tr '_' ' ' | paste -sd ', ' -)

  gh api -X PATCH "$COMMENT_URL" \
    -f body="❌ 알 수 없는 명령\n\n사용 가능: ${CMDS}"
  exit 1
fi

# 파이썬 실행 + 버퍼 저장
python3 "$CMD_FILE" | tee "$BUFFER_FILE" &
PID=$!

LAST=""
while kill -0 $PID 2>/dev/null; do
  CUR=$(cat "$BUFFER_FILE" 2>/dev/null || echo "")

  if [[ "$CUR" != "$LAST" ]]; then
    LAST="$CUR"
    gh api -X PATCH "$COMMENT_URL" \
      -f body="${CUR}\n\n(🛰️ 스트리밍 중)"
  fi
  sleep 1
done

# 종료 반영
if wait $PID; then
  gh api -X PATCH "$COMMENT_URL" \
    -f body="$(cat "$BUFFER_FILE")\n\n🎯 임무 완료"
else
  gh api -X PATCH "$COMMENT_URL" \
    -f body="$(cat "$BUFFER_FILE")\n\n⚠️ 실행 오류 발생"
fi

