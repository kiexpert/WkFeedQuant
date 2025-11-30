#!/usr/bin/env python3
import json, sys, time, os

TARGET = sys.argv[1]
cache_dir = os.path.join(os.getcwd(), "cache")

fn = f"all_kr_15m.json" if TARGET == "KR" else f"all_us_15m.json"
path = os.path.join(cache_dir, fn)

with open(path, "r", encoding="utf-8") as f:
    data = json.load(f)

items = []
for code, item in data.items():
    try:
        energies = item.get("energies", [])
        if not energies: continue
        last = float(energies[-1])
        items.append((item["name"], code, last))
    except Exception:
        continue

items.sort(key=lambda x: x[2], reverse=True)
top7 = items[:7]

unit = "MKRW" if TARGET == "KR" else "MUSD"
mul = 1000 if TARGET == "KR" else 1

print(f"Top 7 by last energy ({unit})")
time.sleep(0.8)

for i, (name, code, val) in enumerate(top7, start=1):
    out = f"{i}. {name} ({code}) {val*mul:,.2f} {unit}"
    print(out)
    time.sleep(0.5)
