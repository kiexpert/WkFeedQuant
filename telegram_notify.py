#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, requests

TOKEN = os.environ["TELEGRAM_BOT_TOKEN"]
CHAT  = os.environ["TELEGRAM_CHAT_ID"]
API   = f"https://api.telegram.org/bot{TOKEN}"

def send_text(msg: str):
    return requests.post(f"{API}/sendMessage", data={
        "chat_id": CHAT,
        "text": msg
    })
