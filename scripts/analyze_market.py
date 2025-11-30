#!/usr/bin/env python3
# -*- coding: utf-8 -*-
import os, sys, json

CACHE_DIR = os.path.join(os.getcwd(), "cache")
UNITS = {"kr": "MKRW", "us": "MUSD", "ix": "MIDX"}
TITLES = {"kr": "KR", "us": "US", "ix": "IDX"}
FLAGS = {"kr": "🇰🇷", "us": "🇺🇸", "ix": "📈"}

def _load_json(path):
    if not os.path.exists(path): return {}
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)

def load_market(market):
    name = {"kr": "all_kr_15m.json", "us": "all_us_15m.json", "ix": "all_ix_15m.json"}.get(market)
    if not name: return {}
    path = os.path.join(CACHE_DIR, name)
    return _load_json(path)

def collect_top(market, limit=7):
    data = load_market(market)
    rows = []
    for code, item in data.items():
        energies = item.get("energies") or []
        if not energies: continue
        try:
            val = float(energies[-1])
        except Exception:
            continue
        name = item.get("name") or code
        symbol = item.get("symbol") or code
        rows.append((val, name, code, symbol))
    rows.sort(key=lambda x: x[0], reverse=True)
    return rows[:limit]

def format_market(market, rows):
    flag = FLAGS.get(market, "📈")
    title = TITLES.get(market, market.upper())
    unit = UNITS.get(market, "MIDX")
    if not rows:
        return f"{flag} {title} 15m Top 0 (no data, {unit})"
    out = [f"{flag} {title} 15m Top {len(rows)} (by last energy, {unit})"]
    for i, (val, name, code, symbol) in enumerate(rows, start=1):
        out.append(f"{i}) {name} ({symbol}) {val:.2f} {unit}")
    return "\n".join(out)

def main():
    market = (sys.argv[1] if len(sys.argv) > 1 else "kr").lower()
    if market not in ("kr", "us", "ix", "all"):
        market = "kr"
    targets = ["kr", "us", "ix"] if market == "all" else [market]
    sections = []
    for m in targets:
        rows = collect_top(m)
        sections.append(format_market(m, rows))
    print("\n\n".join(sections))

if __name__ == "__main__":
    main()

