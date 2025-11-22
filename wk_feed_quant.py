#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os,re,json,time,datetime
import numpy as np
import pandas as pd
import yfinance as yf
from bs4 import BeautifulSoup
import requests

CACHE_DIR="cache";os.makedirs(CACHE_DIR,exist_ok=True)

def _json(o):
    if isinstance(o,(pd.Timestamp,datetime.datetime,datetime.date,np.datetime64)):
        return pd.to_datetime(o).isoformat()
    if isinstance(o,dict): return {k:_json(v) for k,v in o.items()}
    if isinstance(o,(list,tuple,set)): return [_json(x) for x in o]
    return o

# ───────────────────────────────────────────
# 네이버 거래대금 상위
# ───────────────────────────────────────────
def get_top_items(limit=60,retry=0):
    url="https://finance.naver.com/sise/sise_quant.naver"
    headers={"User-Agent":"Mozilla/5.0","Referer":"https://finance.naver.com/"}
    try:
        r=requests.get(url,headers=headers,timeout=5);r.raise_for_status()
        soup=BeautifulSoup(r.text,"lxml")
        table=soup.select_one("table.type_2")
        if not table: raise ValueError("table")
        out=[]
        for row in table.select("tr"):
            a=row.select_one("a.tltle")
            if not a: continue
            name=a.text.strip();href=a.get("href","")
            if "code=" not in href: continue
            code=f"{href.split('code=')[-1][:6]}.KQ"
            tds=[td.text.strip().replace(",","") for td in row.select("td")]
            if len(tds)<7: continue
            try: val=float(tds[6])/100.0
            except: val=0
            out.append((name,code,val))
        out.sort(key=lambda x:x[2],reverse=True)
        return out[:limit]
    except:
        if retry<2: time.sleep(3); return get_top_items(limit,retry+1)
        return []

# ───────────────────────────────────────────
# 야후 로더
# ───────────────────────────────────────────
def yf_code_from(code):
    if re.match(r"A?\d{6}",code): return f"{re.sub(r'^A','',code)}.KS"
    return code

def load_yf_ohlcv(symbol,interval,count):
    yf_code=yf_code_from(symbol)
    raw=yf.download(yf_code,period="5d" if interval.endswith("m") else "100d",
                    interval=interval,progress=False,auto_adjust=True)
    if raw is None or raw.empty: return None,None
    raw=raw.tail(count)
    df=_flatten(raw)
    name=yf.Ticker(yf_code).info.get("longName") or yf_code
    return df,name

def _flatten(df):
    df=df.copy();cols={}
    for c in df.columns:
        k=str(c).lower()
        if "open" in k: cols.setdefault("open",c)
        if "high" in k: cols.setdefault("high",c)
        if "low" in k: cols.setdefault("low",c)
        if "close" in k: cols.setdefault("close",c)
        if "volume" in k: cols.setdefault("volume",c)
    ts=pd.to_datetime(df.index,utc=True).view("int64")//1_000_000
    o=pd.to_numeric(df[cols["open"]])
    h=pd.to_numeric(df[cols["high"]])
    l=pd.to_numeric(df[cols["low"]])
    c=pd.to_numeric(df[cols["close"]])
    v=pd.to_numeric(df[cols["volume"]])
    return pd.DataFrame({"ts":ts,"open":o,"high":h,"low":l,"close":c,"volume":v})

# ───────────────────────────────────────────
# 매물대 & 에너지
# ───────────────────────────────────────────
def compute_profile_energy(df):
    prices=set()
    for _,r in df.iterrows():
        prices.add(round(r["open"],2))
        prices.add(round(r["high"],2))
        prices.add(round(r["low"],2))
        prices.add(round(r["close"],2))

    profile={}
    w_open,w_low,w_high,w_close=0.2,0.3,0.3,0.2
    c=df["close"].values;v=df["volume"].values
    for i in range(len(df)):
        vv=v[i] if v[i]>0 else 10
        for p,w in ((df.loc[i,"open"],w_open),(df.loc[i,"low"],w_low),
                    (df.loc[i,"high"],w_high),(df.loc[i,"close"],w_close)):
            k=float(round(p,2))
            profile[k]=profile.get(k,0)+int(vv*w)

    if len(df)>=2:
        p0,v0=c[-1],v[-1];p1,v1=c[-2],v[-2]
        last=(p0*v0)*1e-6 if v0>=v1 else ((p0*v0)*(v0/v1)+(p1*v1)*(1-v0/v1))*1e-6
    else:
        last=(c[-1]*v[-1])*1e-6

    last=round(last,3)
    profile[0]=last
    energy=np.round(c*v*1e-6,3)
    if len(energy)>0: energy[-1]=last
    return sorted(prices), dict(sorted(profile.items(),key=lambda x:x[1],reverse=True)), energy.tolist(), last

# ───────────────────────────────────────────
# 미국 종목 리스트
# ───────────────────────────────────────────
def load_us_list(n=60):
    base=["TSLA","AAPL","NVDA","AMZN","META","MSFT","NFLX","^NDX","^GSPC",
          "SPY","QQQ","SOXL","SOXS","UVXY","BITX","TQQQ","SQQQ"]
    return base[:n]

# ───────────────────────────────────────────
# 핵심: build_and_flush (빈 JSON 문제 완전 해결)
# ───────────────────────────────────────────
def build_and_flush(interval,codes,is_kr,count,out_path):
    os.makedirs(os.path.dirname(out_path),exist_ok=True)
    result={}
    print(f"🚀 Build {interval} / 종목 {len(codes)}개")

    for idx,(name,code) in enumerate(codes,1):
        try:
            print(f"[{idx}/{len(codes)}] {code} 처리중…",flush=True)
            df,cname=load_yf_ohlcv(code,interval,count)
            if df is None or len(df)==0:
                print(f"   ⚠️ 데이터 없음"); continue

            ps,profile,energy,elast=compute_profile_energy(df)

            obj={
                "symbol":yf_code_from(code),
                "name":cname,
                "interval":interval,
                "rows":len(df),
                "saved_at":datetime.datetime.utcnow().isoformat(),
                "ohlcv":df.astype(float).to_dict("records"),
                "price_set":ps,
                "profile":profile,
                "energy":energy,
                "energy_last":elast
            }

            # ❗ 핵심: 종목별 저장
            result[code]=obj

            # ❗ 즉시 전체 딕셔너리 플러시
            with open(out_path,"w",encoding="utf-8") as f:
                json.dump(_json(result),f,ensure_ascii=False,indent=2)

            print(f"   ✔ 저장완료 → {out_path}")

        except Exception as e:
            print(f"   ❌ 오류 발생: {repr(e)}", flush=True)
            continue

    return result

# ───────────────────────────────────────────
# 메인
# ───────────────────────────────────────────
if __name__=="__main__":
    print("🔄 WkFeedQuant: KR/US 캐시 생성 시작")

    kr_items=get_top_items(limit=60)
    kr_codes=[(n,c) for n,c,_ in kr_items]
    us_items=[(c,c) for c in load_us_list()]

    cfg=[
        ("kr_1m.json","1m",kr_codes,77),
        ("kr_15m.json","15m",kr_codes,77),
        ("kr_1d.json","1d",kr_codes,65),
        ("kr_1wk.json","1wk",kr_codes,65),

        ("us_1m.json","1m",us_items,77),
        ("us_15m.json","15m",us_items,77),
        ("us_1d.json","1d",us_items,65),
        ("us_1wk.json","1wk",us_items,65)
    ]

    for fname,interval,codes,count in cfg:
        out=os.path.join(CACHE_DIR,fname)
        print(f"\n📁 {fname} 생성 중…")
        build_and_flush(interval,codes,fname.startswith("kr"),count,out)

    print("\n✅ 전체 캐시 생성 완료")

