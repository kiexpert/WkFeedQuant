#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, re, json, time, datetime, requests
import pandas as pd
import numpy as np
from bs4 import BeautifulSoup
import yfinance as yf
CACHE_DIR = os.path.join(os.getcwd(), "cache")
os.makedirs(CACHE_DIR, exist_ok = True)
def _log(msg): print(msg, flush = True)
def _save_json(path, obj):
    os.makedirs(os.path.dirname(path), exist_ok = True)
    with open(path, "w", encoding = "utf-8") as f:
        json.dump(obj, f, indent = None, ensure_ascii = False)
def get_top_kr(limit = 33, retry = 0):
    url = "https://finance.naver.com/sise/sise_quant.naver"
    headers = {"User-Agent": "Mozilla/5.0", "Accept-Language": "ko-KR,en;q=0.8"}
    try:
        r = requests.get(url, headers = headers, timeout = 5)
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
            href = a.get("href", "")
            if "code=" not in href:
                continue
            code = "A" + href.split("code=")[-1][:6]
            try: pct = float(tds[2])
            except: pct = 0.0
            try: val = float(tds[6]) / 100.0
            except: val = 0.0
            out.append((name, code, pct, val))
        out.sort(key = lambda x: x[3], reverse = True)
        return out[:limit]
    except Exception:
        if retry < 2:
            time.sleep(3)
            return get_top_kr(limit, retry + 1)
        return []
BASE_US = [
    "SPY","QQQ","DIA","IWM","VTI",
    "TQQQ","SOXL","UPRO","TECL","FNGU",
    "SQQQ","SOXS","SDOW",
    "UVXY","VIXY","SVXY",
    "XLF","XLE","XLK","SMH",
    "ARKK","KWEB","LABU","LABD",
    "TSLA","AAPL","NVDA","AMZN","MSFT","META","AMD"
]
def get_top_us(limit = 30):
    values = []
    for t in BASE_US:
        try:
            tk = yf.Ticker(t)
            info = tk.fast_info or {}
            full = tk.info or {}
            price = info.get("last_price") or full.get("previousClose") or full.get("lastPrice")
            volume = info.get("last_volume") or full.get("volume")
            if not price or not volume:
                continue
            val = float(price) * float(volume)
            name = full.get("longName") or full.get("shortName") or t
            values.append({"ticker": t, "value_b": val / 1e9, "name": name})
        except:
            continue
    df = pd.DataFrame(values)
    if df.empty:
        return []
    df = df.sort_values("value_b", ascending = False)
    return df.head(limit).to_dict("records")

_WK_OHLC_TOK = re.compile(r'(open|high|low|close|volume)', re.I)

def wk_ultra_flatten_ohlcv(df):
    if df is None or len(df) == 0: return df
    # 1) 플랫 컬럼명
    flat = ["_".join([str(x) for x in c if x not in (None,""," ")]) if isinstance(c,tuple) else str(c) for c in df.columns]
    df = df.copy(); df.columns = flat; m = {}
    # 2) OHLCV 매핑
    for c in df.columns:
        k = _WK_OHLC_TOK.search(c.lower())
        if k: m[k.group(1).lower()] = c
    if len(m) < 5: raise KeyError("OHLCV columns not detected")
    # 3) 타임스탬프 변환
    ts = pd.to_datetime(df.index, utc=True, errors="coerce")
    ts = (ts.view("int64") // 1_000_000).astype("int64")
    # 4) 숫자 변환
    num = lambda x: pd.to_numeric(x, errors="coerce")
    o = num(df[m["open"]]).astype("float64")
    h = num(df[m["high"]]).astype("float64")
    l = num(df[m["low"]]).astype("float64")
    c = num(df[m["close"]]).astype("float64")
    v = num(df[m["volume"]]).astype("int64")
    # 5) 길이 불일치 보정
    ml = max(len(o), len(h), len(l), len(c), len(v))
    reidx = lambda x: x.reindex(range(ml))
    o, h, l, c, v = map(reidx, (o, h, l, c, v))
    # 6) high 전체 NaN 방어 (low → close → open 순 fallback)
    if h.isna().all():
        if not l.isna().all(): h = l.copy()
        elif not c.isna().all(): h = c.copy()
        elif not o.isna().all(): h = o.copy()
    # 7) 소수점 정리
    r2 = lambda x: x.round(2)
    o, h, l, c = map(r2, (o, h, l, c))
    return pd.DataFrame({"ts": ts, "open": o, "high": h, "low": l, "close": c, "volume": v})
    
def ensure_safe_volume(df, interval):
    import math
    if df is None or df.empty: return df
    mins = {"1m":1,"15m":15,"1d":390,"1wk":390*5}.get(interval,15)
    fb = mins * 60000
    vv = []
    for x in df["volume"]:
        try: xx = float(x)
        except: xx = 0.0
        # NaN, 음수, 0 → fallback
        if (not math.isfinite(xx)) or xx <= 0:
            vv.append(fb)
            continue
        iv = int(xx)
        if iv < 1: iv = fb
        vv.append(iv)
        fb = iv
    df = df.copy()
    df["volume"] = vv
    return df
    
def collect_profile(df):
    import math
    pf = {}
    o = df["open"].values; h = df["high"].values
    l = df["low"].values;  c = df["close"].values
    v = df["volume"].values
    # ── 1) 막봉 고가로 자동 스텝 계산
    last_high = h[-1]
    digits = int(math.floor(math.log10(last_high)))
    step = max(0.01, 10 ** (digits - 3))
    # ── 2) 가중치
    w_o, w_l, w_h, w_c = 0.2, 0.3, 0.3, 0.2
    # ── 3) 매물대 계산
    for i in range(len(c)):
        vv = v[i] if v[i] > 0 else 10
        for price, w in ((o[i], w_o), (l[i], w_l), (h[i], w_h), (c[i], w_c)):
            slot = int((price + (0.5 * step)) / step)
            pf[slot] = pf.get(slot, 0) + int(round(vv * w))
    # ── 4) 정렬 + 실제가격 복원
    pf_sorted = {round(slot * step, 2): vol for slot, vol in sorted(pf.items(), key=lambda x: x[1], reverse=True)}
    pset = set(pf_sorted.keys())
    return pf_sorted, pset
    
def compute_energy_array(df):
    closes = df["close"].astype(float).values
    vols = df["volume"].astype(float).values
    n = len(closes)
    ea = (closes * vols) * 1e-6
    ea = np.round(ea, 3)
    if n < 2:
        last = float(ea[-1]) if n > 0 else None
        return ea.tolist(), last
    v0, v1 = vols[-2], vols[-1]
    last = float(ea[-2] * (v1 / v0)) if v0 > 0 else float(ea[-2])
    return ea.tolist(), round(last, 3)
def load_ohlcv(code, interval = "15m", count = 77):
    yf_code = f"{code[1:]}.KS" if re.match(r"A\d{6}", code) else code
    period = "5d" if interval.endswith("m") else "77d"
    raw = yf.download(yf_code, period = period, interval = interval,
                      progress = False, auto_adjust = True)
    if raw is None or raw.empty:
        return None, None
    raw = raw.tail(count)
    df = wk_ultra_flatten_ohlcv(raw)
    df = ensure_safe_volume(df, interval)
    ts = pd.to_datetime(df["ts"], unit = "ms", errors = "coerce").dropna()
    if len(ts) >= 2:
        s = ts.iloc[-1]
        d = s - ts.iloc[-2]
    else:
        s = ts.iloc[-1] if len(ts) == 1 else pd.Timestamp.utcnow()
        d = datetime.timedelta(minutes = 15)
    e = s + d
    return df, {
        "symbol": yf_code,
        "rows": len(df),
        "last_bar_start": s.isoformat(),
        "last_bar_end": e.isoformat()
    }

def build_cache_item(code, name, interval, count=77):
    df, meta = load_ohlcv(code, interval, count)
    if df is None or df.empty:
        return None
    pf, pset = collect_profile(df)
    ea, ea_last = compute_energy_array(df)
    symbol = meta.get("symbol")
    rows = meta.get("rows")
    lbs = meta.get("last_bar_start")
    lbe = meta.get("last_bar_end")
    # 저장 시간
    saved = datetime.datetime.utcnow().isoformat()
    return {
        "name": name,
        "symbol": symbol,
        "interval": interval,
        "rows": rows,
        "saved_at": saved,
        "last_bar_start": lbs,
        "last_bar_end": lbe,
        "profile": pf,
        "price_set": sorted(list(pset)),
        "energies": ea,
        # "energy_last": ea_last, # 에너지 배열 마지막값~
        "ohlcv": df.to_dict("list"),
    }

# ============================================================
# 지표 강제 포함용 세트 (모두 미국 취급)
# ============================================================
FORCED_US = {
    # 미국 본체
    "^NDX":"NASDAQ 100 지수","^DJI":"다우 지수","^GSPC":"S&P500 지수","^VIX":"CBOE VIX",
    # 변동성
    "UVXY":"Ultra VIX Short-Term 2x","VIXY":"VIX Short-Term","VIXM":"VIX Mid-Term","SVXY":"Short VIX Inverse",
    # 3배 레버리지
    "TQQQ":"NASDAQ 3x","UPRO":"S&P500 3x","SOXL":"Semiconductor 3x","SPXL":"S&P500 3x alt",
    "FNGU":"FANG+ 3x","TECL":"Tech 3x",
    # 3배 인버스
    "SQQQ":"NASDAQ 3x Inv","SOXS":"Semiconductor 3x Inv","SPXS":"S&P500 3x Inv","SDOW":"DOW 3x Inv",
    "LABD":"Bio 3x Inv","TZA":"Russell2000 3x Inv",
    # 보유·특수
    "BITX":"Bitcoin 2x","CRCL":"Circle","MSTU":"MSTR Target 2x","MSTX":"MSTR 2x Long",
    "NVDL":"NVIDIA 2x","PLTU":"Palantir 2x","PONY":"Pony AI","QCOM":"Qualcomm","QUBT":"QUBT","TSLL":"Tesla 2x",
    # 선물·환율
    "CL=F":"WTI Oil","BZ=F":"Brent Oil","GC=F":"Gold","SI=F":"Silver","HG=F":"Copper",
    "ES=F":"S&P500 Futures","NQ=F":"NASDAQ Futures","YM=F":"DOW Futures","RTY=F":"R2000 Futures",
    "DX-Y.NYB":"Dollar Index","EURUSD=X":"EUR/USD","JPY=X":"USD/JPY","USDKRW=X":"USD/KRW",
    # 글로벌 지수
    "^N225":"Nikkei225","^HSI":"HSI","^FCHI":"CAC40","^GDAXI":"DAX",
    # 국내 지수(미국 티커로 취급)
    "^KS11":"KOSPI","^KQ11":"KOSDAQ"
}

# ============================================================
# 주기별 캐시 저장
# ============================================================
def run_feedquant():
    _log("▶ WkFeedQuant 시작")

    # 기존
    kr_list = get_top_kr(limit=33)
    us_list = get_top_us(limit=33)
    
    # -----------------------------------------
    # ★ 미국 지표 강제 포함: (ticker, name) 형태로 us_list 확장
    # -----------------------------------------
    forced = [(FORCED_US[k], k) for k in FORCED_US]  # (name, ticker)
    # 기존 us_list 형식과 맞추기 위해 dict 생성
    merged = {it["ticker"]: it for it in us_list}
    for name, code in forced:
        merged.setdefault(code, {"ticker":code, "name":name})
    us_list = list(merged.values())

    _log(f"🇰🇷 KR {len(kr_list)}개 / 🇺🇸 US {len(us_list)}개 수집 완료")

    # 주기별 딕셔너리 준비
    buckets_kr = {"1m": {}, "15m": {}, "1d": {}, "1wk": {}}
    buckets_us = {"1m": {}, "15m": {}, "1d": {}, "1wk": {}}

    # KR
    for name, code, pct, val in kr_list:
        pure = code[1:]  # "A000660" → "000660"
        for iv in ("1m", "15m", "1d", "1wk"):
            item = build_cache_item(code, name, iv)
            if item:
                if not buckets_kr[iv] or not pure.isalnum(): _log(json.dumps(item, indent=None))
                buckets_kr[iv][pure] = item
                _log(f"  ✔ KR {code} {iv}")

    # US
    for it in us_list:
        code = it["ticker"]
        name = it["name"]
        for iv in ("1m", "15m", "1d", "1wk"):
            item = build_cache_item(code, name, iv)
            if item:
                if not buckets_us[iv] or not pure.isalnum(): _log(json.dumps(item, indent=None))
                buckets_us[iv][code] = item
                _log(f"  ✔ US {code} {iv}")

    # 파일 저장 (주기별)
    for iv in ("1m", "15m", "1d", "1wk"):
        _save_json(os.path.join(CACHE_DIR, f"all_kr_{iv}.json"), buckets_kr[iv])
        _save_json(os.path.join(CACHE_DIR, f"all_us_{iv}.json"), buckets_us[iv])

    _log("✅ 모든 캐시 저장 완료")
    
if __name__ == "__main__":
    run_feedquant()
