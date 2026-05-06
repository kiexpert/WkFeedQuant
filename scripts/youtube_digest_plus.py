#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Extended YouTube digest entrypoint.

Adds compatibility aliases and metrics without rewriting the base fetcher.
"""
from __future__ import annotations

import datetime
import json
import sys

import youtube_digest as yd


EXTRA_CHANNELS = [
    {
        "slug": "stockcrazypeople",
        "url": "https://www.youtube.com/@stockcrazypeople/videos",
        "min_duration": 300,
        "label": "주식에 미친 사람들",
    },
    {
        "slug": "stockcrazypeople_shorts",
        "url": "https://www.youtube.com/@stockcrazypeople/shorts",
        "min_duration": 0,
        "label": "주식에 미친 사람들 쇼츠",
    },
]


def _dedupe_channels(channels: list[dict]) -> list[dict]:
    seen: set[tuple[str, str]] = set()
    out: list[dict] = []
    for ch in channels:
        key = (str(ch.get("slug", "")), str(ch.get("url", "")))
        if key in seen:
            continue
        seen.add(key)
        out.append(ch)
    return out


# Keep existing jusikmijin entries, but add clear stockcrazypeople aliases.
yd.CHANNELS = _dedupe_channels(list(yd.CHANNELS) + EXTRA_CHANNELS)


def write_index_with_shorts(results: list[dict], started_iso: str) -> None:
    finished_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    successes = [r for r in results if r.get("ok")]
    failures = [r for r in results if not r.get("ok")]
    shorts = [r for r in results if str(r.get("slug", "")).endswith("_shorts")]
    shorts_ok = [r for r in shorts if r.get("ok")]
    stockcrazy = [r for r in results if str(r.get("slug", "")).startswith("stockcrazypeople")]
    index = {
        "schema_version": 2,
        "generated_at": finished_iso,
        "started_at": started_iso,
        "channel_count": len(results),
        "success_count": len(successes),
        "failure_count": len(failures),
        "shorts_channel_count": len(shorts),
        "shorts_success_count": len(shorts_ok),
        "stockcrazypeople": stockcrazy,
        "channels": results,
    }
    yd.INDEX_PATH.write_text(json.dumps(index, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    print(
        f"[INDEX] {yd.INDEX_PATH.name} written: "
        f"{len(successes)}/{len(results)} ok; shorts={len(shorts_ok)}/{len(shorts)} ok",
        flush=True,
    )


yd.write_index = write_index_with_shorts


if __name__ == "__main__":
    sys.exit(yd.main())
