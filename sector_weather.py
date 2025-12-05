#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import json, yfinance as yf
from feedquant import fetch_ohlcv_auto

def get_sector(code):
    try:
        t=yf.Ticker(code)
        s=t.info.get("sector")
        return s if s else "Unknown"
    except:
        return "Unknown"

def summarize_sectors(codes):
    out={}
    for code in codes:
        sec=get_sector(code)
        d=out.setdefault(sec,[])
        d.append(code)
    rep=lambda xs: xs[:2] if len(xs)>2 else xs
    summary=[]
    for sec, lst in out.items():
        summary.append((sec, len(lst), rep(lst)))
    summary.sort(key=lambda x:-x[1])
    return summary

if __name__=="__main__":
    # feedquant 캐시에서 가져온 전체 코드 목록 예시
    all_codes=list(set(
        list(feedquant._feedquant["1m"]["us"].keys())+
        list(feedquant._feedquant["1m"]["kr"].keys())+
        list(feedquant._feedquant["1m"]["ix"].keys())
    ))
    summary=summarize_sectors(all_codes)
    for sec,cnt,leaders in summary:
        print(f"{sec}\t{cnt}\t{', '.join(leaders)}")
