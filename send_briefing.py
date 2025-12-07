#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os
from telegram_notify import send_text

BRIEF = "briefing.txt"

def main():
    # 1) 섹터 브리핑 생성
    os.system(f"python3 sector_weather.py > {BRIEF}")

    # 2) 파일 확인
    if not os.path.exists(BRIEF):
        send_text("❗ 섹터 브리핑 파일이 생성되지 않았습니다.")
        return

    msg = open(BRIEF, "r", encoding="utf-8").read()

    # 3) 텔레그램 전송 (길면 분할)
    MAX = 3800
    if len(msg) <= MAX:
        send_text(msg)
    else:
        for i in range(0, len(msg), MAX):
            send_text(msg[i:i+MAX])

if __name__ == "__main__":
    main()
