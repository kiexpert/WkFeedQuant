#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, json, yfinance as yf
import pandas as pd

#────────────────────────────────────────
# ETF 자동 분류
#────────────────────────────────────────
def classify_etf(t):
    t=t.upper()
    if t in ("SPY","QQQ","IWM","DIA","VTI"): return "Index ETF"
    if t in ("TQQQ","SQQQ"): return "NASDAQ 3x"
    if t in ("UPRO","SPXL","SPXS"): return "S&P500 3x"
    if t in ("SOXL","SOXS"): return "Semiconductor 3x"
    if t in ("TECL",): return "Tech 3x"
    if t in ("SDOW",): return "DOW 3x Inv"
    if t in ("BITX","MSTX","MSTZ"): return "Bitcoin Proxy"
    if t in ("TSLL",): return "EV Leveraged"
    if t in ("NVDL","GGLL","MSFU","AMZU","FBYY"): return "Megacap Leveraged"
    if t in ("XLE","XLF","XLK","SMH","KWEB"): return f"{t} ETF"
    return None

#────────────────────────────────────────
# 야후 섹터 추출 + ETF 우선
#────────────────────────────────────────
def ysec(ticker):
    etf=classify_etf(ticker)
    if etf: return etf
    try:
        info=yf.Ticker(ticker).info
        sec=info.get("sector") or "Unknown"
        return sec
    except:
        return "Unknown"

#────────────────────────────────────────
# 캐시 로드
#────────────────────────────────────────
def load_cache(path):
    try:
        with open(path,"r",encoding="utf-8") as f: return json.load(f)
    except:
        print(f"⚠️ 파일 로드 실패: {path}")
        return {}

#────────────────────────────────────────
# 종목 에너지 계산 (MUSD)
#────────────────────────────────────────
def compute_energy(ohlcv):
    c=ohlcv.get("close",[]); v=ohlcv.get("volume",[])
    if len(c)<2 or len(v)<2: return 0,0,0
    last=float(c[-1])*float(v[-1])*1e-6
    prev=float(c[-2])*float(v[-2])*1e-6
    diff=last-prev
    return last,prev,diff

#────────────────────────────────────────
# 섹터 스냅샷
#────────────────────────────────────────
def sector_snapshot(cache):
    rows=[]
    for cd,it in cache.items():
        sec=ysec(cd)
        last,prev,diff=compute_energy(it.get("ohlcv",{}))
        rows.append((cd,sec,last,prev,diff))
    df=pd.DataFrame(rows,columns=["code","sector","last","prev","diff"])
    sec_now=df.groupby("sector")["last"].sum().sort_values(ascending=False)
    sec_prev=df.groupby("sector")["prev"].sum()
    sec_diff=sec_now-sec_prev
    return df,sec_now,sec_prev,sec_diff

#────────────────────────────────────────
# 메인
#────────────────────────────────────────
if __name__=="__main__":
    path_now="cache/all_us_15m.json"
    now=load_cache(path_now)
    if not now:
        print("⚠️ 현재 캐시 없음"); exit(0)

    df,sec_now,sec_prev,sec_diff=sector_snapshot(now)

    print("\n📊 섹터 총 에너지 (현재)")
    for s in sec_now.index:
        now_v=sec_now[s]; diff=sec_diff.get(s,0)
        pct=(diff/sec_prev[s]*100) if sec_prev.get(s,0)>0 else 0
        print(f"  {s:24s} {now_v:12.3f} MUSD   ({diff:+8.3f} / {pct:+6.2f}%)")

    print("\n🔥 섹터별 TOP3 에너지 리더")
    for s in sec_now.index:
        top=df[df["sector"]==s].sort_values("last",ascending=False).head(3)
        print(f"\n[{s}]")
        for _,r in top.iterrows():
            last=r["last"]; prev=r["prev"]; diff=r["diff"]
            pct=(diff/prev*100) if prev>0 else 0
            print(f"  {r['code']:8s}  energy={last:10.2f} MUSD   ({diff:+7.2f} / {pct:+6.2f}%)")

