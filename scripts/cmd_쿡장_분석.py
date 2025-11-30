import json, os

path = "cache/all_kr_15m.json"
if not os.path.exists(path):
    print("❌ cache missing:", path)
    exit(1)

with open(path, encoding="utf-8") as f:
    data = json.load(f)

items = []
for code, it in data.items():
    name = it.get("name", code)
    ea = it.get("energies", [])
    last = ea[-1] if ea else 0.0
    items.append((last, code, name))

items.sort(reverse=True)
top = items[:7]

print("🇰🇷 KR 15m Top 7 (MKRW)")
for i, (v, code, name) in enumerate(top, 1):
    print(f"{i}. {name} ({code}) {v:.2f} MKRW")

