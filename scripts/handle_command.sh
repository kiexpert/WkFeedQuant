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

# 명령 추출 (앞뒤 공백 제거 후 스페이스를 _로 변환)
COMMAND=$(echo "$COMMENT_BODY" \
  | sed 's/^[ \t]*//;s/[ \t]*$//' \
  | tr ' ' '_' \
  | tr -d '"')

CMD_FILE="scripts/cmd_${COMMAND}.py"

# ────────────────────────────────────────────
# 0) 복명복창: 즉시 사용자에게 확인 메시지
# ────────────────────────────────────────────
gh api -X PATCH "$COMMENT_URL" \
  -f body="🫡 명령 수신: \"${COMMENT_BODY}\"

임무 확인 중…"

# ────────────────────────────────────────────
# 1) 명령 파일 존재 확인
# ────────────────────────────────────────────
if [[ ! -f "$CMD_FILE" ]]; then
  CMDS=$(ls -1 scripts/cmd_*.py \
        | sed 's/^scripts/cmd_//' \
        | sed 's/\.py$//' \
        | tr '_' ' ' \
        | paste -sd ', ' -)

  gh api -X PATCH "$COMMENT_URL" \
    -f body="🫡 명령 수신: \"${COMMENT_BODY}\"

❌ 알 수 없는 명령: ${COMMAND}
사용 가능한 명령: ${CMDS}"
  exit 1
fi

# ────────────────────────────────────────────
# 2) 임무 수행 시작 알림 (즉시)
# ────────────────────────────────────────────
gh api -X PATCH "$COMMENT_URL" \
  -f body="🫡 명령 수신: \"${COMMENT_BODY}\"

▶ 임무 수행 시작… (Streaming Mode)"

# ────────────────────────────────────────────
# 3) 명령 실행 (tee로 버퍼링)
# ────────────────────────────────────────────
python3 "$CMD_FILE" 2>&1 | tee "$BUFFER_FILE" &
PID=$!
LAST_SIZE=0

# ────────────────────────────────────────────
# 4) 실시간 댓글 업데이트 루프
# ────────────────────────────────────────────
while kill -0 $PID 2>/dev/null; do
  CUR_SIZE=$(stat -c%s "$BUFFER_FILE" 2>/dev/null || echo 0)
  if [ "$CUR_SIZE" -ne "$LAST_SIZE" ]; then
    LAST_SIZE="$CUR_SIZE"
    CONTENT=$(cat "$BUFFER_FILE")
    gh api -X PATCH "$COMMENT_URL" \
      -f body="${CONTENT}\n\n⏳ 진행 중…"
  fi
  sleep 1
done

wait $PID
EXIT_CODE=$?

# ────────────────────────────────────────────
# 5) 종료 후 최종 출력 반영
# ────────────────────────────────────────────
CONTENT=$(cat "$BUFFER_FILE")

if [ "$EXIT_CODE" -eq 0 ]; then
  gh api -X PATCH "$COMMENT_URL" \
    -f body="${CONTENT}\n\n🎯 작업 완료"
else
  gh api -X PATCH "$COMMENT_URL" \
    -f body="${CONTENT}\n\n⚠️ 오류 발생 (워크플로 로그 참고)"
fi

exit $EXIT_CODE
