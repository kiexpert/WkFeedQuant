#!/usr/bin/env bash

COMMENT="$1"
COMMENT_ID="$2"

API="gh api --method PATCH /repos/${GITHUB_REPOSITORY}/issues/comments/${COMMENT_ID} -f body="

update_comment() {
  $API"$1" >/dev/null
}

if [[ "$COMMENT" == "쿡장 분석" ]]; then

  update_comment "[HQ] Commander Will Kim — Tactical Control Online."
  sleep 1
  update_comment "[HQ] KR-Market Tactical Scan Initiated…"
  sleep 1
  update_comment "[HQ] Phase 1/4 — Data Uplink Secured\nProgress: ▰▱▱▱▱ 20%"
  sleep 1
  update_comment "[HQ] Phase 2/4 — Volume Profile Recon\nProgress: ▰▰▱▱▱ 40%"
  sleep 1
  update_comment "[HQ] Phase 3/4 — Energy Flow Tracking\nProgress: ▰▰▰▱▱ 60%"
  sleep 1
  update_comment "[HQ] Phase 4/4 — Signal Strength Evaluation\nProgress: ▰▰▰▰▱ 80%"
  sleep 1

  RESULT=$(
    cat <<EOF
[HQ] Operation COMPLETE
Target assets identified:
+ SK하이닉스 → Strong Long
~ 삼성전자 → Hold & Observe
- 카카오 → Risk Zone

Awaiting next command, Commander.
[쿡장 분석] [미쿡 분석] [상태]
EOF
  )
  update_comment "$RESULT"

elif [[ "$COMMENT" == "미쿡 분석" ]]; then
  update_comment "[HQ] US-Market Scan Standing By…"

elif [[ "$COMMENT" == "상태" ]]; then
  update_comment "[HQ] Systems Nominal. Awaiting Orders."
else
  update_comment "❓ Unknown Directive: $COMMENT"
fi
