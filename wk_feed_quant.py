#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, time, datetime, traceback, warnings
import numpy as np, pandas as pd, yfinance as yf
from pathlib import Path

warnings.filterwarnings("ignore", category=FutureWarning)
CACHE_DIR = "cache"
os.makedirs(CACHE_DIR, exist_ok=True)

#────────────────────────────────────────
# 공용 유틸
#────────────────────────────────────────
def now_iso(): return datetime.datetime.utcnow().strftime("%Y-%m-%dT%H:%M:%SZ")
def json_write(path, obj):
    p = Path(path); p.parent.mkdir(parents=True, exist_ok=True)
    tmp = str(p)+".tmp"
    with open(tmp, "w", encoding="utf-8") as f:
        json.dump(obj, f, ensure_ascii=False, indent=2)
    os.replace(tmp, p)

def to_iso(x):
    try: return pd.to_datetime(x).isoformat()
    except: return x

def json_safe(o):
    if isinstance(o, dict):
        return {str(k): json_safe(v) for k,v in o.items()}
    if isinstance(o,(list,tuple,set)):
        return [json_safe(v) for v in o]
    return to_iso(o)

#────────────────────────────────────────
# OHLCV 평탄화
#────────────────────────────────────────
def flatten(df):
    cols=[]; df2=df.copy()
    for c in df2.columns:
        if isinstance(c,tuple): cols.append("_".join([str(x) for x in c if x]))
        else: cols.append(str(c))
    df2.columns=cols
    need={"open","high","low","close","volume"}
    m={}
    for c in df2.columns:
        lc=c.lower()
        if "open" in lc: m["open"]=c
        if "high" in lc: m["high"]=c
        if "low" in lc: m["low"]=c
        if "close" in lc: m["close"]=c
        if "volume" in lc: m["volume"]=c
    if not need<=set(m.keys()): raise KeyError("필수 OHLCV 누락")
    ts=pd.to_datetime(df2.index,utc=True).view("int64")//1_000_000
    o=pd.to_numeric(df2[m["open"]],errors="coerce").astype("float64")
    h=pd.to_numeric(df2[m["high"]],errors="coerce").astype("float64")
    l=pd.to_numeric(df2[m["low"]],errors="coerce").astype("float64")
    c=pd.to_numeric(df2[m["close"]],errors="coerce").astype("float64")
    v=pd.to_numeric(df2[m["volume"]],errors="coerce").astype("int64")
    return pd.DataFrame({"ts":ts,"open":o,"high":h,"low":l,"close":c,"volume":v})

#────────────────────────────────────────
# 에너지 배열
#────────────────────────────────────────
def energy_array(df):
    if df is None or len(df)==0: return []
    c=df["close"].values; v=df["volume"].values
    ea=(c*v*1e-6).astype(float)
    if len(ea)>=2:
        v0=float(v[-1]); v1=float(v[-2])
        if v1>0: ea[-1]=ea[-1] if v0>=v1 else ea[-2]*(v0/v1)
    return [round(float(x),3) for x in ea]

#────────────────────────────────────────
# 매물대 계산 (윌김님 버전)
#────────────────────────────────────────
def price_profile(df,dec=2):
    pf={}; o=df["open"].values; h=df["high"].values; l=df["low"].values; c=df["close"].values; v=df["volume"].values
    n=len(c); w_o,w_l,w_h,w_c=0.2,0.3,0.3,0.2
    for i in range(n):
        vv=v[i] if v[i]>0 else 10
        for price,w in ((o[i],w_o),(l[i],w_l),(h[i],w_h),(c[i],w_c)):
            k=float(round(price,dec)); pf[k]=pf.get(k,0)+int(round(vv*w))
    pf=dict(sorted(pf.items()))
    return pf

#────────────────────────────────────────
# OHLCV 로딩
#────────────────────────────────────────
def load_ohlcv(code,interval,count):
    p="5d" if interval.endswith("m") else "6mo"
    raw=yf.download(code,period=p,interval=interval,auto_adjust=True,progress=False)
    if raw is None or raw.empty: raise RuntimeError("데이터 없음")
    raw=raw.tail(count)
    df=flatten(raw)
    return df

#────────────────────────────────────────
# 한국/미국 거래대금 상위 종목
#────────────────────────────────────────
def top_us():
    base=["TSLA","NVDA","AAPL","MSFT","AMZN","META","QQQ","SPY","IWM","TQQQ","SQQQ","SOXL","SOXS","UVXY","XLF","XLE"]
    out=[]
    for t in base:
        try:
            fi=yf.Ticker(t).fast_info
            price=fi.get("last_price"); vol=fi.get("last_volume")
            if not price or not vol: continue
            out.append({"ticker":t,"value":float(price)*float(vol)})
        except: continue
    out=sorted(out,key=lambda x:x["value"],reverse=True)
    return [x["ticker"] for x in out]

def top_kr():
    from bs4 import BeautifulSoup
    import requests
    url="https://finance.naver.com/sise/sise_quant.naver"
    h={"User-Agent":"Mozilla/5.0"}
    r=requests.get(url,headers=h,timeout=5)
    soup=BeautifulSoup(r.text,"lxml")
    table=soup.select_one("table.type_2")
    out=[]
    for row in table.select("tr"):
        a=row.select_one("a.tltle")
        tds=[td.text.strip().replace(",","").replace("%","") for td in row.select("td")]
        if not a or len(tds)<7: continue
        code=f"A{a['href'].split('code=')[-1][:6]}"
        try: tv=float(tds[6])/100.0
        except: continue
        out.append((code,tv))
    out=sorted(out,key=lambda x:x[1],reverse=True)
    return [c for c,_ in out[:33]]

#────────────────────────────────────────
# 단일 종목 처리
#────────────────────────────────────────
def build_one(symbol,interval,count):
    df=load_ohlcv(symbol,interval,count)
    pf=price_profile(df)
    ea=energy_array(df)
    return {
        "symbol":symbol,
        "interval":interval,
        "rows":len(df),
        "ohlcv":df.to_dict("records"),
        "profile":pf,
        "energy":ea,
        "saved_at":now_iso()
    }

#────────────────────────────────────────
# 메인 캐시 빌더
#────────────────────────────────────────
def build_feed():
    US=top_us()
    KR=top_kr()
    intervals=["15m","1d"]
    counts={"15m":77,"1d":77}
    group={"us":US,"kr":KR}

    for market,codes in group.items():
        for iv in intervals:
            out={}
            for code in codes:
                yf_code = f"{code[1:]}.KS" if market=="kr" else code
                try:
                    obj=build_one(yf_code,iv,counts[iv])
                    out[yf_code]=json_safe(obj)
                except Exception as e:
                    out[yf_code]={"error":str(e),"symbol":yf_code,"interval":iv}
            fn=f"{CACHE_DIR}/{market}_{iv}.json"
            json_write(fn,out)

#────────────────────────────────────────
# 실행
#────────────────────────────────────────
if __name__=="__main__":
    print("▶ WkFeedQuant: building unified OHLCV feed cache…")
    try: build_feed()
    except Exception as e:
        print("❌ 오류:",e)
        traceback.print_exc()
        raise
    print("✔ 완료:", now_iso())

