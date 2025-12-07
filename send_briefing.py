#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, re
from telegram_notify import send_text, send_voice

BRIEF = "briefing.txt"

# ----------------------------------------------------------
# ① 음성용 초요약 생성기 (현재 시간 포함, KST 기준)
# ----------------------------------------------------------
def make_voice_summary(full_text: str) -> str:
    from datetime import datetime, timedelta

    # KST 시간 계산
    now_utc = datetime.utcnow()
    now_kst = now_utc + timedelta(hours = 9)
    tstr = now_kst.strftime("%Y-%m-%d %H시 %M분")

    lines = full_text.splitlines()
    top15 = None
    top1d_in = None
    top1d_out = None
    leader = None

    for line in lines:
        s = line.strip()
        if not s:
            continue
        sector = s.split()[0]

        if ("Δ15m:+" in line) and (top15 is None):
            top15 = sector
        if ("Δ1d:+" in line) and (top1d_in is None):
            top1d_in = sector
        if ("Δ1d:-" in line) and (top1d_out is None):
            top1d_out = sector
        if ("energy=" in line) and (leader is None):
            leader = s.split()[0]

    top15 = top15 or "시장"
    top1d_in = top1d_in or "시장"
    top1d_out = top1d_out or "시장"
    leader = leader or "주도주 없음"

    summary = (
        f"현재 시간은 한국 기준 {tstr} 입니다. "
        f"최근 15분 동안은 {top15} 섹터가 가장 강합니다. "
        f"일간 기준으로는 {top1d_in} 섹터에 자금이 유입되고, "
        f"{top1d_out} 섹터에서는 자금이 빠져나가고 있습니다. "
        f"현재 주도주는 {leader} 입니다."
    )
    return summary

# ----------------------------------------------------------
# ② mp3 생성 (gTTS 사용)
# ----------------------------------------------------------
def make_mp3(text: str, out_path = "briefing.mp3"):
    from gtts import gTTS
    tts = gTTS(text, lang = "ko")
    tts.save(out_path)
    return out_path

# ----------------------------------------------------------
# ③ 브리핑 전체 생성 + 전송
# ----------------------------------------------------------
def main():
    os.system(f"python3 sector_weather.py > {BRIEF}")

    if not os.path.exists(BRIEF):
        send_text("❗ 섹터 브리핑 파일이 생성되지 않았습니다.")
        return

    msg = open(BRIEF, "r", encoding = "utf-8").read()

    MAX = 3800
    if len(msg) <= MAX:
        send_text(msg)
    else:
        for i in range(0, len(msg), MAX):
            send_text(msg[i:i+MAX])

    summary = make_voice_summary(msg)
    mp3_path = make_mp3(summary)
    send_voice(mp3_path)

if __name__ == "__main__":
    main()
