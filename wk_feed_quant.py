#!/usr/bin/env python3
# -*- coding: utf-8 -*-

import os, re, json, time, datetime, requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import yfinance as yf

CACHE_DIR = os.path.join(os.getcwd(), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

def _log(msg):
    print(msg, flush=True)

def _save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=None, ensure_ascii=False)

# ──────────────────────────────────────────
# 네이버 거래대금 상위
# ──────────────────────────────────────────
def get_top_kr(limit=33, retry=0):
    url = "https://finance.naver.com/sise/sise_quant.naver"
    headers = {"User-Agent":"Mozilla/5.0","Accept-Language":"ko-KR,en;q=0.8"}
    try:
        r=requests.get(url,headers=headers,timeout=5)
        r.raise_for_status()
        soup=BeautifulSoup(r.text,"lxml")
        table=soup.select_one("table.type_2")
        if not table: raise ValueError("table missing")

        out=[]
        for row in table.select("tr"):
            a=row.select_one("a.tltle")
            tds=[td.text.replace(",","").replace("%","").strip() for td in row.select("td")]
            if not a or len(tds)<7: continue
            name=a.text.strip()
            href=a.get("href","")
            if "code=" not in href: continue
            code="A"+href.split("code=")[-1][:6]
            try: pct=float(tds[2])
            except: pct=0.0
            try: val=float(tds[6])/100.0
            except: val=0.0
            out.append((name,code,pct,val))
        out.sort(key=lambda x:x[3],reverse=True)
        return out[:limit]
    except:
        if retry<2: time.sleep(3); return get_top_kr(limit,retry+1)
        return []

# ──────────────────────────────────────────
# 미국 리스트
# ──────────────────────────────────────────
BASE_US=[
    "SPY","QQQ","DIA","IWM","VTI",
    "TQQQ","SOXL","UPRO","TECL","FNGU",
    "SQQQ","SOXS","SDOW",
    "UVXY","VIXY","SVXY",
    "XLF","XLE","XLK","SMH",
    "ARKK","KWEB","LABU","LABD",
    "TSLA","AAPL","NVDA","AMZN","MSFT","META","AMD",
]

def get_top_us(limit=30):
    values=[]
    for t in BASE_US:
        try:
            tk=yf.Ticker(t)
            info=tk.fast_info or {}
            full=tk.info or {}
            price=info.get("last_price") or full.get("previousClose")
            volume=info.get("last_volume") or full.get("volume")
            if not price or not volume: continue
            val=float(price)*float(volume)
            name=full.get("longName") or full.get("shortName") or t
            values.append({"ticker":t,"value_b":val/1e9,"name":name})
        except:
            continue

    df=pd.DataFrame(values)
    if df.empty: return []
    df=df.sort_values("value_b",ascending=False)
    return df.head(limit).to_dict("records")

# ──────────────────────────────────────────
# 평탄화
# ──────────────────────────────────────────
def wk_ultra_flatten_ohlcv(df):
    if df is None or len(df)==0: return df
    flat=[]
    for c in df.columns:
        if isinstance(c,tuple): flat.append("_".join([str(x) for x in c if x not in ("",None)]))
        else: flat.append(str(c))
    df=df.copy(); df.columns=flat

    m={}
    for c in df.columns:
        lc=c.lower()
        if "open" in lc: m["open"]=c
        elif "high" in lc: m["high"]=c
        elif "low" in lc: m["low"]=c
        elif "close" in lc: m["close"]=c
        elif "volume" in lc: m["volume"]=c

    ts=pd.to_datetime(df.index,utc=True,errors="coerce")
    ts=(ts.view("int64")//1_000_000).astype("int64")

    return pd.DataFrame({
        "ts":ts,
        "open":pd.to_numeric(df[m["open"]],errors="coerce").astype("float64"),
        "high":pd.to_numeric(df[m["high"]],errors="coerce").astype("float64"),
        "low":pd.to_numeric(df[m["low"]],errors="coerce").astype("float64"),
        "close":pd.to_numeric(df[m["close"]],errors="coerce").astype("float64"),
        "volume":pd.to_numeric(df[m["volume"]],errors="coerce").astype("int64")
    })

# ──────────────────────────────────────────
# 거래량 보정
# ──────────────────────────────────────────
def ensure_safe_volume(df, interval):
    if df is None or df.empty: return df
    mins={"1m":1,"15m":15,"1d":390,"1wk":1950}.get(interval,15)
    fb=mins*60000
    v=[]
    for x in df["volume"]:
        try: xx=float(x)
        except: xx=0
        v.append(fb if xx<1 else int(xx))
    df=df.copy(); df["volume"]=v
    return df

# ──────────────────────────────────────────
# 매물대
# ──────────────────────────────────────────
def collect_profile(df, decimals=2):
    pf={}
    o=df["open"].values; h=df["high"].values; l=df["low"].values
    c=df["close"].values; v=df["volume"].values
    w=(0.2,0.3,0.3,0.2)

    for i in range(len(c)):
        vv=v[i] if v[i]>0 else 10
        for price,wv in ((o[i],w[0]),(l[i],w[1]),(h[i],w[2]),(c[i],w[3])):
            k=float(round(price,decimals))
            pf[k]=pf.get(k,0)+int(round(vv*wv))

    pset=set(float(round(k,decimals)) for k in pf.keys())
    pf_sorted=dict(sorted(pf.items(),key=lambda x:x[1],reverse=True))
    return pf_sorted,pset

# ──────────────────────────────────────────
# EA array
# ──────────────────────────────────────────
def compute_energy_array(df):
    c=df["close"].values.astype(float); v=df["volume"].values.astype(float); n=len(c)
    ea=np.round(c*v*1e-6,3)
    if n<2: return ea.tolist(),(float(ea[-1]) if n else None)
    p0,p1,v0,v1=c[-1],c[-2],v[-1],v[-2]
    if v0>=v1: last=p0*v0
    else:
        r=v0/v1
        last=(p0*v0)*r+(p1*v1)*(1-r)
    last=round(last*1e-6,3); ea[-1]=last
    return ea.tolist(),last

# ──────────────────────────────────────────
# OHLCV 로더
# ──────────────────────────────────────────
def load_ohlcv(code, interval="15m", count=77):
    yf_code=f"{code[1:]}.KS" if re.match(r"A\d{6}",code) else code
    period="5d" if interval.endswith("m") else "77d"

    raw=yf.download(yf_code,period=period,interval=interval,progress=False,auto_adjust=True)
    if raw is None or raw.empty:
        return None,None

    raw=raw.tail(count)
    df=wk_ultra_flatten_ohlcv(raw)
    df=ensure_safe_volume(df, interval)

    ts=pd.to_datetime(df["ts"],unit="ms",errors="coerce")
    if len(ts)>=2:
        s=ts.iloc[-1]; d=s-ts.iloc[-2]
    else:
        s=ts.iloc[-1] if len(ts)==1 else pd.Timestamp.utcnow()
        d=datetime.timedelta(minutes=15)
    e=s+d

    return df, {
        "symbol":yf_code,
        "rows":len(df),
        "last_bar_start":s.isoformat(),
        "last_bar_end":e.isoformat()
    }

# ──────────────────────────────────────────
# 캐시 1종목 생성
# ──────────────────────────────────────────
def build_cache_item(code, name, interval, count=77):
    df, meta = load_ohlcv(code, interval, count)
    if df is None or df.empty:
        return None

    pf, pset = collect_profile(df)
    ea, ea_last = compute_energy_array(df)

    meta.update({
        "name":name,
        "profile":pf,
        "price_set":sorted(list(pset)),
        "energy_array":ea,
        "energy_last":ea_last
    })

    # 🔥 여기서 1차원 배열로 저장
    ohlcv_arr = {
        "ts": df["ts"].astype(int).tolist(),
        "open": df["open"].astype(float).tolist(),
        "high": df["high"].astype(float).tolist(),
        "low": df["low"].astype(float).tolist(),
        "close": df["close"].astype(float).tolist(),
        "volume": df["volume"].astype(int).tolist(),
    }

    return {"ohlcv": ohlcv_arr, "meta": meta}

# ──────────────────────────────────────────
# KR / US 전체 병합 저장
# ──────────────────────────────────────────
all_kr={}
all_us={}

def run_feedquant():
    _log("▶ WkFeedQuant 시작")

    kr_list=get_top_kr(limit=20)
    us_list=get_top_us(limit=20)

    _log(f"🇰🇷 KR {len(kr_list)}개 / 🇺🇸 US {len(us_list)}개 수집 완료")

    for name, code, pct, val in kr_list:
        for iv in ("1m","15m","1d","1wk"):
            item=build_cache_item(code,name,iv)
            if item:
                all_kr[f"{code}_{iv}"]=item
                _log(f"  ✔ KR 저장: {code} {iv}")

    for it in us_list:
        code=it["ticker"]; name=it["name"]
        for iv in ("1m","15m","1d","1wk"):
            item=build_cache_item(code,name,iv)
            if item:
                all_us[f"{code}_{iv}"]=item
                _log(f"  ✔ US 저장: {code} {iv}")

    _save_json(os.path.join(CACHE_DIR,"all_kr.json"), all_kr)
    _save_json(os.path.join(CACHE_DIR,"all_us.json"), all_us)

    _log("✅ 모든 캐시 저장 완료")

if __name__=="__main__":
    run_feedquant()

