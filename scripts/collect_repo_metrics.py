#!/usr/bin/env python3
# -*- coding: utf-8 -*-
"""Collect GitHub repository metrics and push them to a private repo.

Designed to run from WkFeedQuant GitHub Actions, but it does NOT commit metrics
back to WkFeedQuant because that repo is public. Metrics are written only to the
configured private target repo, normally kiexpert/WkAutoQuant.

Collected per repo when the token has permission:
- repository metadata: visibility, size, stars, forks, watchers, open issues
- traffic views / clones, including daily breakdown
- popular paths / popular referrers
- contributor/participation/code-frequency stats when available
- recent workflow run summary when available

GitHub traffic APIs expose approximately the last 14 days only.
"""
from __future__ import annotations

import argparse
import base64
import datetime as dt
import json
import os
import time
from pathlib import Path
from typing import Any
from urllib.parse import quote

import urllib.error
import urllib.request

API = "https://api.github.com"
UTC = dt.timezone.utc


class GH:
    def __init__(self, token: str):
        if not token:
            raise SystemExit("GH_PAT is required")
        self.token = token

    def request(self, method: str, path: str, *, data: Any = None, accept: str = "application/vnd.github+json") -> tuple[int, Any, dict]:
        url = path if path.startswith("http") else API + path
        body = None
        headers = {
            "Accept": accept,
            "Authorization": f"Bearer {self.token}",
            "X-GitHub-Api-Version": "2022-11-28",
            "User-Agent": "WkFeedQuant-metrics-collector",
        }
        if data is not None:
            body = json.dumps(data, ensure_ascii=False).encode("utf-8")
            headers["Content-Type"] = "application/json"
        req = urllib.request.Request(url, data=body, headers=headers, method=method)
        try:
            with urllib.request.urlopen(req, timeout=30) as r:
                raw = r.read().decode("utf-8", errors="replace")
                parsed = json.loads(raw) if raw else None
                return r.status, parsed, dict(r.headers)
        except urllib.error.HTTPError as e:
            raw = e.read().decode("utf-8", errors="replace")
            try:
                parsed = json.loads(raw) if raw else {"message": e.reason}
            except Exception:
                parsed = {"message": raw or e.reason}
            return e.code, parsed, dict(e.headers)

    def get(self, path: str) -> tuple[int, Any, dict]:
        return self.request("GET", path)

    def put(self, path: str, data: Any) -> tuple[int, Any, dict]:
        return self.request("PUT", path, data=data)

    def list_pages(self, path: str, *, limit_pages: int = 20) -> list[Any]:
        out: list[Any] = []
        next_path = path
        for _ in range(limit_pages):
            code, data, headers = self.get(next_path)
            if code >= 400:
                raise RuntimeError(f"GET {next_path} failed: {code} {data}")
            if isinstance(data, list):
                out.extend(data)
            else:
                out.append(data)
            link = headers.get("Link", "")
            nxt = None
            for part in link.split(","):
                if 'rel="next"' in part:
                    left = part.split(";", 1)[0].strip()
                    nxt = left[1:-1] if left.startswith("<") and left.endswith(">") else None
            if not nxt:
                break
            next_path = nxt
        return out


def _now() -> dt.datetime:
    return dt.datetime.now(UTC)


def _safe_slug(full_name: str) -> str:
    return full_name.replace("/", "__")


def _compact_repo(r: dict) -> dict:
    return {
        "full_name": r.get("full_name"),
        "name": r.get("name"),
        "owner": (r.get("owner") or {}).get("login"),
        "private": r.get("private"),
        "visibility": r.get("visibility"),
        "archived": r.get("archived"),
        "disabled": r.get("disabled"),
        "fork": r.get("fork"),
        "default_branch": r.get("default_branch"),
        "html_url": r.get("html_url"),
        "language": r.get("language"),
        "size_kb": r.get("size"),
        "stargazers_count": r.get("stargazers_count"),
        "watchers_count": r.get("watchers_count"),
        "subscribers_count": r.get("subscribers_count"),
        "forks_count": r.get("forks_count"),
        "open_issues_count": r.get("open_issues_count"),
        "network_count": r.get("network_count"),
        "created_at": r.get("created_at"),
        "updated_at": r.get("updated_at"),
        "pushed_at": r.get("pushed_at"),
        "license": (r.get("license") or {}).get("spdx_id"),
        "topics": r.get("topics") or [],
    }


def _get_or_error(gh: GH, path: str) -> dict:
    code, data, _ = gh.get(path)
    if code >= 400:
        return {"ok": False, "status": code, "error": data}
    return {"ok": True, "data": data}


def collect_repo(gh: GH, full_name: str, *, include_heavy: bool = True) -> dict:
    owner_repo = quote(full_name, safe="/")
    code, repo, _ = gh.get(f"/repos/{owner_repo}")
    if code >= 400:
        return {"repo": full_name, "ok": False, "status": code, "error": repo}

    doc: dict[str, Any] = {
        "repo": full_name,
        "ok": True,
        "collected_at": _now().isoformat(timespec="seconds"),
        "meta": _compact_repo(repo),
        "traffic": {},
        "activity": {},
    }

    for key, path in {
        "views": f"/repos/{owner_repo}/traffic/views?per=day",
        "clones": f"/repos/{owner_repo}/traffic/clones?per=day",
        "popular_paths": f"/repos/{owner_repo}/traffic/popular/paths",
        "popular_referrers": f"/repos/{owner_repo}/traffic/popular/referrers",
    }.items():
        doc["traffic"][key] = _get_or_error(gh, path)
        time.sleep(0.15)

    if include_heavy:
        # These endpoints can return 202 while GitHub computes stats. Store that honestly.
        for key, path in {
            "contributors": f"/repos/{owner_repo}/stats/contributors",
            "participation": f"/repos/{owner_repo}/stats/participation",
            "code_frequency": f"/repos/{owner_repo}/stats/code_frequency",
            "commit_activity": f"/repos/{owner_repo}/stats/commit_activity",
        }.items():
            doc["activity"][key] = _get_or_error(gh, path)
            time.sleep(0.20)

    # Small summaries for quick briefing reads.
    views = doc["traffic"].get("views", {})
    clones = doc["traffic"].get("clones", {})
    vdata = views.get("data") if views.get("ok") else {}
    cdata = clones.get("data") if clones.get("ok") else {}
    doc["summary"] = {
        "views_count_14d": (vdata or {}).get("count", 0),
        "views_uniques_14d": (vdata or {}).get("uniques", 0),
        "clones_count_14d": (cdata or {}).get("count", 0),
        "clones_uniques_14d": (cdata or {}).get("uniques", 0),
        "stars": repo.get("stargazers_count"),
        "forks": repo.get("forks_count"),
        "watchers": repo.get("watchers_count"),
        "open_issues": repo.get("open_issues_count"),
        "size_kb": repo.get("size"),
        "private": repo.get("private"),
        "visibility": repo.get("visibility"),
    }
    return doc


def list_accessible_repos(gh: GH, owner: str | None = None) -> list[dict]:
    repos = gh.list_pages("/user/repos?per_page=100&affiliation=owner,collaborator,organization_member&sort=updated", limit_pages=20)
    if owner:
        repos = [r for r in repos if (r.get("owner") or {}).get("login", "").lower() == owner.lower()]
    return repos


def write_outputs(out_dir: Path, payload: dict) -> None:
    out_dir.mkdir(parents=True, exist_ok=True)
    (out_dir / "traffic_summary.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    history = out_dir / "history"
    history.mkdir(parents=True, exist_ok=True)
    stamp = _now().strftime("%Y%m%d_%H%M%S")
    (history / f"{stamp}.json").write_text(json.dumps(payload, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")
    per_repo = out_dir / "repos"
    per_repo.mkdir(parents=True, exist_ok=True)
    for row in payload["repos"]:
        name = _safe_slug(row.get("repo", "unknown"))
        (per_repo / f"{name}.json").write_text(json.dumps(row, ensure_ascii=False, indent=2) + "\n", encoding="utf-8")


def put_file(gh: GH, repo: str, path: str, content: str, message: str, branch: str = "main") -> None:
    owner_repo = quote(repo, safe="/")
    path_q = quote(path)
    sha = None
    code, existing, _ = gh.get(f"/repos/{owner_repo}/contents/{path_q}?ref={quote(branch)}")
    if code == 200 and isinstance(existing, dict):
        sha = existing.get("sha")
    elif code not in (404,):
        raise RuntimeError(f"read content failed {repo}/{path}: {code} {existing}")
    body = {
        "message": message,
        "content": base64.b64encode(content.encode("utf-8")).decode("ascii"),
        "branch": branch,
    }
    if sha:
        body["sha"] = sha
    code, data, _ = gh.put(f"/repos/{owner_repo}/contents/{path_q}", body)
    if code >= 400:
        raise RuntimeError(f"put content failed {repo}/{path}: {code} {data}")


def push_to_target(gh: GH, target_repo: str, prefix: str, payload: dict, branch: str = "main") -> None:
    stamp = _now().strftime("%Y%m%d_%H%M%S")
    msg = f"chore(repo-metrics): refresh GitHub traffic {stamp} [skip ci]"
    summary = json.dumps(payload, ensure_ascii=False, indent=2) + "\n"
    put_file(gh, target_repo, f"{prefix}/traffic_summary.json", summary, msg, branch)
    put_file(gh, target_repo, f"{prefix}/history/{stamp}.json", summary, msg, branch)
    for row in payload["repos"]:
        name = _safe_slug(row.get("repo", "unknown"))
        put_file(gh, target_repo, f"{prefix}/repos/{name}.json", json.dumps(row, ensure_ascii=False, indent=2) + "\n", msg, branch)
        time.sleep(0.10)


def build_payload(gh: GH, owner: str, include_heavy: bool, limit: int | None = None) -> dict:
    repos = list_accessible_repos(gh, owner=owner)
    if limit:
        repos = repos[:limit]
    rows = []
    for i, r in enumerate(repos, 1):
        full_name = r.get("full_name")
        print(f"[collect] {i}/{len(repos)} {full_name}", flush=True)
        rows.append(collect_repo(gh, full_name, include_heavy=include_heavy))
        time.sleep(0.25)

    ok_rows = [r for r in rows if r.get("ok")]
    totals = {
        "repo_count": len(rows),
        "ok_repo_count": len(ok_rows),
        "views_count_14d": sum((r.get("summary") or {}).get("views_count_14d") or 0 for r in ok_rows),
        "views_uniques_14d": sum((r.get("summary") or {}).get("views_uniques_14d") or 0 for r in ok_rows),
        "clones_count_14d": sum((r.get("summary") or {}).get("clones_count_14d") or 0 for r in ok_rows),
        "clones_uniques_14d": sum((r.get("summary") or {}).get("clones_uniques_14d") or 0 for r in ok_rows),
        "stars": sum((r.get("summary") or {}).get("stars") or 0 for r in ok_rows),
        "forks": sum((r.get("summary") or {}).get("forks") or 0 for r in ok_rows),
        "public_repo_count": sum(1 for r in ok_rows if not (r.get("summary") or {}).get("private")),
        "private_repo_count": sum(1 for r in ok_rows if (r.get("summary") or {}).get("private")),
    }
    top_views = sorted(ok_rows, key=lambda r: (r.get("summary") or {}).get("views_count_14d") or 0, reverse=True)[:15]
    top_clones = sorted(ok_rows, key=lambda r: (r.get("summary") or {}).get("clones_count_14d") or 0, reverse=True)[:15]
    return {
        "schema_version": 1,
        "generated_at": _now().isoformat(timespec="seconds"),
        "owner": owner,
        "note": "GitHub traffic APIs generally cover the last ~14 days. Stored in private target repo only.",
        "totals": totals,
        "top_views_14d": [{"repo": r.get("repo"), **(r.get("summary") or {})} for r in top_views],
        "top_clones_14d": [{"repo": r.get("repo"), **(r.get("summary") or {})} for r in top_clones],
        "repos": rows,
    }


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--owner", default=os.getenv("METRICS_OWNER", "kiexpert"))
    ap.add_argument("--target-repo", default=os.getenv("METRICS_TARGET_REPO", "kiexpert/WkAutoQuant"))
    ap.add_argument("--target-prefix", default=os.getenv("METRICS_TARGET_PREFIX", "wavevault/github_traffic"))
    ap.add_argument("--target-branch", default=os.getenv("METRICS_TARGET_BRANCH", "main"))
    ap.add_argument("--out-dir", default="_repo_metrics")
    ap.add_argument("--light", action="store_true", help="skip heavier stats endpoints")
    ap.add_argument("--limit", type=int, default=0)
    ap.add_argument("--no-push", action="store_true")
    args = ap.parse_args()

    token = os.getenv("GH_PAT") or os.getenv("GITHUB_TOKEN") or ""
    gh = GH(token)
    payload = build_payload(gh, args.owner, include_heavy=not args.light, limit=args.limit or None)
    write_outputs(Path(args.out_dir), payload)
    print("[summary]", json.dumps(payload["totals"], ensure_ascii=False), flush=True)
    if not args.no_push:
        push_to_target(gh, args.target_repo, args.target_prefix.strip("/"), payload, branch=args.target_branch)
        print(f"[push] wrote metrics to {args.target_repo}:{args.target_prefix}", flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
