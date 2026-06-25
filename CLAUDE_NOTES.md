# TradeAdvisor — Session Notes

---

## Session: 2026-06-24

### 1. P3 — Earnings Blackout — DONE

*(See commit `0d402af` — already documented below)*

---

### 2. Earnings Date Column Added

**Problem:** `earnings_warning` flag existed but the actual earnings date was never shown in the UI. User couldn't see when earnings were without knowing to look elsewhere.

**Fix:** Added `earnings_date` field to every opportunity dict. Both `csp_results.html` and `top_csp.html` now show an Earnings column — date is orange when near-expiry flagged, plain text otherwise, `—` if unavailable.

**Commit:** `0d402af`

---

### 3. P2 — IV Rank — DONE

**Why:** Without IV Rank, a "22% annualized" CSP could be normal noise or genuinely elevated premium — user can't tell if it's worth selling.

**Implementation:**
- `database.py`: Added `iv_history(symbol TEXT, iv FLOAT, recorded_at FLOAT)` table to `init_db()`. Added `record_iv(symbol, iv)` (insert) and `get_iv_rank(symbol)` — queries last 52 weeks, returns `{"iv_rank": float, "sample_count": int}` or `None` if < 5 samples.
- `options_engine.py`: During the contract loop, tracks the strike with IV closest to ATM (`atm_iv`). After the expiry loop: calls `record_iv`, then `get_iv_rank`, stamps `iv_rank` onto every opportunity for that symbol.
- Both CSP and CC templates: IV Rank column between OI and Earnings. Green ≥ 50 (elevated, good to sell), orange 30–49 (neutral), gray < 30 (low), `—` while accumulating (< 5 readings).
- IV Rank is **display-only** — does not affect score yet. Validate the signal first.

**Data accumulation:** Shows `—` until 5 hourly scan readings exist per symbol (~5 hours). Becomes meaningful after ~1 week.

**Test coverage:** 4 new DB tests — `test_record_and_rank_iv`, `test_iv_rank_insufficient_data_returns_none`, `test_iv_rank_flat_iv_returns_none`, `test_iv_rank_unknown_symbol_returns_none`.

**Commit:** `81e6f49`

---

### 4. P4 — Covered Calls — DONE

**Implementation:**
- `options_engine.py`: Refactored `find_csp_opportunities` body into `_find_opportunities(symbol, max_dte, side)`. Public methods are now one-liner wrappers. Added `find_cc_opportunities`. CC-specific logic: scans `chain.calls`, OTM window 0–10% above price, call delta 0.25–0.30, `_call_delta` (N(d1) without the `-1`), `_score_cc`.
- CC scoring differs from CSP: **RSI overbought (+1)** is a positive signal (stock extended = good to cap gains), and distance rewards strike being further above price (more buffer before shares get called away).
- `top_cc.py`: New file, exact mirror of `top_csp.py` — background thread, file + DB cache (`top_cc_cache`), same per-symbol slot guarantee.
- `app.py`: `/cc/<symbol>` and `/top-cc` routes. Imported `get_top_cc_opportunities`.
- `templates/cc_results.html` + `templates/top_cc.html`: New templates, identical columns to CSP counterparts.
- `templates/dashboard.html`: "Top Covered Calls" nav link; "CC" column per ticker row linking to `/cc/<symbol>`.

**All 64 tests passing.**

**Commit:** `8a0ce71`

---

## Commits This Session (2026-06-24)
- `0d402af` — P3: Flag CSPs expiring near earnings date with warning badge and date column
- `81e6f49` — P2: Add IV Rank — record ATM IV per scan, display 0-100 rank alongside score
- `8a0ce71` — P4: Add Covered Call scanner — /cc/<symbol>, /top-cc, background scan, CC scoring

---

## Pending for Next Session

### P5 — UI Polish / Mobile Responsive
Bootstrap grid, cleaner typography, score badges. Dashboard and results pages.

---

## Session: 2026-06-24 (earlier — P3 detail)

### 1. P3 — Earnings Blackout — DONE

**Problem:** Scanner could recommend selling a CSP that expires within days of an earnings release — high-risk situation where IV spikes pre-earnings and the stock can gap down violently.

**Fix:** Added `_get_next_earnings(ticker)` to `OptionsEngine`:
- Calls `ticker.calendar` (yfinance), extracts `Earnings Date[0]` as a `date` object
- Returns `None` gracefully on any error (calendar unavailable, network failure, etc.)
- Called once per symbol after expirations are fetched (already inside semaphore, no extra locking needed)

**Flag logic:** For each expiry in the scan, `earnings_warning = abs((expiry_date - earnings_date).days) <= 5`.
- Added `"earnings_warning": bool` field to every opportunity dict
- Both `csp_results.html` and `top_csp.html` show `⚠ EARN` badge in the Expiry column when flagged
- Rows are shown (not suppressed) — user sees the data and decides

**Test coverage:** 6 new tests added to `test_options_engine.py` (60 total, all passing):
- `test_get_next_earnings_returns_date` — normal case
- `test_get_next_earnings_empty_calendar` — empty dict
- `test_get_next_earnings_none_calendar` — None calendar
- `test_get_next_earnings_exception_returns_none` — network error
- `test_earnings_warning_flag_near` — within 5 days
- `test_earnings_warning_flag_far` — outside 5 days
- `MockTicker` updated with `calendar` property (earnings 60 days out, no warning)
- Integration test asserts `earnings_warning` key present and `False` on mock

---

## Session: 2026-06-23

### 1. Test Suite — Built and Fixed (54 tests passing)

**Context:** CLAUDE_NOTES from 2026-06-22 noted zero tests existed. Tests were written but had 8 broken/erroring tests on first run.

**Bugs fixed in existing tests:**
- `DB_PATH` → `_DB_PATH` monkeypatch in `test_database.py`, `test_app_auth.py`, `test_admin_upload.py` (attribute name mismatch)
- `MockTicker.history()` lacked `**kwargs` — `auto_adjust=True` caused silent `TypeError` → 21s retry loop → empty results
- Hardcoded past expiry date `"2026-06-20"` in mock; switched to `datetime.now() + timedelta(days=7)`
- `"premium"` key assertion replaced with `"bid"`/`"ask"` (key removed from result dict in prior session)

**New coverage added:**
- `conftest.py` — sets `FLASK_SECRET_KEY` as safety net for CI (removed EODHD_API_KEY line later when EODHD was dropped)
- `test_options_engine.py` — 15 pure-method tests: `_put_delta` (6), `_score_csp` (3), `_label` (4), `_days_to_expiry` (2), `_build_indicator_data_from_hist` (3)
- `test_database.py` — 4 new tests: `get_user_by_id`, ticker idempotency, `set_cache`/`get_cache` round-trip, cache miss
- `tests/test_provider.py` — new file, 10 tests: `calculate_rsi` (5), `safe_float` (5)

**Commits:** `5c19265`

---

### 2. P1 — Replace EODHD with yfinance for Dashboard Prices — DONE

**Problem:** EODHD gives end-of-day prices only — dashboard showed yesterday's close during market hours.

**Fix:** Rewrote `market_data/provider.py` — `fetch_snapshot` now uses `yf.Ticker(symbol).history(period="1y", auto_adjust=True)`, the same call the CSP scanner already makes. Prices now update intraday.

**Changes:**
- Removed EODHD HTTP call and API key dependency entirely
- Snapshot cache TTL reduced from 4h → 15min
- Added `change_pct` (today vs prev close) and `as_of` date to snapshot dict
- Moved shared `_yf_semaphore` from `options_engine.py` into `provider.py` so both dashboard fetches and CSP scanner share one concurrency gate
- `build_row` in `app.py` passes `change_pct`, `rsi`, `as_of` to template
- Dashboard now shows: **Change% column** (green/red), **RSI column** (green if ≤30 oversold, red if ≥70 overbought), data freshness note below table
- Added "Top CSP Opportunities" nav link in dashboard header

**Commit:** `a4fd2b3`

---

### 3. P1b — Personalize Top CSP from User Watchlists — DONE

**Problem:** `top_csp.py` had a hardcoded `WATCHLIST = ["HOOD", "SOFI", "GDX", "DAL", "IBKR", "SPY", "NVDA", "XLE"]` independent of any user's actual tickers.

**Fix:**
- Added `get_all_tickers()` to `database.py` — returns `DISTINCT symbol` across all `user_tickers`
- `_do_scan()` in `top_csp.py` now calls `get_all_tickers()` each hourly cycle; falls back to `_DEFAULT_WATCHLIST = ["AAPL", "MSFT", "NVDA", "SPY"]` if DB is empty (fresh deploy)
- Removed hardcoded `WATCHLIST` constant

**Commit:** `e23d9b8`

---

### 4. Admin Clear-Cache Route — DONE

**Problem:** After P1b deploy, Top CSP still showed old results because PostgreSQL `cache` table had a stale `top_csp_cache` entry. Render free tier has no shell access to run SQL directly.

**Fix:** Added `/admin/clear-cache` route (admin-only, login-gated) that writes `[]` to `top_csp_cache` in the DB, forcing the background thread's next write to use the real watchlist.

**Note:** URL is `/admin/clear-cache` (not `/admin/cache-clear` — easy to mix up).

**Commit:** `515e13a`

---

## Commits This Session (2026-06-23)
- `5c19265` — Add test suite: fix 8 broken tests and fill coverage gaps (54 passing)
- `a4fd2b3` — P1: Replace EODHD with yfinance for dashboard price snapshots
- `e23d9b8` — P1b: Personalize Top CSP from user watchlists instead of hardcoded list
- `515e13a` — Add /admin/clear-cache route to wipe stale top_csp_cache from browser

---

## Pending for Next Session

### P2 — IV Rank / IV Percentile
**Why:** Without IV Rank, a "22% annualized" CSP could be normal noise or genuinely elevated premium — the user can't tell. IV Rank is the primary signal for CSP selling.

**Plan:**
1. Add `iv_history` table to DB: `(symbol TEXT, iv FLOAT, recorded_at FLOAT)`
2. Record IV readings from the options scanner on each scan run (already fetching `impliedVolatility` per strike — take the median or ATM IV per symbol)
3. Compute IV Rank = `(current_iv - 52w_low_iv) / (52w_high_iv - 52w_low_iv) * 100`
4. Show IV Rank alongside score in CSP results and Top CSP page
5. Gets better over time as more readings accumulate in the DB

### ~~P3 — Earnings Blackout~~ — DONE (2026-06-24)

### P4 — Top Covered Calls Page
**Why:** Natural companion to Top CSP. Covered calls share ~80% of the CSP scanner code (same chain fetch, reversed direction — scan calls instead of puts, delta ~0.25–0.30, slightly OTM).

**Sequence after P2 + P3:** IV Rank and earnings awareness make both CSP and CC recommendations meaningfully better.

### P5 — UI Polish / Mobile Responsive
Bootstrap grid, cleaner typography, score badges.

---

## Session: 2026-06-22

### 1. Watchlist Blown Away on Render — Diagnosed

**Problem:** Dashboard showed only 3 tickers (AAPL, MSFT, NVDA) after the P4 deploy.

**Root cause:** Render PostgreSQL `user_tickers` data was wiped (likely a Render free-tier instance reset during the P4 redeploy). When the user next logged in, `ensure_default_tickers_for_user()` in `app.py:171` found 0 tickers and seeded the 3 defaults (`DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA"]`). The P4 code changes themselves are safe — all `CREATE TABLE IF NOT EXISTS`, nothing drops data.

**Fix:** User manually re-added the full watchlist via the dashboard UI. No code change needed.

**Note:** `top_csp.py` has its own hardcoded `WATCHLIST` (independent of the user DB), so Top-CSP was never affected.

---

### 2. P5A — Strip Debug Print Statements — DONE, committed `36637c6`

Removed all `print()` calls from `app.py`, `options_engine.py`, and `top_csp.py`:
- Startup version banner (app.py lines 12-15)
- Per-symbol trade result debug print in `build_row`
- Full CSP debug block in `/csp/<symbol>` route
- Top-CSP score dump in `/top-csp` route
- All scan/cache/expiration/chain debug prints in `options_engine.py` (45+ prints)
- All cache hit/miss/save prints in `top_csp.py`
- Removed unused `import traceback` from `options_engine.py`
- Empty `except` blocks after print removal replaced with `except Exception: pass`

---

### 3. P5B — Remove Debug Routes — DONE, committed `36637c6`

Deleted `/debug-options` and `/debug-history` routes from `app.py`. Both were login-gated but had no business being in prod.

---

## Commits This Session (2026-06-22)
- `36637c6` — P5: Strip debug print statements and remove debug routes

---

## Pending for Next Session

### Test Coverage
**Zero project tests exist.** pytest 9.0.2 is already installed in `.venv`.

**Plan — write `tests/` directory with four files:**

1. **`conftest.py`** (project root) — sets `EODHD_API_KEY=test-key` before any imports (provider.py raises RuntimeError at import if not set)

2. **`tests/test_trade_advisor.py`** — `StrategyEngine.evaluate()`:
   - BUY signal: above both DMAs + RSI oversold + near 52w low
   - SELL signal: near 52w high + RSI not oversold
   - HOLD: neutral/mixed signals
   - Missing price → HOLD with confidence=0
   - Missing DMA or RSI → HOLD
   - Invalid price type → TypeError
   - RSI boundary conditions (≤30 oversold, >70 overbought)
   - 52w positioning boundaries (price ≤ low*1.05 = near_low, price ≥ high*0.95 = near_high)
   - Confidence clamped 0–100

3. **`tests/test_options_engine.py`** — Pure OptionsEngine methods (no yfinance):
   - `_put_delta`: ATM (~-0.46), deep OTM (~0), deep ITM (~-1), zero IV/DTE/price → None
   - `_score_csp`: max score (11), zero score, partial signals
   - `_label`: STRONG (≥8), GOOD (5–7), OK (3–4), WEAK (<3)
   - `_days_to_expiry`: future date, past date
   - `_build_indicator_data_from_hist`: <200 rows → `{}`, 250 rows → all fields present

4. **`tests/test_provider.py`** — Pure functions (no HTTP):
   - `calculate_rsi`: too-short series → None, monotonic up → >90, monotonic down → <10, mixed → 0–100
   - `safe_float`: normal float, string number, None → None, invalid string → None

5. **`tests/test_database.py`** — SQLite CRUD via `monkeypatch` on `database._DB_PATH`:
   - `create_user` + `get_user_by_email` + `get_user_by_id`
   - `add_ticker_to_user`, `get_tickers_for_user`, `remove_ticker_from_user`
   - Idempotency: adding same ticker twice doesn't duplicate
   - `set_cache` + `get_cache` hit and miss

**What to skip:** `find_csp_opportunities` (yfinance + threading), Flask routes, `top_csp.py` background thread.

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

## Full Issue Backlog

**All P2–P5 items complete as of 2026-06-22. Only remaining work is test coverage (see Pending above).**

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
