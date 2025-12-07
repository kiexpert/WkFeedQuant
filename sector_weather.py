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
# 야후 섹터 자동 추출 + ETF 우선 분류
#────────────────────────────────────────
def ysec(ticker):
    etf=classify_etf(ticker)
    if etf: return etf,"ETF"
    try:
        info=yf.Ticker(ticker).info
        sec=info.get("sector") or ""
        ind=info.get("industry") or ""
        if not sec: sec="Unknown"
        return sec,ind
    except:
        return "Unknown",""

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
# 종목 에너지 계산 (백만 MUSD)
#────────────────────────────────────────
def compute_energy(ohlcv):
    c=ohlcv.get("close",[]); v=ohlcv.get("volume",[])
    if len(c)<1 or len(v)<1: return 0.0
    return float(c[-1])*float(v[-1])*1e-6

#────────────────────────────────────────
# 섹터 스냅샷 생성
#────────────────────────────────────────
def sector_snapshot(cache):
    rows=[]
    for cd,it in cache.items():
        sec,_=ysec(cd)
        e=compute_energy(it.get("ohlcv",{}))
        rows.append((cd,sec,e))
    df=pd.DataFrame(rows,columns=["code","sector","energy"])
    sec=df.groupby("sector")["energy"].sum().sort_values(ascending=False)
    return df,sec

#────────────────────────────────────────
# 섹터 Δ 비교
#────────────────────────────────────────
def compare(prev,now):
    p=prev.copy(); n=now.copy()
    for s in n.index:
        if s not in p: p.loc[s]=0.0
    for s in p.index:
        if s not in n: n.loc[s]=0.0
    return (n-p).sort_values(ascending=False)

#────────────────────────────────────────
# 메인 실행
#────────────────────────────────────────
if __name__=="__main__":
    path_now="cache/all_us_15m.json"
    path_prev="cache/all_us_15m_prev.json"

    now=load_cache(path_now)
    if not now:
        print("⚠️ 현재 캐시 없음"); exit(0)

    df,sec_now=sector_snapshot(now)

    print("\n📊 섹터 총 에너지 (현재)")
    for s,v in sec_now.items():
        print(f"  {s:24s} {v:12.3f} MUSD")

    if os.path.exists(path_prev):
        prev=load_cache(path_prev)
        _,sec_prev=sector_snapshot(prev)
        d=compare(sec_prev,sec_now)
        print("\n📈 섹터 Δ 에너지 (전 스냅샷 대비)")
        for s,v in d.items():
            tag="▲" if v>0 else ("▼" if v<0 else "")
            print(f"  {s:24s} {v:12.3f} MUSD {tag}")

    print("\n🔥 섹터별 TOP3 에너지 리더")
    for s in sec_now.index:
        top=df[df["sector"]==s].sort_values("energy",ascending=False).head(3)
        print(f"\n[{s}]")
        for _,r in top.iterrows():
            print(f"  {r['code']:8s}  energy={r['energy']:10.2f} MUSD")

