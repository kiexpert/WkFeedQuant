#!/usr/bin/env python3
# -*- coding: utf-8 -*-

#────────────────────────────────────────
# 🇺🇸 WkFeedQuant 기반 섹터 에너지 흐름 분석기
#  - 종목별 energy = close * volume
#  - 섹터별 총 에너지 + Δ 변화량
#  - 섹터별 TOP3 리더(주도주/짝궁주)
#────────────────────────────────────────

import os, json, yfinance as yf
import pandas as pd

#────────────────────────────────────────
# 야후 섹터 자동 추출 (ETF/레버리지는 Unknown → 규칙추가 예정)
#────────────────────────────────────────
def ysec(t):
    try:
        info=yf.Ticker(t).info
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
# 종목 단위 에너지 계산
#────────────────────────────────────────
def compute_energy(ohlcv):
    c=ohlcv.get("close",[])
    v=ohlcv.get("volume",[])
    if len(c)<1 or len(v)<1: return 0.0
    return float(c[-1])*float(v[-1])*1e-6  # 백만 단위 축소

#────────────────────────────────────────
# 섹터 스냅샷 계산
#────────────────────────────────────────
def sector_energy_snapshot(cache):
    rows=[]
    for cd,it in cache.items():
        sec,_=ysec(cd)
        e=compute_energy(it.get("ohlcv",{}))
        rows.append((cd,sec,e))
    df=pd.DataFrame(rows,columns=["code","sector","energy"])
    sec=df.groupby("sector")["energy"].sum().sort_values(ascending=False)
    lead=df.sort_values("energy",ascending=False)
    return df,sec,lead

#────────────────────────────────────────
# 섹터 에너지 변화량 Δ
#────────────────────────────────────────
def compare(prev,now):
    # prev/now 모두 pandas Series
    # index 맞추고 차이 계산
    prev2=prev.copy()
    now2=now.copy()
    # 없는 섹터는 0으로 처리
    for s in now2.index:
        if s not in prev2: prev2.loc[s]=0.0
    for s in prev2.index:
        if s not in now2: now2.loc[s]=0.0
    d=(now2-prev2).sort_values(ascending=False)
    return d

#────────────────────────────────────────
# 메인 실행
#────────────────────────────────────────
if __name__=="__main__":
    path_now="cache/all_us_15m.json"
    path_prev="cache/all_us_15m_prev.json"

    now=load_cache(path_now)
    if not now:
        print("⚠️ 현재 캐시 없음"); exit(0)

    # 스냅샷 계산
    df,sec_now,lead=sector_energy_snapshot(now)

    print("\n📊 섹터 총 에너지 (현재)")
    for s,v in sec_now.items():
        print(f"  {s:24s} {v:10.3f} MUSD")

    # Δ 분석
    if os.path.exists(path_prev):
        prev=load_cache(path_prev)
        _,sec_prev,_=sector_energy_snapshot(prev)
        d=compare(sec_prev,sec_now)
        print("\n📈 섹터 Δ 에너지 (전 스냅샷 대비)")
        for s,v in d.items():
            tag="▲" if v>0 else ("▼" if v<0 else "")
            print(f"  {s:20s} {v:8.2f} {tag}")

    # TOP3 리더(주도주/짝궁주)
    print("\n🔥 섹터별 TOP3 에너지 리더")
    for s in sec_now.index:
        top=df[df["sector"]==s].sort_values("energy",ascending=False).head(3)
        print(f"\n[{s}]")
        for _,r in top.iterrows():
            print(f"  {r['code']:6s}  energy={r['energy']:.2f}")


