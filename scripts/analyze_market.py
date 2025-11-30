#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, json

CACHE_DIR = os.path.join(os.getcwd(), "cache")
UNITS  = {"kr": "MKRW", "us": "MUSD", "ix": "MIDX"}
TITLES = {"kr": "KR", "us": "US", "ix": "IDX"}
FLAGS  = {"kr": "🇰🇷", "us": "🇺🇸", "ix": "📈"}
TOP_LIMIT = 7  # ← 변경

def _load_json(path):
    if not os.path.exists(path): return {}
    with open(path,"r",encoding="utf-8") as f:
        return json.load(f)

def load_market(market):
    name = {"kr":"all_kr_15m.json","us":"all_us_15m.json","ix":"all_ix_15m.json"}.get(market)
    if not name: return {}
    return _load_json(os.path.join(CACHE_DIR,name))

def collect_top(market, limit=TOP_LIMIT):
    rows = []
    for code,item in load_market(market).items():
        en = item.get("energies")
        if not en: continue
        try: val = float(en[-1])
        except: continue
        rows.append((val,item.get("name",code),code,item.get("symbol",code)))
    rows.sort(key=lambda x:x[0], reverse=True)
    return rows[:limit]

def format_market(market, rows):
    flag=FLAGS[market]; title=TITLES[market]; unit=UNITS[market]
    out=[f"{flag} {title} 15m Top {len(rows)} ({unit})"]
    for i,(v,n,c,s) in enumerate(rows,1):
        out.append(f"{i}. {n} ({s}) {v:.2f} {unit}")
    return "\n".join(out)

if __name__=="__main__":
    market=(sys.argv[1] if len(sys.argv)>1 else "kr").lower()
    if market not in ("kr","us","ix","all"): market="kr"
    targets=("kr","us","ix") if market=="all" else (market,)
    for m in targets:
        print(format_market(m, collect_top(m))+"\n")
