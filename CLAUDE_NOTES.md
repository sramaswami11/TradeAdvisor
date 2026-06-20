# TradeAdvisor — Session Notes

---

## Session: 2026-06-19

### 1. Fixed `remove_ticker` Missing Auth Guard (DONE — committed)

**Problem:** `remove_ticker` at `/remove/<symbol>` hit `session["user_id"]` directly with no
`if "user_id" not in session` check. Unauthenticated request → 500 KeyError.
Every other protected route had the guard; this one was missed.

**Fix:** Added standard auth redirect before the DB call. (`app.py:291`)

**Commit:** `17ebbe3` (bundled with P1B)

---

### 2. Fixed RSI Hardcoded to 50 in CSP Scanner (DONE — committed)

**Problem:** `_build_indicator_data_from_hist` in `options_engine.py` had `rsi = 50` as
a placeholder. RSI was never computed in the CSP path — always "neutral", BUY signals
(require oversold) could never fire. Dashboard path used EODHD and computed real RSI.

**Fix:** Imported `calculate_rsi` from `market_data/provider.py` and replaced the hardcode
with `calculate_rsi(hist["Close"])`. The `hist` DataFrame is already in hand so no extra call.

**Commit:** `17ebbe3`

---

### 3. Fixed yfinance Session Incompatibility (DONE — committed)

**Problem:** Commit `5e955c7` (previous session) passed a `requests.Session` with a
browser User-Agent to `yf.Ticker(symbol, session=session)`. yfinance 0.2.66 upgraded
its internals to use `curl_cffi` (Chrome impersonation built-in) and now raises
`YFDataException` if you hand it a plain `requests.Session`.

**Fix:** Removed the session creation entirely — let yfinance handle its own session.
Removed `requests` import and `YAHOO_HEADERS` constant from `options_engine.py` (both dead).
`requests` stays in `requirements.txt` because `market_data/provider.py` still uses it for EODHD.

**Commit:** `d1a383d`

---

### 4. Reduced Rate-Limit Burst and Memory Pressure (DONE — committed)

**Problem:** History and expirations fetch were back-to-back on the same ticker.
Yahoo was rate-limiting the second call. Back-off was 10/30/60s — combined with
gunicorn running 2 workers, sleeping workers held memory long enough to OOM.

**Fix:**
- Added `time.sleep(2)` between history fetch and `_get_expirations` call.
- Tightened back-off from 10/30/60s → 5/10/20s.
- Dropped gunicorn workers from 2 → 1 (`render.yaml`). Background ThreadPoolExecutor
  already handles parallelism; 2 workers on 512MB Render free was redundant and risky.

**Commit:** `0637178`

---

### 5. Serialized yfinance Calls with Semaphore (DONE — committed)

**Problem:** Background `top_csp` thread was running 3 concurrent `find_csp_opportunities`
calls (via ThreadPoolExecutor, `_SCAN_WORKERS=3`). When a user triggered `/csp/SPY`
simultaneously, that was 4 concurrent yfinance calls + their pandas DataFrames in memory →
OOM, gunicorn SIGKILL'd the worker consistently at the 3rd expiration retry.

**Fix:**
- Added `threading.Semaphore(1)` as `_yf_semaphore` in `options_engine.py`.
- `find_csp_opportunities` acquires before entering and releases in `finally` — guaranteed
  release on any exit path (exception, early `return []`, or normal return).
- Dropped `_SCAN_WORKERS` from 3 → 1 in `top_csp.py` to match serialized behavior.

**Verified working:** CSP scan for SPY completes without SIGKILL after this fix.

**Commit:** `ea5b599`

---

### 6. NVDIA Typo (still pending — manual fix)

Watchlist contains `NVDIA` instead of `NVDA`. EODHD returns 404 for `NVDIA.US`.
Fix: log into live app, remove `NVDIA`, re-add `NVDA` from the dashboard.
Data lives in Render PostgreSQL — no code change needed.

---

## Full Issue Backlog (Priority Order)

### P2 — Dead Code

**C. `_build_indicator_data()` method** (`options_engine.py:553-573`)
Kept "as alias for old callers" but no callers exist. Makes a redundant second Yahoo call.

**D. `ensure_name_column()`** (`database.py:70-87`)
Migration helper from when `name` column was added. Never called. Dead code.

### P3 — File Cleanup

**E. Delete `tradeadvisor.db`** — old 65KB SQLite file from Jan 26, locally only, gitignored.

**F. Delete `app.py.bak`** — old backup from Jan 15.

### P4 — Operational Improvement

**G. Cache persistence in PostgreSQL**
`/tmp` caches (`expiration_cache.json`, `top_csp_cache.json`, `snapshot_cache_*.json`)
are wiped on Render redeploy. Warm-up takes ~60s after each deploy.
Option: add `cache(key TEXT, value TEXT, timestamp FLOAT)` table to PostgreSQL.
Background thread still fills; caches survive deploys.

### P5 — Low Noise

**H. Debug prints** — `app.py`, `options_engine.py`, `top_csp.py` spam logs in prod.

**I. Debug routes** — `/debug-options` and `/debug-history` are exposed in prod
(login-gated, low risk, but should be removed).

---

## Key Files
- `app.py` — Flask routes
- `database.py` — SQLite/PostgreSQL dual-backend, controlled by `DATABASE_URL`
- `options_engine.py` — CSP scanner (yfinance, scoring, caching, semaphore)
- `top_csp.py` — background refresh thread + ThreadPoolExecutor scan
- `market_data/provider.py` — EODHD market data fetch + RSI calculation
- `trade_advisor.py` — StrategyEngine (200/50 DMA, RSI, 52w positioning)
- `requirements.txt` — added `psycopg2-binary`, `requests`
- `render.yaml` — Render PostgreSQL + `DATABASE_URL` wiring, 1 gunicorn worker
- `templates/top_csp.html` — "Scan in progress" cold-start message

## Commits This Session (2026-06-19)
- `17ebbe3` — Fix auth guard on remove_ticker and compute real RSI in CSP scanner
- `d1a383d` — Drop manual requests.Session — yfinance now requires curl_cffi internally
- `0637178` — Reduce memory pressure and rate-limit burst on Render free tier
- `ea5b599` — Serialize yfinance calls with semaphore to prevent OOM on Render free tier

## Commits Previous Session (2026-06-18)
- `5e955c7` — Fix Yahoo Finance rate limiting: apply User-Agent session to yf.Ticker, escalate 429 back-off

## Commits Session Before That (2026-06-17)
- `a9709ae` — Migrate database layer to support Render PostgreSQL
- `54f13d5` — Move top-csp scan off request path into background thread
- `ce108f9` — Validate DATABASE_URL format before using psycopg2
- `c3f7845` — Expand watchlist to 8 symbols, parallelize scan with ThreadPoolExecutor
