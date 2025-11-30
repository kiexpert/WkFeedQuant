#!/usr/bin/env python3
import json, sys, time, os

TARGET = sys.argv[1]
cache_dir = os.path.join(os.getcwd(), "cache")
fn = "all_kr_15m.json" if TARGET == "KR" else "all_us_15m.json"
path = os.path.join(cache_dir, fn)

print(f"📂 Loading {fn}")
time.sleep(0.6)

if not os.path.exists(path):
    print("⚠️ 데이터 파일 없음 :", path)
    sys.exit(1)

try:
    with open(path, "r", encoding="utf-8") as f:
        data = json.load(f)
except Exception as e:
    print("⚠️ JSON 파싱 실패:", repr(e))
    sys.exit(1)

items = []
for code, item in data.items():
    try:
        last = float(item.get("energies", [])[-1])
        items.append((item["name"], code, last))
    except:
        continue

if not items:
    print("⚠️ 에너지 데이터 없음")
    sys.exit(1)

items.sort(key=lambda x: x[2], reverse=True)
top7 = items[:7]

unit = "MKRW" if TARGET == "KR" else "MUSD"
mul = 1000 if TARGET == "KR" else 1

print(f"Top 7 by last energy ({unit})")
time.sleep(0.6)

for i, (name, code, val) in enumerate(top7, start=1):
    print(f"{i}. {name} ({code}) {val*mul:,.2f} {unit}")
    time.sleep(0.3)

sys.exit(0)
