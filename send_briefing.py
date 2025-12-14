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
    def strip_ansi(s: str) -> str:
        return re.sub(r"\x1b\[[0-9;]*m", "", s)
    def fnum(x):
        try: return float(x)
        except: return None
    now_utc=datetime.utcnow(); now_kst=now_utc+timedelta(hours=9); tstr=now_kst.strftime("%Y-%m-%d %H시 %M분")
    txt=strip_ansi(full_text).replace("\n\t","\t")
    lines=txt.splitlines()
    print("===== DEBUG: voice summary lines =====")
    for i,l in enumerate(lines): print(f"{i:03d}: {l}")
    print("===== DEBUG END =====")
    rx_sector=re.compile(r"^\s*(?P<name>.+?)\s+(?P<energy>[0-9.]+)\s*MUSD\s*\(.*?Δ15m:\s*(?P<d15_sign>[+-])\s*(?P<d15_val>[0-9.]+)\s*/\s*(?P<d15_pct>[0-9.]+)%\s*,\s*Δ1d:\s*(?P<d1_sign>[+-])\s*(?P<d1_val>[0-9.]+)\s*/\s*(?P<d1_pct>[0-9.]+)%\s*\)")
    rx_leader=re.compile(r"^\s*(?P<sym>[A-Z0-9._-]+)\s+energy=\s*(?P<en>[0-9.]+)\s*MUSD",re.I)
    top15=None; top1d_in=None; top1d_out=None; leader=None
    best15=-1e18; best1d=-1e18; worst1d=1e18
    for line in lines:
        s=line.strip()
        if not s: continue
        if leader is None:
            m=rx_leader.match(s)
            if m: leader=m.group("sym")
        m=rx_sector.match(line)
        if not m: continue
        name=m.group("name").strip()
        e=fnum(m.group("energy"))
        d15=fnum(m.group("d15_pct")); d15 = -d15 if m.group("d15_sign")=="-" and d15 is not None else d15
        d1=fnum(m.group("d1_pct")); d1  = -d1  if m.group("d1_sign")=="-"  and d1  is not None else d1
        if d15 is not None and d15>best15: best15=d15; top15={"name":name,"energy":e,"pct":d15}
        if d1  is not None and d1 >best1d: best1d=d1; top1d_in={"name":name,"energy":e,"pct":d1}
        if d1  is not None and d1 <worst1d: worst1d=d1; top1d_out={"name":name,"energy":e,"pct":d1}
    if top15 is None: top15={"name":"시장","energy":None,"pct":None}
    if top1d_in is None: top1d_in={"name":"시장","energy":None,"pct":None}
    if top1d_out is None: top1d_out={"name":"시장","energy":None,"pct":None}
    if leader is None: leader="주도주 없음"
    def scale_musd(musd):
        if musd is None: return None
        if musd>=1000: return f"{musd/1000:.1f}B달러"
        return f"{musd:.0f}M달러"
    top15_sz=scale_musd(top15["energy"]); in_sz=scale_musd(top1d_in["energy"]); out_sz=scale_musd(top1d_out["energy"])
    summary=(f"현재 시간은 한국 기준 {tstr} 입니다. "
             f"최근 15분 동안은 {top15['name']} 섹터가 가장 강하며{(' 규모는 '+top15_sz) if top15_sz else ''} "
             f"일간 기준으로는 {top1d_in['name']} 섹터로 자금이 유입되고{(' 규모는 '+in_sz) if in_sz else ''}, "
             f"{top1d_out['name']} 섹터에서 자금이 빠져나가고 있습니다{(' 규모는 '+out_sz) if out_sz else ''}. "
             f"현재 주도주는 {leader} 입니다.")
    print("===== DEBUG: voice summary picks =====")
    print("top15=",top15); print("top1d_in=",top1d_in); print("top1d_out=",top1d_out); print("leader=",leader)
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
