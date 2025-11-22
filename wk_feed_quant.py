#!/usr/bin/env python3
# -*- coding: utf-8 -*-

"""
WkFeedQuant — KR/US 시장 차트 자동캐시 생성기
──────────────────────────────────────────────
- 네이버: 한국 거래대금 상위 종목 자동 수집
- 야후파이낸스: 미국 고거래량·대표종목 자동 수집
- OHLCV 15m, 1d 수집
- 가격평탄화 / 거래량 안전보정
- 매물대(profile), 가격집합(price_set)
- EA(백만단위 energy array) + 막봉보정 EA_last
- JSON 캐시 저장
──────────────────────────────────────────────
"""

import os, re, json, time, datetime, requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import yfinance as yf

# ============================================================
# 설정
# ============================================================
CACHE_DIR = os.path.join(os.getcwd(), "cache")
os.makedirs(CACHE_DIR, exist_ok=True)

# ============================================================
# 공통 유틸
# ============================================================
def _log(msg):
    print(msg, flush=True)

def _save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok=True)
    with open(path, "w", encoding="utf-8") as f:
        json.dump(obj, f, indent=2, ensure_ascii=False)


# ============================================================
# KR ─ 네이버 한국 거래대금 상위
# ============================================================
def get_top_kr(limit=33, retry=0):
    url = "https://finance.naver.com/sise/sise_quant.naver"
    headers = {
        "User-Agent":"Mozilla/5.0",
        "Accept-Language":"ko-KR,en;q=0.8"
    }
    try:
        r = requests.get(url, headers=headers, timeout=5)
        r.raise_for_status()
        soup = BeautifulSoup(r.text, "lxml")
        table = soup.select_one("table.type_2")
        if not table:
            raise ValueError("table missing")

        out = []
        for row in table.select("tr"):
            a = row.select_one("a.tltle")
            tds = [td.text.replace(",", "").replace("%", "").strip() for td in row.select("td")]
            if not a or len(tds) < 7:
                continue
            name = a.text.strip()
            href = a.get("href","")
            if "code=" not in href:
                continue
            code = "A"+href.split("code=")[-1][:6]
            try: pct = float(tds[2])
            except: pct = 0.0
            try: val = float(tds[6])/100.0
            except: val = 0.0
            out.append((name, code, pct, val))

        out.sort(key=lambda x: x[3], reverse=True)
        return out[:limit]

    except Exception:
        if retry < 2:
            time.sleep(3)
            return get_top_kr(limit, retry+1)
        return []


# ============================================================
# US ─ 야후파이낸스 미국 종목 리스트
# ============================================================
BASE_US = [
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
            price = info.get("last_price") or full.get("previousClose") or full.get("lastPrice")
            volume= info.get("last_volume") or full.get("volume")
            if not price or not volume:
                continue
            val=float(price)*float(volume)
            name=full.get("longName") or full.get("shortName") or t
            values.append({"ticker":t,"value_b":val/1e9,"name":name})
        except:
            continue

    df=pd.DataFrame(values)
    if df.empty:
        return []
    df=df.sort_values("value_b",ascending=False)
    return df.head(limit).to_dict("records")


# ============================================================
# OHLCV 평탄화 (야후 공통)
# ============================================================
def wk_ultra_flatten_ohlcv(df):
    if df is None or df.empty:
        return pd.DataFrame()

    cols=[]
    for c in df.columns:
        if isinstance(c, tuple):
            cols.append("_".join([str(x) for x in c if x not in ("",None)]))
        else:
            cols.append(str(c))
    df=df.copy()
    df.columns=cols

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

    def num(x): return pd.to_numeric(x,errors="coerce")

    out=pd.DataFrame({
        "ts": ts,
        "open":num(df[m["open"]]),
        "high":num(df[m["high"]]),
        "low":num(df[m["low"]]),
        "close":num(df[m["close"]]),
        "volume":num(df[m["volume"]]).astype("int64")
    })
    return out


# ============================================================
# 거래량 안전보정
# ============================================================
def ensure_safe_volume(df, interval):
    if df is None or df.empty:
        return df
    mins={"1m":1,"15m":15,"1d":390,"1wk":390*5}.get(interval,15)
    fb=mins*60000
    vv=[]
    for x in df["volume"]:
        try:
            xx=float(x)
        except:
            xx=0
        vv.append(fb if xx < 1 else int(xx))
    df=df.copy()
    df["volume"]=vv
    return df


# ============================================================
# 매물대 / price set
# ============================================================
def collect_profile(df, decimals=2):
    pf={}
    o=df["open"].values; h=df["high"].values; l=df["low"].values
    c=df["close"].values; v=df["volume"].values
    w_o,w_l,w_h,w_c=0.2,0.3,0.3,0.2
    n=len(c)

    for i in range(n):
        vv = v[i] if v[i]>0 else 10
        for price,w in ((o[i],w_o),(l[i],w_l),(h[i],w_h),(c[i],w_c)):
            k=float(round(price,decimals))
            pf[k]=pf.get(k,0)+int(round(vv*w))

    pset=set([float(round(x,decimals)) for x in list(pf.keys())])
    pf_sorted=dict(sorted(pf.items(), key=lambda x: x[1], reverse=True))
    return pf_sorted, pset


# ============================================================
# EA array (백만단위 + 막봉보정)
# ============================================================
def compute_energy_array(df):
    closes=df["close"].astype(float).values
    vols=df["volume"].astype(float).values
    n=len(closes)
    ea=(closes*vols)*1e-6
    if n < 2:
        last=float(ea[-1]) if n>0 else None
        return ea.tolist(), last

    v0=vols[-2]; v1=vols[-1]
    if v0<=0:
        ea_last=float(ea[-2])
    else:
        ea_last=float(ea[-2]*(v1/v0))
    return ea.tolist(), ea_last


# ============================================================
# OHLCV 로더
# ============================================================
def load_ohlcv(code, interval="15m", count=77):
    if re.match(r"A\d{6}", code):
        yf_code=f"{code[1:]}.KS"
    else:
        yf_code=code
    period="5d" if interval.endswith("m") else "77d"

    raw=yf.download(yf_code,period=period,interval=interval,progress=False,auto_adjust=True)
    if raw is None or raw.empty:
        return None,None

    raw=raw.tail(count)
    df=wk_ultra_flatten_ohlcv(raw)
    df=ensure_safe_volume(df, interval)

    # start/end bar
    ts=pd.to_datetime(df["ts"],unit="ms",errors="coerce").dropna()
    if len(ts)>=2:
        s=ts.iloc[-1]; d=s-ts.iloc[-2]
    else:
        s=ts.iloc[-1] if len(ts)==1 else pd.Timestamp.utcnow()
        d=datetime.timedelta(minutes=15)
    e=s+d

    meta={
        "symbol":yf_code,
        "rows":len(df),
        "last_bar_start":s.isoformat(),
        "last_bar_end":e.isoformat()
    }
    return df, meta


# ============================================================
# 캐시 생성기
# ============================================================
def build_cache_item(code, name, interval, count=77):
    df, meta=load_ohlcv(code, interval, count)
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
    return {
        "ohlcv":df.to_dict("records"),
        "meta":meta
    }


# ============================================================
# 메인 실행
# ============================================================
def run_feedquant():
    _log("▶ WkFeedQuant 시작")

    # KR/US 리스트
    kr_list=get_top_kr(limit=20)
    us_list=get_top_us(limit=20)

    _log(f"🇰🇷 KR {len(kr_list)}개 / 🇺🇸 US {len(us_list)}개 수집 완료")

    # KR 캐시
    for name, code, pct, val in kr_list:
        for iv in ("15m","1d"):
            item=build_cache_item(code, name, iv)
            if item:
                path=os.path.join(CACHE_DIR, f"{code}_{iv}.json")
                _save_json(path, item)
                _log(f"  ✔ KR 저장: {code} {iv}")

    # US 캐시
    for it in us_list:
        code=it["ticker"]; name=it["name"]
        for iv in ("15m","1d"):
            item=build_cache_item(code, name, iv)
            if item:
                path=os.path.join(CACHE_DIR, f"{code}_{iv}.json")
                _save_json(path, item)
                _log(f"  ✔ US 저장: {code} {iv}")

    _log("✅ 모든 캐시 저장 완료")


# ============================================================
# Self Test
# ============================================================
if __name__=="__main__":
    run_feedquant()
