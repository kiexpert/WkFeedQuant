#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""
youtube_digest.py — GHA-side YouTube Subtitle Fetcher (offload from local WkAutoQuant)

Runs yt-dlp sequentially against ~22 Korean stock-market YouTube channels,
downloads Korean auto-subs for the latest non-shorts (and shorts) videos,
parses VTT into plain transcripts, and writes:

  - wavevault/youtube_digest/<YYYY-MM-DD>_<slug>.txt   (one per channel)
  - youtube_digest.json                                 (index manifest)

The companion workflow (.github/workflows/youtube-digest.yml) commits the
results back to the repo so that downstream consumers (WkAutoQuant briefing
bot) can pull pre-fetched transcripts via raw.githubusercontent.com instead
of running yt-dlp locally (which freezes the system on weak hardware).

Usage (CI):
  python scripts/youtube_digest.py                # all channels
  python scripts/youtube_digest.py --channel joodeok
  python scripts/youtube_digest.py --timeout 60   # per-channel timeout (sec)
"""
from __future__ import annotations

import argparse
import datetime
import json
import os
import re
import subprocess
import sys
import tempfile
from pathlib import Path

if sys.stdout and hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")

_REPO_ROOT = Path(__file__).resolve().parent.parent
# NOTE: wavevault/ is .gitignored as a whole, but we negate wavevault/youtube_digest/
# in .gitignore so the per-channel transcripts can ship in commits. Consumers fetch
# via entry["path"] from youtube_digest.json — that path string is the source of truth.
YT_DIGEST_DIR = _REPO_ROOT / "wavevault" / "youtube_digest"
INDEX_PATH = _REPO_ROOT / "youtube_digest.json"

# ============================================================
# Channel Registry — mirror of WkAutoQuant scripts/fetch_youtube_digest.py
# Keep slugs identical so consumers can map 1:1.
# ============================================================
CHANNELS = [
    {"slug": "manju_sugeup", "url": "https://www.youtube.com/@trader_manju/videos", "min_duration": 300},
    {"slug": "manju_sugeup_shorts", "url": "https://www.youtube.com/@trader_manju/shorts", "min_duration": 0},
    {"slug": "joodeok", "url": "https://www.youtube.com/@joodeok/videos", "min_duration": 300},
    {"slug": "joodeok_shorts", "url": "https://www.youtube.com/@joodeok/shorts", "min_duration": 0},
    {"slug": "ha_seunghoon", "url": "https://www.youtube.com/channel/UC7YLvjJf3lDJUQ-TsbWyBjg/videos", "min_duration": 300},
    {"slug": "ha_seunghoon_shorts", "url": "https://www.youtube.com/channel/UC7YLvjJf3lDJUQ-TsbWyBjg/shorts", "min_duration": 0},
    {"slug": "yeomvely", "url": "https://www.youtube.com/@yeomvely/videos", "min_duration": 300},
    {"slug": "yeomvely_shorts", "url": "https://www.youtube.com/@yeomvely/shorts", "min_duration": 0},
    {"slug": "mijueun", "url": "https://www.youtube.com/@mijooeun/videos", "min_duration": 300},
    {"slug": "mijueun_shorts", "url": "https://www.youtube.com/@mijooeun/shorts", "min_duration": 0},
    {"slug": "samprotv", "url": "https://www.youtube.com/@3PROTV/videos", "min_duration": 300},
    {"slug": "samprotv_shorts", "url": "https://www.youtube.com/@3PROTV/shorts", "min_duration": 0},
    {"slug": "hong_in_gi", "url": "https://www.youtube.com/@%EB%8C%80%EC%99%95%EA%B0%9C%EB%AF%B8%ED%99%8D%EC%9D%B8%EA%B8%B0/videos", "min_duration": 300},
    {"slug": "hong_in_gi_shorts", "url": "https://www.youtube.com/@%EB%8C%80%EC%99%95%EA%B0%9C%EB%AF%B8%ED%99%8D%EC%9D%B8%EA%B8%B0/shorts", "min_duration": 0},
    {"slug": "osun_us", "url": "https://www.youtube.com/@futuresnow/videos", "min_duration": 60},
    {"slug": "osun_us_shorts", "url": "https://www.youtube.com/@futuresnow/shorts", "min_duration": 0},
    {"slug": "kim_dante", "url": "https://www.youtube.com/channel/UCKTMvIu9a4VGSrpWy-8bUrQ/videos", "min_duration": 300},
    {"slug": "kim_dante_shorts", "url": "https://www.youtube.com/channel/UCKTMvIu9a4VGSrpWy-8bUrQ/shorts", "min_duration": 0},
    {"slug": "kiwoom_championship", "url": "https://www.youtube.com/@kiwoomchk_trading/videos", "min_duration": 300},
    {"slug": "kiwoom_championship_shorts", "url": "https://www.youtube.com/@kiwoomchk_trading/shorts", "min_duration": 0},
    {"slug": "jusikmijin", "url": "https://www.youtube.com/channel/UCHEWCYP9MbA9RSUiMPvqK9A/videos", "min_duration": 300},
    {"slug": "jusikmijin_shorts", "url": "https://www.youtube.com/channel/UCHEWCYP9MbA9RSUiMPvqK9A/shorts", "min_duration": 0},
    {"slug": "najuda", "url": "https://www.youtube.com/channel/UCu9ndaXUyy9YFzBLIcmy6_A/videos", "min_duration": 300},
    {"slug": "najuda_shorts", "url": "https://www.youtube.com/channel/UCu9ndaXUyy9YFzBLIcmy6_A/shorts", "min_duration": 0},
]

# ============================================================
# VTT parsing
# ============================================================
_VTT_TAG = re.compile(r"<[^>]+>")
_VTT_TS = re.compile(r"^\d{2}:\d{2}:\d{2}\.\d+ --> ")
_VTT_HEADER = re.compile(r"^(WEBVTT|Kind:|Language:)")


def parse_vtt(vtt_path: str) -> str:
    """Strip VTT timing/markup, return plain transcript text (deduped lines)."""
    lines: list[str] = []
    seen: set[str] = set()
    with open(vtt_path, encoding="utf-8", errors="replace") as f:
        for raw in f:
            line = raw.strip()
            if not line or _VTT_HEADER.match(line) or _VTT_TS.match(line):
                continue
            line = _VTT_TAG.sub("", line)
            if "-->" in line:
                continue
            if line in seen:
                continue
            seen.add(line)
            lines.append(line)
    return "\n".join(lines)


# ============================================================
# yt-dlp invocation (use python -m yt_dlp for portability on CI)
# ============================================================
_YTDLP_CMD = [sys.executable, "-m", "yt_dlp"]


def fetch_latest_vtt(
    channel: dict, work_dir: str, timeout: int = 90
) -> tuple[str | None, str | None, str | None]:
    """Returns (vtt_path, video_id, upload_date_yyyymmdd)."""
    slug = channel["slug"]
    out_template = os.path.join(work_dir, f"{slug}.%(ext)s")
    min_dur = int(channel.get("min_duration", 300))

    cmd = [
        *_YTDLP_CMD,
        "--write-auto-subs", "--write-subs",
        "--sub-lang", "ko",
        "--skip-download",
        "--sub-format", "vtt",
        "--playlist-end", "1",
        # Use the TV/web-safari player clients to dodge "Sign in to confirm you're
        # not a bot" on data-center IPs (GitHub Actions runners get flagged a lot).
        # Order matters — yt-dlp tries each until one returns a usable response.
        "--extractor-args", "youtube:player_client=tv,web_safari,android",
        "-o", out_template,
    ]
    if min_dur > 0:
        cmd += ["--match-filter", f"duration > {min_dur}"]
    cmd.append(channel["url"])

    print(f"[FETCH] {slug}: yt-dlp ...", flush=True)
    try:
        r = subprocess.run(
            cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=timeout,
        )
    except subprocess.TimeoutExpired:
        print(f"[TIMEOUT] {slug}: exceeded {timeout}s", flush=True)
        return None, None, None
    if r.returncode != 0:
        # Print full stderr (cap at ~2KB) so the real failure (player decryption,
        # 403, missing format) isn't hidden behind the leading JS-runtime warning.
        err = (r.stderr or "").strip()
        print(f"[ERROR] {slug}: yt-dlp rc={r.returncode}: {err[:2000]}", flush=True)
        return None, None, None

    vtt_path = os.path.join(work_dir, f"{slug}.ko.vtt")
    if not os.path.isfile(vtt_path):
        print(f"[MISS] {slug}: no .ko.vtt produced", flush=True)
        return None, None, None

    # Best-effort metadata fetch (cheap second call). Don't fail the channel if it errors.
    meta_cmd = [
        *_YTDLP_CMD, "--skip-download",
        "--print", "%(id)s|||%(upload_date)s",
        "--playlist-end", "1",
        "--extractor-args", "youtube:player_client=tv,web_safari,android",
    ]
    if min_dur > 0:
        meta_cmd += ["--match-filter", f"duration > {min_dur}"]
    meta_cmd.append(channel["url"])
    vid_id, upload_date = None, None
    try:
        m = subprocess.run(
            meta_cmd, capture_output=True, text=True,
            encoding="utf-8", errors="replace", timeout=45,
        )
        if m.returncode == 0 and "|||" in m.stdout:
            parts = m.stdout.strip().split("|||")
            vid_id = parts[0] or None
            upload_date = parts[1] if len(parts) > 1 else None
    except subprocess.TimeoutExpired:
        pass

    return vtt_path, vid_id, upload_date


# ============================================================
# Main
# ============================================================
def _date_norm(d: str | None) -> str:
    """20260505 → 2026-05-05; pass through if already dashed; fallback to today."""
    if d and len(d) == 8 and d.isdigit():
        return f"{d[:4]}-{d[4:6]}-{d[6:]}"
    if d and len(d) == 10 and d[4] == "-":
        return d
    return datetime.date.today().strftime("%Y-%m-%d")


def process_channel(channel: dict, timeout: int) -> dict:
    slug = channel["slug"]
    with tempfile.TemporaryDirectory(prefix=f"yt_{slug}_") as tmp:
        vtt_path, vid_id, upload_date = fetch_latest_vtt(channel, tmp, timeout=timeout)
        if not vtt_path:
            return {"slug": slug, "ok": False, "reason": "fetch_failed"}
        transcript = parse_vtt(vtt_path)

    date_str = _date_norm(upload_date)
    YT_DIGEST_DIR.mkdir(parents=True, exist_ok=True)
    out = YT_DIGEST_DIR / f"{date_str}_{slug}.txt"
    out.write_text(transcript, encoding="utf-8")
    print(f"[SAVE] {slug}: {out.relative_to(_REPO_ROOT)} ({len(transcript):,} chars)", flush=True)
    return {
        "slug": slug,
        "ok": True,
        "video_id": vid_id,
        "upload_date": date_str,
        "chars": len(transcript),
        "path": str(out.relative_to(_REPO_ROOT)).replace("\\", "/"),
    }


def write_index(results: list[dict], started_iso: str) -> None:
    finished_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    successes = [r for r in results if r.get("ok")]
    failures = [r for r in results if not r.get("ok")]
    index = {
        "schema_version": 1,
        "generated_at": finished_iso,
        "started_at": started_iso,
        "channel_count": len(results),
        "success_count": len(successes),
        "failure_count": len(failures),
        "channels": results,
    }
    INDEX_PATH.write_text(
        json.dumps(index, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"[INDEX] {INDEX_PATH.name} written: {len(successes)}/{len(results)} ok", flush=True)


def main() -> int:
    p = argparse.ArgumentParser(description="GHA YouTube digest fetcher (offload)")
    p.add_argument("--channel", "-c", help="Process a single channel by slug")
    p.add_argument("--timeout", type=int, default=90, help="yt-dlp per-channel timeout (sec)")
    p.add_argument("--list", action="store_true", help="List configured channel slugs")
    args = p.parse_args()

    if args.list:
        for ch in CHANNELS:
            print(ch["slug"])
        return 0

    targets = CHANNELS
    if args.channel:
        targets = [c for c in CHANNELS if c["slug"] == args.channel]
        if not targets:
            print(f"[ERR] unknown slug: {args.channel}", file=sys.stderr)
            return 2

    started_iso = datetime.datetime.now(datetime.timezone.utc).strftime("%Y-%m-%dT%H:%M:%SZ")
    print(f"[START] {started_iso}  channels={len(targets)}  timeout={args.timeout}s", flush=True)

    results: list[dict] = []
    ok = 0
    for ch in targets:
        try:
            r = process_channel(ch, timeout=args.timeout)
        except Exception as e:
            r = {"slug": ch["slug"], "ok": False, "reason": f"exception:{type(e).__name__}:{e}"}
            print(f"[EXC] {ch['slug']}: {e}", flush=True)
        results.append(r)
        if r.get("ok"):
            ok += 1

    write_index(results, started_iso)
    print(f"[DONE] {ok}/{len(targets)} channels succeeded", flush=True)
    # Always rc=0 — partial fetches are normal (channel might have no recent video).
    # CI step still commits whatever was produced.
    return 0


if __name__ == "__main__":
    sys.exit(main())
