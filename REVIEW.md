# WkFeedQuant 종합검토 보고서

> 검토일: 2026-02-16
> 대상: WkFeedQuant 전체 코드베이스

---

## 1. 프로젝트 개요

**WkFeedQuant**는 한국/미국 주식시장의 실시간 OHLCV 데이터를 수집하고, 매물대(Volume Profile) 및 에너지(Price × Volume) 지표를 계산하여 섹터별 분석 결과를 텔레그램으로 브리핑하는 자동화 시스템이다.

| 구성요소 | 파일 | 역할 |
|---------|------|------|
| 데이터 수집 | `wk_feed_quant.py` | OHLCV 수집, 매물대/에너지 계산, 캐시 저장 |
| 섹터 분석 | `sector_weather.py` | 섹터별 에너지 집계 및 변화율 표시 |
| 브리핑 전송 | `send_briefing.py` | 텍스트/음성 브리핑 생성 및 텔레그램 전송 |
| 텔레그램 API | `telegram_notify.py` | 텔레그램 메시지/음성 전송 래퍼 |
| 스크립트 | `scripts/` | GitHub Issue 기반 명령 처리, 시장별 Top N 분석 |
| CI/CD | `.github/workflows/` | 10분 주기 캐시, 1시간 주기 브리핑, Issue 명령 |

**기술 스택**: Python 3.11, yfinance, BeautifulSoup4, pandas, numpy, gTTS, GitHub Actions, Telegram Bot API

---

## 2. 아키텍처 검토

### 2.1 장점

- **단순하고 효과적인 구조**: 4개의 핵심 Python 파일이 각자 명확한 역할을 담당하여 이해하기 쉽다.
- **GitHub Actions 활용**: 별도 서버 없이 cron 기반 자동화를 구현했다.
- **다중 시간프레임 지원**: 1m, 15m, 1d, 1wk 4개 주기의 데이터를 일관된 구조로 저장한다.
- **강제 종목(FORCED) 패턴**: 동적 상위 종목 + 고정 관심종목을 병합하는 방식이 실용적이다.

### 2.2 구조적 우려

- **Git을 데이터 저장소로 사용**: 10분마다 `git push -f`로 JSON 캐시를 main에 강제 푸시한다. Git은 바이너리/대용량 데이터 저장에 적합하지 않고, 히스토리가 빠르게 비대해진다.
- **단일 브랜치 강제 푸시**: `git push -f origin HEAD:main`은 다른 변경사항을 덮어쓸 위험이 있다. 코드 변경과 데이터 업데이트가 같은 브랜치에서 충돌할 수 있다.
- **모듈 간 결합**: `send_briefing.py`가 `os.system("python3 sector_weather.py")`로 서브프로세스를 호출하면서, 동시에 같은 워크플로에서 이미 `sector_weather.py`를 실행하고 있다(이중 실행 가능성).

---

## 3. 코드 품질 검토

### 3.1 `wk_feed_quant.py` (핵심 데이터 수집기)

**심각도: 높음**

| 위치 | 이슈 | 설명 |
|------|------|------|
| L44-47 | bare `except` | `except:` 절에서 모든 예외를 삼킨다. `KeyboardInterrupt` 등도 무시된다. |
| L79-80 | bare `except` | `get_top_us()`에서 yfinance API 오류를 무음 처리한다. 데이터 누락 시 원인 추적 불가. |
| L96 | 5컬럼 미만 시 오류 | `raise KeyError("OHLCV columns not detected")` — 상위 호출자가 이를 적절히 처리하는지 검증 필요. |
| L127 | `math.log10(0)` 위험 | `last_high`가 0이면 `math.log10(0)`이 `-inf`를 반환하거나 `ValueError`를 발생시킨다. |
| L151-152 | 0 나누기 방어 불충분 | `v0 > 0` 체크는 있지만, `v0`이 정확히 0일 때 `ea[-2]`가 `NaN`이면 예상과 다른 결과를 낼 수 있다. |
| L10-17 | JSON 커스텀 포맷터 | 정규식 기반 JSON 포맷팅이 복잡하고 에지케이스에 취약하다. |

**개선 권고:**
```python
# bare except 대신 구체적 예외 사용
except (ValueError, KeyError, TypeError) as e:
    _log(f"⚠️ {code}: {e}")
    continue

# math.log10(0) 방어
if last_high <= 0:
    step = 0.01
else:
    digits = int(math.floor(math.log10(last_high)))
    step = max(0.01, 10 ** (digits - 3))
```

### 3.2 `sector_weather.py` (섹터 분석)

**심각도: 중간**

| 위치 | 이슈 | 설명 |
|------|------|------|
| L42-46 | yfinance API 호출 과다 | `ysec()` 함수가 종목마다 `yf.Ticker(ticker).info`를 호출한다. 77개 종목이면 77번 API 호출이 발생하여 rate limit에 걸릴 수 있다. |
| L45 | bare `except` | 섹터 정보 조회 실패 시 "Unknown"을 반환하지만, 네트워크 오류와 데이터 부재를 구분하지 않는다. |
| L64 | 에너지 계산 하드코딩 | `len(c) < 28` 검증이 매직넘버로 사용된다. 이 값의 근거가 코드에서 드러나지 않는다. |

**개선 권고:**
- 섹터 정보를 캐시 파일에 포함시키거나 별도 매핑 파일로 관리하여 반복 API 호출을 제거한다.
- `compute_energy()`의 인덱스 `-27`이 왜 1일(1d) 기준인지 주석으로 명시한다 (15m × 26 = 6.5시간 ≈ 장중 시간?).

### 3.3 `send_briefing.py` (브리핑 전송)

**심각도: 중간**

| 위치 | 이슈 | 설명 |
|------|------|------|
| L14 | `datetime.utcnow()` deprecated | Python 3.12+에서 `datetime.utcnow()`는 deprecated 되었다. `datetime.now(timezone.utc)` 사용 권장. |
| L31-33, 44-49, 56-58 | DEBUG print문 잔존 | 프로덕션 코드에 `===== DEBUG =====` 출력이 6곳 남아있다. 텔레그램으로 전송되거나 로그를 오염시킬 수 있다. |
| L74 | `os.system()` 사용 | 셸 인젝션 위험은 낮지만, `subprocess.run()`이 더 안전하고 에러 처리가 용이하다. |
| L80 | 파일 핸들 미종료 | `open(BRIEF, "r").read()` — `with` 문 없이 파일을 열어 GC에 의존한다. |
| L19 | 정규식 파싱 취약 | ANSI 코드 제거 후 텍스트 파싱에 의존하는데, 출력 형식이 바뀌면 즉시 깨진다. |

### 3.4 `telegram_notify.py` (텔레그램 API)

**심각도: 낮음~중간**

| 위치 | 이슈 | 설명 |
|------|------|------|
| L5 | 환경변수 누락 시 `KeyError` | `os.environ["TELEGRAM_BOT_TOKEN"]`은 모듈 임포트 시점에 평가되어, 로컬 테스트 시 즉시 크래시한다. |
| L10-13 | 응답 검증 없음 | `requests.post()` 결과의 HTTP 상태코드나 텔레그램 API 에러를 확인하지 않는다. |
| L9-21 | 타임아웃 미설정 | `requests.post()`에 `timeout` 파라미터가 없어 네트워크 장애 시 무한 대기할 수 있다. |

### 3.5 `scripts/handle_command.sh` (명령 처리)

**심각도: 높음 (보안)**

| 위치 | 이슈 | 설명 |
|------|------|------|
| L20-23 | 명령 인젝션 위험 | `COMMENT_BODY`가 GitHub Issue 코멘트에서 오는 사용자 입력이다. `CMD_FILE="scripts/cmd_${COMMAND}.py"` 구성 시 경로 조작(path traversal)이 가능할 수 있다. 예: `../../etc/passwd` 형태 입력. |
| L31 | 변수 미이스케이프 | `${COMMENT_BODY}`가 `gh api` 인자에 직접 삽입되어 특수문자가 포함된 코멘트에서 문제가 발생할 수 있다. |
| L64 | 명령 출력 직접 노출 | 파이썬 스크립트의 에러 메시지가 GitHub Issue 코멘트로 그대로 노출되어 내부 경로나 환경 정보가 유출될 수 있다. |

**개선 권고:**
```bash
# 명령어 화이트리스트 검증 추가
ALLOWED_CMDS="상태|미쿡_분석|쿡장_분석"
if ! echo "$COMMAND" | grep -qE "^(${ALLOWED_CMDS})$"; then
    echo "❌ 허용되지 않은 명령"
    exit 1
fi
```

---

## 4. 보안 검토

### 4.1 시크릿 관리

| 항목 | 상태 | 비고 |
|------|------|------|
| `TELEGRAM_BOT_TOKEN` | GitHub Secrets | 적절 |
| `TELEGRAM_CHAT_ID` | GitHub Secrets | 적절 |
| `GH_PAT` | GitHub Secrets | 적절 |
| 시크릿 하드코딩 | 없음 | 양호 |

### 4.2 위험 요소

1. **`git push -f origin HEAD:main`**: main 브랜치에 대한 강제 푸시 권한이 워크플로에 부여되어 있다. 악의적 PR이 머지되면 임의 코드가 main에서 실행될 수 있다.
2. **GitHub Issue 기반 명령 실행**: 이슈 코멘트로 임의 명령을 트리거할 수 있는 구조이다. 현재 `분석`/`상태` 키워드만 필터링하지만, `handle_command.sh`에서 추가적인 입력 검증이 필요하다.
3. **네이버 금융 스크래핑**: User-Agent 위장(`Mozilla/5.0`)을 사용한다. 네이버 이용약관 위반 가능성이 있고, 차단 시 한국 시장 데이터 전체가 중단된다.

---

## 5. 안정성 및 에러 처리

### 5.1 실패 시나리오 분석

| 시나리오 | 현재 동작 | 영향 |
|---------|---------|------|
| yfinance API 다운 | 빈 캐시 생성 | 이전 정상 캐시가 빈 파일로 덮어씌워진다 |
| 네이버 금융 차단 | 3회 재시도 후 빈 리스트 반환 | 한국 종목 데이터 전체 소실 |
| 텔레그램 API 오류 | 무음 실패 | 브리핑 전송 누락 인지 불가 |
| JSON 파싱 오류 | 빈 dict 반환 | 에러 원인 추적 불가 |
| 디스크 공간 부족 | 예외 미처리 | 워크플로 실패 |

### 5.2 핵심 문제: 빈 캐시 덮어쓰기

`wk_feed_quant.py`에서 API 장애 시 `buckets_kr`/`buckets_us`가 비어 있을 수 있는데, 이 경우에도 `_save_json()`이 실행되어 기존 정상 캐시를 빈 JSON(`{}`)으로 덮어쓴다. 이는 치명적인 데이터 손실이다.

**개선 권고:**
```python
# 캐시 저장 전 최소 데이터 검증
for iv in ivs:
    if len(buckets_kr[iv]) < 5:
        _log(f"⚠️ KR {iv} 데이터 부족({len(buckets_kr[iv])}개), 기존 캐시 유지")
        continue
    _save_json(os.path.join(CACHE_DIR, f"all_kr_{iv}.json"), buckets_kr[iv])
```

---

## 6. 성능 검토

### 6.1 병목 지점

1. **순차적 API 호출** (`wk_feed_quant.py` L343-368): KR/US/IDX 종목을 순차적으로 처리한다. 약 160개 종목 × 4 주기 = ~640회 yfinance 호출이 직렬로 실행되어 전체 실행 시간이 길다.
2. **섹터 정보 반복 조회** (`sector_weather.py` L42-46): 종목별 `yf.Ticker().info` 호출은 불필요하게 느리다. 한 번 조회한 섹터 정보를 캐시하면 대폭 개선된다.
3. **JSON 커스텀 포맷팅** (`wkjson_dumps`): 매 저장 시 정규식으로 JSON을 재포맷한다. 캐시 파일 크기(~500KB)에서는 무시할 수준이지만, 디버깅 목적이라면 프로덕션에서는 `json.dumps()`만으로 충분하다.

### 6.2 GitHub Actions 비용

- 10분마다 워크플로가 실행되면 일 144회, 월 ~4,320회 실행이다.
- 무료 계정 기준 월 2,000분 제한에 빠르게 도달할 수 있다.
- 장 마감/주말에도 동일하게 실행되어 무의미한 리소스를 소모한다.

---

## 7. CI/CD 검토

### 7.1 `wk_feed_quant.yml`

| 항목 | 평가 | 비고 |
|------|------|------|
| `git push -f` | 위험 | main 보호 규칙 무력화 |
| `rm -rf cache/*.json` | 위험 | 기존 캐시를 삭제 후 새로 생성 — 실패 시 데이터 소실 |
| `git fetch --all` | 비효율 | 모든 리모트/브랜치를 fetch — `git fetch origin main`으로 충분 |
| `continue-on-error: true` | 주의 | 캐시 복구 실패를 무시하므로, 캐시 없이 실행될 수 있음 |

### 7.2 `sector_weather.yml`

- L67에서 `python3 sector_weather.py | tee briefing.txt`로 파일을 생성하고, L71에서 `send_briefing.py`가 다시 `os.system("python3 sector_weather.py > briefing.txt")`를 실행한다. **sector_weather.py가 2회 실행된다.**
- 이는 불필요한 API 호출 중복이며, 두 실행 결과가 다를 수 있다.

### 7.3 `mud.yml`

- `issue_comment` 이벤트에서 `contains(body, '분석')`으로 필터링한다. "분석" 단어가 포함된 모든 코멘트에서 트리거되므로, 일상 대화에서도 의도치 않게 실행될 수 있다.
- `Report Success` 단계가 기존 코멘트 내용을 `(Workflow Status: success)`로 **완전히 덮어쓴다** — 기존 분석 결과가 사라진다.

### 7.4 `sector_weather.yml` 오타

- L19: `build-sector-weatcher` → `build-sector-weather` (오타)

---

## 8. 데이터 모델 검토

### 8.1 캐시 JSON 구조

```json
{
  "TICKER": {
    "name": "종목명",
    "symbol": "야후 심볼",
    "interval": "15m",
    "rows": 77,
    "last_bar_start": "2026-02-16T...",
    "last_bar_end": "2026-02-16T...",
    "profile": { "가격": 거래량, ... },
    "price_set": [가격 리스트],
    "energies": [에너지 배열],
    "ohlcv": { "ts":[], "open":[], "high":[], "low":[], "close":[], "volume":[] }
  }
}
```

- `profile`과 `price_set`은 매물대 분석용이나, 현재 `sector_weather.py`에서 사용하지 않는다. 캐시 용량의 상당 부분을 차지하지만 활용도가 낮다.
- `ohlcv`가 columnar format(열 기반)으로 저장되어 있어 효율적이다.

### 8.2 에너지 지표의 의미

- `energy = price × volume × 1e-6` (MUSD/MKRW)
- 거래대금의 스케일링 버전으로, 유동성과 시장 관심도를 나타낸다.
- 섹터별 합산 시 대형주 편향이 강하다 (NVDA, TSLA 등이 섹터 에너지를 지배).

---

## 9. 테스트 현황

**테스트 코드: 없음**

- 단위 테스트(unit test): 0개
- 통합 테스트(integration test): 0개
- 테스트 프레임워크 설정: 없음
- CI 테스트 단계: 없음

### 권장 테스트 대상 (우선순위순)

1. `wk_ultra_flatten_ohlcv()` — 다양한 DataFrame 형식 입력 처리
2. `collect_profile()` — 매물대 계산 정확성
3. `compute_energy_array()` — 에너지 계산 정확성, 엣지케이스 (volume=0, 빈 DataFrame)
4. `compute_energy()` (sector_weather) — 인덱스 경계값 처리
5. `make_voice_summary()` — 정규식 파싱 안정성

---

## 10. 문서화 현황

| 항목 | 상태 | 비고 |
|------|------|------|
| README.md | 1줄 | 설치/실행 방법, 환경변수 설정 등 없음 |
| 함수 docstring | 없음 | 모든 함수에 docstring 부재 |
| 타입 힌트 | 거의 없음 | `send_briefing.py`의 `make_voice_summary`만 `str` 힌트 존재 |
| 인라인 주석 | 한국어 | 핵심 로직에 주석이 있으나 불균일 |
| 아키텍처 문서 | 없음 | |
| API 문서 | 없음 | |

---

## 11. 핵심 개선 권고 (우선순위순)

### P0 (즉시 조치 필요)

1. **빈 캐시 덮어쓰기 방지**: API 장애 시 기존 캐시가 빈 파일로 대체되는 문제. 최소 데이터 건수 검증 후 저장.
2. **`send_briefing.py` DEBUG 출력 제거**: 프로덕션 코드에 잔존하는 6개의 DEBUG print문 제거.
3. **`sector_weather.py` 이중 실행 제거**: 워크플로에서 이미 실행한 결과를 `send_briefing.py`에서 다시 실행하는 문제 수정.

### P1 (단기 개선)

4. **handle_command.sh 입력 검증 강화**: 명령어 화이트리스트 적용, 경로 조작 방지.
5. **bare except 제거**: 모든 `except:` 절을 구체적 예외 타입으로 변경.
6. **텔레그램 API 에러 처리 추가**: 응답 상태코드 확인 및 재시도 로직.
7. **requests 타임아웃 일관 적용**: 모든 HTTP 호출에 `timeout=10` 추가.
8. **mud.yml Report Success 버그 수정**: 기존 분석 결과를 덮어쓰는 문제 수정.

### P2 (중기 개선)

9. **섹터 정보 캐시**: `yf.Ticker().info` 반복 호출을 제거하고 매핑 파일로 관리.
10. **장 시간/휴일 인식**: 장 마감 및 주말에는 워크플로 실행을 건너뛰어 Actions 분 절약.
11. **핵심 함수 단위 테스트 추가**: `compute_energy_array`, `collect_profile`, `wk_ultra_flatten_ohlcv`.
12. **README 확장**: 설치, 설정, 실행 방법, 아키텍처 설명 추가.

### P3 (장기 개선)

13. **데이터 저장소 분리**: Git이 아닌 외부 저장소(S3, SQLite 등)로 캐시 데이터 이관.
14. **병렬 데이터 수집**: `concurrent.futures` 또는 `asyncio`를 활용한 API 호출 병렬화.
15. **모니터링/알림**: 데이터 수집 실패, 캐시 이상, 워크플로 실패 시 알림 체계 구축.

---

## 12. 요약

WkFeedQuant는 GitHub Actions만으로 실시간 시장 감시 시스템을 운영하는 실용적인 프로젝트다. 핵심 로직(에너지 지표, 매물대 분석)은 잘 구현되어 있으나, **에러 처리**, **데이터 안전성**, **보안 검증**에서 개선이 필요하다. 특히 빈 캐시 덮어쓰기와 DEBUG 코드 잔존은 즉시 수정해야 한다. 중기적으로는 테스트 커버리지 확보와 섹터 정보 캐싱이 시스템 안정성을 크게 높일 것이다.
