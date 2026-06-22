# TradeAdvisor — Session Notes

---

## Session: 2026-06-21

### 1. Standardized CSP Display Columns — DONE, committed `5e2eafb`

**Problem:** Per-symbol CSP page and Top-CSP page had different, inconsistent columns. Per-symbol showed Strike/Expiry/DTE/Premium/Yield%/Ann%/Distance%/Score/Recommendation; Top-CSP showed Symbol/Price/Strike/Expiry/DTE/Premium/Yield%/Distance%/Score/Rating.

**Fix:** Unified both views to: Symbol* / Strike / Expiry / DTE / Bid / Ask / Ann% / Distance% / Delta / OI / Score.
- Replaced Premium with Bid + Ask separately (more actionable for execution)
- Replaced Yield% with Ann% (apples-to-apples across different DTE)
- Added Delta (Black-Scholes put delta via `math.erfc`, no scipy needed, uses yfinance `impliedVolatility`, risk-free rate 5%)
- Added OI (open interest, comma-formatted)
- Dropped Price, Strategy, standalone Recommendation — Score column now shows "9 STRONG" with color coding
- Applied basic styling to `top_csp.html` (was completely unstyled before)

**Backend changes (`options_engine.py`):**
- Added `import math`
- Added `_put_delta(price, strike, dte, iv)` method
- Now captures `openInterest` and `impliedVolatility` from yfinance chain row

---

### 2. Added Delta Filter (0.25–0.30) — DONE, committed `5e2eafb`

**Problem:** User wanted to only show CSP opportunities in the 0.25–0.30 delta range (sweet spot: ~70–75% probability of expiring worthless).

**Fix:** Filter added in `options_engine.py` before scoring: `if delta is not None and not (-0.30 <= delta <= -0.25): continue`

**Important:** Filter uses `delta is not None` (not `delta is None or not`) so strikes with missing IV pass through rather than being silently dropped. This prevents the scan returning 0 results when yfinance returns partial data under rate limiting.

---

### 3. Removed Dead Code (P2) — DONE, committed `3a5557a`

- Deleted `_build_indicator_data()` alias in `options_engine.py` (no callers, made redundant Yahoo call)
- Deleted `ensure_name_column()` in `database.py` (one-off migration helper, already applied)
- Cleaned up dead import in `migrate_to_db.py`

---

### 4. Deleted Stale Files (P3) — DONE, committed `8381d30`

- Deleted `app.py.bak` (manual backup from Jan 15)
- Deleted `trade_advisor.db` (original local SQLite from Jan 26, gitignored equivalent still exists locally)

---

### 5. Cache Persistence to PostgreSQL (P4) — DONE, committed `af9a91d`

**Problem:** `/tmp` caches (`expiration_cache.json`, `top_csp_cache.json`) are wiped on every Render redeploy, causing ~60s cold-start warm-up and returning 0 results until the background scan completes.

**Fix:** Added `cache(key TEXT PRIMARY KEY, value TEXT, timestamp FLOAT)` table to PostgreSQL via `init_db()`. Added `get_cache(key)` and `set_cache(key, value, ts)` to `database.py`.

- Both caches now **write-through** to PostgreSQL on every save
- On load: file is tried first (fast path); if missing, falls back to DB
- After any Render redeploy, stale-but-good results are immediately available from PostgreSQL while the background scan re-warms

**Files changed:** `database.py`, `options_engine.py`, `top_csp.py`

---

### 6. Delta Filter Too Aggressive Fix — DONE, committed `518b000`

**Problem:** After deploying the delta filter, Top-CSP page returned 0 results on Render. Root cause: yfinance returns `impliedVolatility=0` or NaN under rate limiting. `_put_delta` returned `None`, and the original filter `if delta is None or not (-0.30 <= delta <= -0.25)` excluded those strikes entirely.

**Fix:** Changed to `if delta is not None and not (-0.30 <= delta <= -0.25): continue` — strikes with missing IV pass through (shown as `—` in UI), only computable deltas are filtered.

---

## Commits This Session (2026-06-21)
- `5e2eafb` — Standardize CSP display: add delta filter, bid/ask, OI, Ann% across both views
- `3a5557a` — Remove dead code: _build_indicator_data alias and ensure_name_column migration helper
- `518b000` — Soften delta filter: pass through strikes when IV is missing rather than dropping them
- `af9a91d` — P4: Persist expiration and top-csp caches to PostgreSQL to survive Render deploys
- `8381d30` — P3: Delete stale backup and old SQLite file

---

## Pending for Next Session
- **P5A** — Strip debug `print` statements from `app.py`, `options_engine.py`, `top_csp.py` (log spam in prod)
- **P5B** — Remove `/debug-options` and `/debug-history` routes (login-gated but exposed in prod)
- **NVDIA typo** — Persists in live Render PostgreSQL watchlist; remove via dashboard UI, don't re-run admin import with old file

## Validation Checklist for Next Session
Before starting new work, verify these on the live Render app:
1. `/top-csp` — shows results (not empty), all deltas in -0.25 to -0.30 range (or `—` if IV missing)
2. `/csp/SPY` — returns results after background scan has warmed the expiration cache
3. After a fresh deploy — `/top-csp` serves stale results from PostgreSQL immediately (not "Scan in progress")
4. Check Render logs: `EXPIRATION CACHE: loaded from DB` or `TOP CSP DB CACHE HIT` should appear after redeploy
5. No NVDIA in dashboard watchlist

---

## Full Issue Backlog (Priority Order)

### P5 — Low Noise

**H. Debug prints** — `app.py`, `options_engine.py`, `top_csp.py` spam logs in prod.

**I. Debug routes** — `/debug-options` and `/debug-history` are exposed in prod
(login-gated, low risk, but should be removed).

---

## Key Files
- `app.py` — Flask routes
- `database.py` — SQLite/PostgreSQL dual-backend, controlled by `DATABASE_URL`; also has `get_cache`/`set_cache` for persistent caching
- `options_engine.py` — CSP scanner (yfinance, scoring, caching, semaphore, Black-Scholes delta)
- `top_csp.py` — background refresh thread + ThreadPoolExecutor scan
- `market_data/provider.py` — EODHD market data fetch + RSI calculation
- `trade_advisor.py` — StrategyEngine (200/50 DMA, RSI, 52w positioning)
- `requirements.txt` — added `psycopg2-binary`, `requests`
- `render.yaml` — Render PostgreSQL + `DATABASE_URL` wiring, 1 gunicorn worker
- `templates/top_csp.html` — unified column layout with styling
- `templates/csp_results.html` — unified column layout

## Commits Previous Session (2026-06-20)
- `4280ae0` — Fail fast on 429 and clear option chain cache to prevent OOM on Render
- `7f0800d` — Fix SPY missing from top-csp: widen strike window, cap DTE, guarantee per-symbol slot

## Commits Session Before That (2026-06-19)
- `5bd5c8f` — Update CLAUDE_NOTES with 2026-06-19 session summary
- `ea5b599` — Serialize yfinance calls with semaphore to prevent OOM on Render free tier
- `0637178` — Reduce memory pressure and rate-limit burst on Render free tier
- `d1a383d` — Drop manual requests.Session — yfinance now requires curl_cffi internally
- `17ebbe3` — Fix auth guard on remove_ticker and compute real RSI in CSP scanner

## Commits Session Before That (2026-06-18)
- `5e955c7` — Fix Yahoo Finance rate limiting: apply User-Agent session to yf.Ticker, escalate 429 back-off

## Commits Session Before That (2026-06-17)
- `a9709ae` — Migrate database layer to support Render PostgreSQL
- `54f13d5` — Move top-csp scan off request path into background thread
- `ce108f9` — Validate DATABASE_URL format before using psycopg2
- `c3f7845` — Expand watchlist to 8 symbols, parallelize scan with ThreadPoolExecutor

---

## Session: 2026-06-20

### 1. Fixed OOM SIGKILL on Render (options_engine.py) — DONE, committed `4280ae0`

**Problem:** CSP scan for SPY was still OOM-killing the Render worker after the semaphore fix from the previous session. Logs showed all 3 expiration retries failing with 429 ("rate limited") and then SIGKILL immediately after.

**Root causes identified:**
- `_get_expirations` retry loop slept 5+10+20 = 35s on 429 while holding the semaphore AND the 1-year `hist` DataFrame in memory. Each failed `ticker.options` call with curl_cffi also left response buffers.
- `_option_chain_cache` on the shared `_shared_engine` singleton was never cleared between symbol scans — option chain DataFrames from all 8 background-scanned symbols accumulated in memory.

**Fix (3 lines):**
- `del hist` after `_build_indicator_data_from_hist`, before expiration fetch.
- On 429 in `_get_expirations`: return stale cache immediately if available, else `return []`. No sleep, no retry.
- `self._option_chain_cache.clear()` in the `finally` block of `find_csp_opportunities`.

---

### 2. Tightened CSP Scan Parameters (options_engine.py) — DONE, committed `7f0800d`

**Problem:** Scanner was going 18% OTM (e.g. SPY $746 → strike $658) and up to 45 DTE. Both impractical. User wanted ≤10% OTM and ≤14 DTE (2 weeks).

**Also:** The 2% minimum OTM floor (`distance_pct > -0.02`) was incorrectly filtering out ATM strikes. SPY $740 strike at SPY price $740 → distance_pct = 0 → filtered out before scoring. The ATM put bid/ask was $3.39/$3.44 — a perfectly valid CSP with 0.62% yield and 20.7% annualized.

**Fix:**
- `max_dte` default: 45 → 14
- OTM upper bound: `distance_pct > -0.02` → `distance_pct > 0` (exclude ITM puts only; allow ATM)
- OTM lower bound: `distance_pct < -0.18` → `distance_pct < -0.10` (10% max OTM)

---

### 3. Fixed SPY Missing from Top-CSP Page (top_csp.py) — DONE, committed `7f0800d`

**Problem:** SPY found 373 CSP opportunities per scan but never appeared in `/top-csp`. Root cause: `_do_scan` globally sorted all results and took `[:15]`. SPY's best strikes score 7 (signals +4, yield +1, annualized +2). High-IV names like HOOD/NVDA score 10, DAL/IBKR/XLE score 8-9, and all 15 slots were consumed before SPY.

**Score breakdown for SPY $740 ATM, DTE=11, premium $4.61:**
- above_200_dma (+2), above_50_dma (+1), rsi_neutral (+1) = 4
- yield_pct 0.623% > 0.5% (+1)
- annualized 20.7% > 10% (+1), > 20% (+1)
- Total: 7 — competitive but loses to HOOD/NVDA/DAL

**Fix:** Restructured `_do_scan` to track results per symbol. Guarantees the best result from each symbol that had opportunities, then fills remaining slots from overflow sorted by score. Removed the `[:15]` hard cap (max is now 8 symbols × 3 = 24 results).

**Verified working locally.** Render deploy pending test.

---

## Commits This Session (2026-06-20)
- `4280ae0` — Fail fast on 429 and clear option chain cache to prevent OOM on Render
- `7f0800d` — Fix SPY missing from top-csp: widen strike window, cap DTE, guarantee per-symbol slot

---

## Pending for Next Session
- Test `7f0800d` on Render (delete `/tmp/top_csp_cache.json` or wait for hourly refresh after deploy)
- Fix NVDIA→NVDA typo in live Render PostgreSQL watchlist (log in, remove NVDIA, add NVDA)

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

## Commits Previous Session (2026-06-19)
- `5bd5c8f` — Update CLAUDE_NOTES with 2026-06-19 session summary
- `ea5b599` — Serialize yfinance calls with semaphore to prevent OOM on Render free tier
- `0637178` — Reduce memory pressure and rate-limit burst on Render free tier
- `d1a383d` — Drop manual requests.Session — yfinance now requires curl_cffi internally
- `17ebbe3` — Fix auth guard on remove_ticker and compute real RSI in CSP scanner

## Commits Session Before That (2026-06-18)
- `5e955c7` — Fix Yahoo Finance rate limiting: apply User-Agent session to yf.Ticker, escalate 429 back-off

## Commits Session Before That (2026-06-17)
- `a9709ae` — Migrate database layer to support Render PostgreSQL
- `54f13d5` — Move top-csp scan off request path into background thread
- `ce108f9` — Validate DATABASE_URL format before using psycopg2
- `c3f7845` — Expand watchlist to 8 symbols, parallelize scan with ThreadPoolExecutor
