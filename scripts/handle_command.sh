#!/usr/bin/env bash
set -e

COMMENT="$1"
COMMENT_ID="$2"

API="gh api --method PATCH /repos/${GITHUB_REPOSITORY}/issues/comments/${COMMENT_ID} -f body="

update_comment() {
  $API"$1" >/dev/null
}

scan_kr() {
  update_comment "[HQ] Commander Will Kim — Tactical Control Online."
  sleep 1

  update_comment "[HQ] KR-Market Tactical Scan Initiated…\n▰▱▱▱▱ 20%\nData Uplink\n(데이터 링크 확보)"
  sleep 1
  update_comment "[HQ] KR-Market Tactical Scan Initiated…\n▰▰▱▱▱ 40%\nVolume Profile Recon\n(매물대 정찰)"
  sleep 1
  update_comment "[HQ] KR-Market Tactical Scan Initiated…\n▰▰▰▱▱ 60%\nEnergy-Flow Tracking\n(에너지 흐름 추적)"
  sleep 1
  update_comment "[HQ] KR-Market Tactical Scan Initiated…\n▰▰▰▰▱ 80%\nSignal Strength Evaluation\n(신호 강도 평가)"
  sleep 1

  RESULT=$(
    cat <<EOF
[HQ] Operation COMPLETE
▰▰▰▰▰ 100%

Target assets identified:
+ SK하이닉스 → Strong Long
~ 삼성전자 → Hold & Observe
- 카카오 → Risk Zone

Awaiting next directive, Commander.
➡️ [쿡장 분석]
➡️ [미쿡 분석]
➡️ [상태]
EOF
  )
  update_comment "$RESULT"
}

case "$COMMENT" in
  "쿡장 분석")
    scan_kr
    ;;
  "미쿡 분석")
    update_comment "[HQ] US-Market Scan Standing By…"
    ;;
  "상태")
    update_comment "[HQ] Systems Nominal. Awaiting Orders."
    ;;
  *)
    update_comment "❓ Unknown Directive: $COMMENT"
    ;;
esac

