#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, json, time, datetime, re
import yfinance as yf

FEEDQUANT_DIR = "cache"
INTERVAL = "1d"   # feedquant 기준 (KR/US 동일)
TOP_N = 100       # 섹터별 집계할 최대 종목 수 (속도 위해)

# ----------------------------------------------------------
# 1) feedquant 캐시 로딩 (전 종목을 메모리에 읽지 않음)
# ----------------------------------------------------------
def load_feedquant_meta():
    base = os.path.join(FEEDQUANT_DIR, "all_us_1d.json")
    base_kr = os.path.join(FEEDQUANT_DIR, "all_kr_1d.json")

    out = {}
    for path in (base, base_kr):
        if not os.path.exists(path):
            continue
        with open(path, "r", encoding="utf-8") as f:
            js = json.load(f)
            for code, item in js.items():
                try:
                    pf = item.get("profile") or {}
                    # 매물대 가장 강한 값 (오늘 거래대금 유사)
                    volume_power = pf.get(0, 0)
                    out[code] = {
                        "name": item.get("name", code),
                        "volume_power": float(volume_power),
                    }
                except:
                    pass
    return out


# ----------------------------------------------------------
# 2) 야후 파이낸스에서 섹터 정보 캐싱
# ----------------------------------------------------------
SECTOR_CACHE = {}

def get_sector(code):
    if code in SECTOR_CACHE:
        return SECTOR_CACHE[code]

    yf_code = f"{re.sub(r'^A', '', code)}.KS" if code.isdigit() else code

    try:
        info = yf.Ticker(yf_code).info
    except Exception:
        SECTOR_CACHE[code] = ("Unknown", "Unknown")
        return SECTOR_CACHE[code]

    sector = info.get("sector") or "Unknown"
    industry = info.get("industry") or "Unknown"

    SECTOR_CACHE[code] = (sector, industry)
    return SECTOR_CACHE[code]


# ----------------------------------------------------------
# 3) 섹터별 집계
# ----------------------------------------------------------
def build_sector_weather(meta):
    scores = {}

    # 거래대금 상위 종목만
    items = sorted(meta.items(), key=lambda x: -x[1]["volume_power"])
    items = items[:TOP_N]

    for code, item in items:
        sector, industry = get_sector(code)
        volp = item["volume_power"]

        if sector not in scores:
            scores[sector] = {"energy": 0, "count": 0, "leaders": []}

        scores[sector]["energy"] += volp
        scores[sector]["count"] += 1
        scores[sector]["leaders"].append({"code": code, "power": volp})

    # 섹터별 정렬
    for sec in scores:
        scores[sec]["leaders"] = sorted(
            scores[sec]["leaders"], key=lambda x: -x["power"]
        )[:5]

    # 전체 섹터 정렬 후 반환
    ordered = dict(
        sorted(scores.items(), key=lambda x: -x[1]["energy"])
    )
    return ordered


# ----------------------------------------------------------
# 4) 메인
# ----------------------------------------------------------
def main():
    print("▶ Loading feedquant metadata…")
    meta = load_feedquant_meta()

    print(f"▶ Loaded {len(meta)} cached items")

    print("▶ Building sector weather…")
    weather = build_sector_weather(meta)

    print("\n=== 📡 Sector Weather (Light Version) ===")
    now = datetime.datetime.utcnow().isoformat()

    out = {
        "generated_at": now,
        "sector_weather": weather
    }

    print(json.dumps(out, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
