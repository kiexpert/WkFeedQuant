#!/usr/bin/env bash
set -e

COMMENT="$1"
COMMENT_ID="$2"
API="gh api --method PATCH /repos/${GITHUB_REPOSITORY}/issues/comments/${COMMENT_ID} -f body="

update_comment() { $API"$1" >/dev/null; }

scan_market() {
  local market="$1"; local label
  case "$market" in
    kr) label="KR-Market";;
    us) label="US-Market";;
    ix) label="Index-Market";;
    *)  label="Market";;
  esac

  update_comment "[HQ] Commander Will Kim — Tactical Control Online."
  sleep 1
  update_comment "[HQ] ${label} Tactical Scan Initiated…\n▰▱▱▱▱ 20%\nData Uplink\n(데이터 링크 확보)"
  sleep 1
  update_comment "[HQ] ${label} Tactical Scan Initiated…\n▰▰▱▱▱ 40%\nVolume Profile Recon\n(매물대 정찰)"
  sleep 1
  update_comment "[HQ] ${label} Tactical Scan Initiated…\n▰▰▰▱▱ 60%\nEnergy-Flow Tracking\n(에너지 흐름 추적)"
  sleep 1
  update_comment "[HQ] ${label} Tactical Scan Initiated…\n▰▰▰▰▱ 80%\nSignal Strength Evaluation\n(신호 강도 평가)"
  sleep 1

  local summary
  summary="$(python3 scripts/analyze_market.py "$market" 2>/dev/null || echo '')"

  local result
  result=$(cat <<EOF
[HQ] Operation COMPLETE (${label})
▰▰▰▰▰ 100%

${summary}

Awaiting next directive, Commander.
➡️ [쿡장 분석] ➡️ [미쿡 분석] ➡️ [상태]
EOF
)
  update_comment "$result"
}

case "$COMMENT" in
  "쿡장 분석")
    scan_market "kr"
    ;;
  "미쿡 분석")
    scan_market "us"
    ;;
  "상태")
    update_comment "[HQ] Systems Nominal. Awaiting Orders.\n(캐시: cache/all_kr_15m.json, cache/all_us_15m.json, cache/all_ix_15m.json)"
    ;;
  *)
    update_comment "❓ Unknown Directive: $COMMENT"
    ;;
esac

