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
    if len(c)<28: return 0,0,0,0,0  # Δ15m/Δ1d 모두 필요
    last=float(c[-1])*float(v[-1])*1e-6
    prev=float(c[-2])*float(v[-2])*1e-6
    prev1d=float(c[-27])*float(v[-27])*1e-6
    diff15=last-prev
    diff1d=last-prev1d
    return last,prev,prev1d,diff15,diff1d

#────────────────────────────────────────
# 섹터 스냅샷
#────────────────────────────────────────
def sector_snapshot(cache):
    rows=[]
    for cd,it in cache.items():
        sec=ysec(cd)
        last,prev,prev1d,d15,d1d=compute_energy(it.get("ohlcv",{}))
        rows.append((cd,sec,last,prev,prev1d,d15,d1d))
    df=pd.DataFrame(rows,columns=["code","sector","last","prev","prev1d","d15","d1d"])
    sec_now=df.groupby("sector")["last"].sum().sort_values(ascending=False)
    sec_prev=df.groupby("sector")["prev"].sum()
    sec_prev1=df.groupby("sector")["prev1d"].sum()
    sec_d15=df.groupby("sector")["d15"].sum()
    sec_d1d=df.groupby("sector")["d1d"].sum()
    return df,sec_now,sec_prev,sec_prev1,sec_d15,sec_d1d

#────────────────────────────────────────
# 메인
#────────────────────────────────────────
if __name__=="__main__":
    path_now="cache/all_us_15m.json"
    now=load_cache(path_now)
    if not now:
        print("⚠️ 현재 캐시 없음"); exit(0)

    df,sec_now,sec_prev,sec_prev1,sec_d15,sec_d1d=sector_snapshot(now)

    print("\n📊 섹터 총 에너지 (현재)")
    for s in sec_now.index:
        now_v=sec_now[s]
        d15=sec_d15.get(s,0); p15=sec_prev.get(s,0); pct15=(d15/p15*100) if p15 else 0
        d1d=sec_d1d.get(s,0); p1d=sec_prev1.get(s,0); pct1d=(d1d/p1d*100) if p1d else 0
        print(f"  {s:24s} {now_v:12.3f} MUSD   (Δ15m:{d15:+8.3f}/{pct15:+6.2f}% , Δ1d:{d1d:+8.3f}/{pct1d:+6.2f}%)")

    print("\n🔥 섹터별 TOP3 에너지 리더")
    for s in sec_now.index:
        top=df[df["sector"]==s].sort_values("last",ascending=False).head(3)
        print(f"\n[{s}]")
        for _,r in top.iterrows():
            last=r["last"]; prev=r["prev"]; prev1d=r["prev1d"]
            d15=r["d15"]; d1d=r["d1d"]
            pct15=(d15/prev*100) if prev else 0
            pct1d=(d1d/prev1d*100) if prev1d else 0
            print(f"  {r['code']:8s}  energy={last:10.2f} MUSD   (Δ15m:{d15:+7.2f}/{pct15:+6.2f}% , Δ1d:{d1d:+7.2f}/{pct1d:+6.2f}%)")

