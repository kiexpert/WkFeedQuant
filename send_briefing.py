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
    import re
    # KST 시간 계산
    now_kst = datetime.utcnow() + timedelta(hours=9)
    tstr = now_kst.strftime("%Y-%m-%d %H시 %M분")
    # 줄 전처리: 의도적 줄늘림(\n\t) 복구
    lines = full_text.replace("\n\t", "\t").splitlines()
    sector_rows = []
    in_sector_block = False
    # 섹터 요약 라인 정규식 (풀네임 + 수치 추출)
    rx = re.compile(r'^\s{2,}([A-Za-z& ]+?)\s+([\d.]+)\s+MUSD.*?Δ15m:\s*([+-][\d.]+).*?Δ1d:\s*([+-][\d.]+)', re.UNICODE)
    for line in lines:
        if "📊 섹터 총 에너지" in line:
            in_sector_block = True
            continue
        if in_sector_block and not line.strip():
            break
        if not in_sector_block:
            continue
        m = rx.search(line)
        if not m:
            continue
        name = m.group(1).strip()
        energy = float(m.group(2))
        d15 = float(m.group(3))
        d1d = float(m.group(4))
        sector_rows.append({"name": name, "energy": energy, "d15": d15, "d1d": d1d})
    # 금액 단위 음성 변환
    def fmt_money(musd: float) -> str:
        return f"{musd/1000:.1f} billion dollars" if musd >= 1000 else f"{musd:.1f} million dollars"
    # 강세 / 유입 / 유출 판별
    top15 = max(sector_rows, key=lambda x: x["d15"], default=None)
    top1d_in = max(sector_rows, key=lambda x: x["d1d"], default=None)
    top1d_out = min((s for s in sector_rows if s["d1d"] < 0), key=lambda x: x["d1d"], default=None)
    # 주도주 (TOP3 첫 종목)
    leader = None
    for line in lines:
        if "energy=" in line:
            leader = line.strip().split()[0]
            break
    summary = (
        f"현재 시간은 한국 기준 {tstr} 입니다. "
        f"최근 15분 동안은 {top15['name']} 섹터가 가장 강하며 "
        f"약 {fmt_money(top15['energy'])} 규모의 자금이 움직였습니다. "
        f"일간 기준으로는 {top1d_in['name']} 섹터에 자금이 유입되고, "
        f"{top1d_out['name']} 섹터에서는 자금이 빠져나가고 있습니다. "
        f"현재 주도주는 {leader or '확인되지 않음'} 입니다."
    )
    # 디버그 출력
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
