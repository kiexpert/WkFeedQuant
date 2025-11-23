#!/usr/bin/env bash
set -euo pipefail

# ────────────────────────────────
# 📌 기본 환경 구성
# ────────────────────────────────
setup_path_env() {
    local VAR="$1"
    local VALUE="$2"
    export "${VAR}=${VALUE}"
    mkdir -p "$VALUE"
    [[ -n "${GITHUB_ENV:-}" ]] && echo "${VAR}=${VALUE}" >> "$GITHUB_ENV"
    echo "[env] $VAR = $VALUE"
}

run_gh_cache() {
    local stderr_file
    stderr_file="$(mktemp)"
    local output=""
    local exit_code=0

    if ! output="$("$@" 2>"$stderr_file")"; then
        exit_code=$?
    fi

    if [[ $exit_code -eq 0 ]]; then
        [[ -s "$stderr_file" ]] && { echo "gh stderr:"; cat "$stderr_file"; }
        rm -f "$stderr_file"
        echo "$output"
        return 0
    fi

    local err=""
    [[ -s "$stderr_file" ]] && err="$(cat "$stderr_file")"
    echo "❌ gh command failed: $*"
    echo "$err"
    rm -f "$stderr_file"
    return 0
}

# ────────────────────────────────
# 🔎 최신 캐시 탐색
# ────────────────────────────────
setup_path_env "WK_CACHE_DIR" "${HOME}/.wk-cache"
setup_path_env "PYTHONUSERBASE" "${HOME}/.wk-cache/site"
setup_path_env "PIP_CACHE_DIR"   "${HOME}/.wk-cache/pip"

export PYTHONPATH="$(pwd)"
[[ -n "${GITHUB_ENV:-}" ]] && echo "PYTHONPATH=$(pwd)" >> "$GITHUB_ENV"
echo "[env] PYTHONPATH=$(pwd)"

echo "🧭 Searching wk-cache entries..."

cache_raw="$(run_gh_cache gh cache list --limit 100 --sort created_at --order desc)"

: > cache_list.txt
echo "$cache_raw" | grep 'wk-cache' > cache_list.txt || true

latest="none"
if [[ -s cache_list.txt ]]; then
    latest=$(head -n 1 cache_list.txt | awk '{print $2}')
    echo "🆕 Latest wk-cache key = $latest"
else
    echo "ℹ️ No cache found. First run."
fi

export WK_CACHE_KEY="$latest"
[[ -n "${GITHUB_ENV:-}" ]] && echo "WK_CACHE_KEY=$latest" >> "$GITHUB_ENV"

# ────────────────────────────────
# 🧹 최신 캐시 1개 제외 전체 삭제 (페이징)
# ────────────────────────────────
delete_all_except_latest() {
    echo "🧹 Removing all wk-cache entries EXCEPT latest ($latest)..."

    # 🔥 gh cache delete 실패해도 전체 스크립트 죽지 않도록 set +e
    set +e

    local page=1
    while true; do
        raw="$(gh cache list --limit 100 --page "$page" --sort created_at --order desc 2>/dev/null)"
        [[ -z "$raw" ]] && break

        echo "$raw" | grep 'wk-cache' | while IFS= read -r line; do
            id="$(echo "$line" | awk '{print $1}')"
            key="$(echo "$line" | awk '{print $2}')"

            [[ "$id" =~ ^[0-9]+$ ]] || continue

            if [[ "$key" == "$latest" ]]; then
                echo "🔒 KEEP latest → $key"
                continue
            fi

            echo "🗑 DELETE id=$id key=$key"
            gh cache delete "$id" || echo "⚠️ delete failed for $id"
        done

        ((page++))
    done

    # 🔒 다시 엄격모드 복구
    set -e

    echo "🎉 Cache cleanup completed (latest preserved)"
}

delete_all_except_latest

# ────────────────────────────────
# 🕓 다음 캐시 키 생성
# ────────────────────────────────
run_id="${GITHUB_RUN_ID:-local}"
kst_timestamp="$(date -u -d '+9 hours' '+%Y-%m-%d_%H%M')"
next_key="wk-cache-kr-${kst_timestamp}-${run_id}"

[[ -n "${GITHUB_ENV:-}" ]] && echo "WK_CACHE_NEXT_KEY=${next_key}" >> "$GITHUB_ENV"
echo "🕓 Next key: $next_key"

echo "::notice title=CacheFinder::Latest=${latest}, Next=${next_key}"
echo "✅ Completed — exit 0"
exit 0
