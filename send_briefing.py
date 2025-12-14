#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, re
from telegram_notify import send_text, send_voice

BRIEF = "briefing.txt"

# ----------------------------------------------------------
# ① 음성용 초요약 생성기 (현재 시간 포함, KST 기준)
# ----------------------------------------------------------
def make_voice_summary(full_text:str)->str:
    from datetime import datetime,timedelta
    import re
    now_kst=datetime.utcnow()+timedelta(hours=9)
    tstr=now_kst.strftime("%d일 %H시 %M분")
    text=re.sub(r'\x1b\[[0-9;]*m','',full_text)
    text=text.replace('\n\t','\t')
    lines=text.splitlines()
    SECTOR_LINE_RE=re.compile(r'^\s*(?P<name>[A-Za-z0-9&.\- ]+?)\s{2,}(?P<energy>[0-9,]+(?:\.[0-9]+)?)\s*MUSD.*?Δ15m:\s*(?P<d15>[+\-][0-9.]+).*?Δ1d:\s*(?P<d1d>[+\-][0-9.]+)',re.ASCII)
    sectors=[]
    for i,l in enumerate(lines):
        m=SECTOR_LINE_RE.search(l)
        if not m: continue
        sectors.append({
            "name":m.group("name").strip(),
            "energy":float(m.group("energy").replace(',','')),
            "d15":float(m.group("d15")),
            "d1d":float(m.group("d1d")),
            "line":i
        })
    print("===== DEBUG: parsed sectors =====")
    for s in sectors: print(s)
    print("===== DEBUG END =====")
    top15=max(sectors,key=lambda x:x["d15"],default=None)
    top1d_in=max(sectors,key=lambda x:x["d1d"],default=None)
    top1d_out=min(sectors,key=lambda x:x["d1d"],default=None)
    leader=None
    for l in lines:
        if "energy=" in l:
            leader=l.strip().split()[0]
            break
    def scale(v):
        return f"{v/1000:.1f} 빌리언달러" if abs(v)>=1000 else f"{abs(v):.0f} 밀리언달러"
    print("===== DEBUG: voice summary picks =====")
    print("top15=",top15)
    print("top1d_in=",top1d_in)
    print("top1d_out=",top1d_out)
    print("leader=",leader)
    print("===== DEBUG END =====")
    summary=(
        f"{tstr} 현재 {top15['name']} 섹터에 약 {scale(top15['d15'])}가 최근 15분 동안 가장 강하게 들어왔습니다. "
        f"오늘은 {top1d_in['name']} 섹터로 약 {scale(top1d_in['d1d'])} 들어오고, "
        f"{top1d_out['name']} 섹터에서는 약 {scale(top1d_out['d1d'])} 빠져나가고 있습니다. "
        f"현재 주도주는 {leader} 입니다."
    )
    print("===== DEBUG: final voice briefing =====")
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
