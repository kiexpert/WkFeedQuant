#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, yfinance as yf

CACHE_DIR = "cache"
FILES = ["all_kr_15m.json","all_us_15m.json","all_ix_15m.json"]

def load_codes_from_cache():
    codes=[]
    for fn in FILES:
        path=os.path.join(CACHE_DIR,fn)
        if not os.path.exists(path): continue
        try:
            with open(path,"r",encoding="utf-8") as f:
                js=json.load(f)
                codes+=list(js.keys())
        except:
            pass
    return sorted(set(codes))

def get_sector(code):
    try:
        info=yf.Ticker(code).info
        sec=info.get("sector")
        return sec if sec else "Unknown"
    except:
        return "Unknown"

def summarize_sectors(codes):
    sec_map={}
    for code in codes:
        sec=get_sector(code)
        sec_map.setdefault(sec,[]).append(code)
    out=[]
    for sec, lst in sec_map.items():
        leaders=lst[:3] if len(lst)>3 else lst
        out.append((sec,len(lst),leaders))
    out.sort(key=lambda x:-x[1])
    return out

if __name__=="__main__":
    codes=load_codes_from_cache()
    summary=summarize_sectors(codes)
    print("섹터명\t종목수\t대표 종목")
    for sec,cnt,lead in summary:
        print(f"{sec}\t{cnt}\t{', '.join(lead)}")
