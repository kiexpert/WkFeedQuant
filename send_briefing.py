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
    def strip_ansi(s): return re.sub(r"\x1b\[[0-9;]*m","",s)
    now_utc=datetime.utcnow(); now_kst=now_utc+timedelta(hours=9); tstr=now_kst.strftime("%Y-%m-%d %H시 %M분")
    txt=strip_ansi(full_text).replace("\n\t","\t")
    lines=txt.splitlines()
    print("===== DEBUG: voice summary lines =====")
    for i,l in enumerate(lines): print(f"{i:03d}: {l}")
    print("===== DEBUG END =====")
    rx_head=re.compile(r"^\s*(?P<name>[A-Za-z0-9 &+.-]+?)\s+(?P<energy>[0-9.]+)\s*MUSD")
    rx_15=re.compile(r"Δ15m:\s*([+-])\s*[0-9.]+\s*/\s*([0-9.]+)%")
    rx_1d=re.compile(r"Δ1d:\s*([+-])\s*[0-9.]+\s*/\s*([0-9.]+)%")
    rx_leader=re.compile(r"^\s*([A-Z0-9._-]+)\s+energy=")
    best15=-1e18; best1d=-1e18; worst1d=1e18
    top15=None; top1d_in=None; top1d_out=None; leader=None
    for line in lines:
        s=line.strip()
        if not s: continue
        if leader is None:
            m=rx_leader.match(s)
            if m: leader=m.group(1)
        m=rx_head.match(line)
        if not m: continue
        name=m.group("name").strip()
        energy=float(m.group("energy"))
        m15=rx_15.search(line)
        m1d=rx_1d.search(line)
        if not m15 or not m1d: continue
        d15=float(m15.group(2)); d15=-d15 if m15.group(1)=="-" else d15
        d1=float(m1d.group(2)); d1=-d1 if m1d.group(1)=="-" else d1
        if d15>best15: best15=d15; top15=(name,energy,d15)
        if d1>best1d: best1d=d1; top1d_in=(name,energy,d1)
        if d1<worst1d: worst1d=d1; top1d_out=(name,energy,d1)
    if top15 is None: top15=("시장",None,None)
    if top1d_in is None: top1d_in=("시장",None,None)
    if top1d_out is None: top1d_out=("시장",None,None)
    if leader is None: leader="주도주 없음"
    def scale(v):
        if v is None: return ""
        return f"{v/1000:.1f}빌리언달러" if v>=1000 else f"{v:.0f}밀리언달러"
    summary=(f"현재 시간은 한국 기준 {tstr} 입니다. "
             f"최근 15분 동안은 {top15[0]} 섹터가 가장 강하며 {scale(top15[1])} 규모입니다. "
             f"일간 기준으로는 {top1d_in[0]} 섹터로 자금이 유입되고, "
             f"{top1d_out[0]} 섹터에서 자금이 빠져나가고 있습니다. "
             f"현재 주도주는 {leader} 입니다.")
    print("===== DEBUG: voice summary picks =====")
    print("top15=",top15)
    print("top1d_in=",top1d_in)
    print("top1d_out=",top1d_out)
    print("leader=",leader)
    print("===== DEBUG END =====")
    print("===== DEBUG: voice summary result =====")
    print(summary)
    print("===== DEBUG END =====")
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
