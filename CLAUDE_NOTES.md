# TradeAdvisor — Session Notes

---

## Session: 2026-06-18

### 1. Fixed Yahoo Finance Rate Limiting on Render (DONE — committed & deployed)

**Problem:** `/csp/SPY` returned zero results. All 3 attempts to fetch option expirations
failed with rate-limit errors. Render's datacenter IP gets blocked by Yahoo Finance
without a browser-like User-Agent header.

**Root cause:** `YAHOO_HEADERS` (with browser User-Agent) was defined as a class variable
in `OptionsEngine` but was **never applied** to the `yf.Ticker()` call. All yfinance
HTTP requests went out with the default Python/requests User-Agent → rate limited.

**Fix:**
- Create a `requests.Session` with the User-Agent and pass it as `yf.Ticker(symbol, session=session)`
  so every internal call (history, options, option_chain) uses the header.
- Replaced flat 5s sleep on 429 in `_get_expirations` with escalating back-off: 10s → 30s → 60s.
- Added `requests` explicitly to `requirements.txt`.

**Files changed:**
- `options_engine.py` — session creation + escalating 429 back-off
- `requirements.txt` — added `requests`

**Commit:** `5e955c7`

---

### 2. NVDIA Typo Identified (pending manual fix)

**Problem:** Watchlist contains `NVDIA` instead of `NVDA`. EODHD returns 404 for
`NVDIA.US`. Dashboard shows "Invalid or missing price data" for that row.

**Fix:** Log into the live app, remove `NVDIA`, re-add `NVDA` from the dashboard.
(Data lives in Render PostgreSQL — no code change needed.)

**Status:** Not yet fixed — user will do this when testing tomorrow.

---

## Full Issue Backlog (Priority Order)

### P1 — Bugs (not yet fixed)

**A. `remove_ticker` has no auth guard** (`app.py:291-292`)
All other protected routes check `if "user_id" not in session` before proceeding.
`remove_ticker` hits `session["user_id"]` directly — unauthenticated request → 500 KeyError.

**B. RSI hardcoded to 50 in CSP scanner** (`options_engine.py` — `_build_indicator_data_from_hist`)
`rsi = 50` is a hardcoded placeholder — RSI is never computed in the CSP path.
Always evaluates to "neutral"; BUY signals (require oversold) can never fire.
The **dashboard** path (`fetch_snapshot` via EODHD) computes real RSI correctly — only the CSP scanner is affected.
Fix: compute RSI from the `hist` DataFrame already in hand (same pandas formula as `market_data/provider.py`).

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
- `options_engine.py` — CSP scanner (yfinance, scoring, caching)
- `top_csp.py` — background refresh thread + ThreadPoolExecutor scan
- `market_data/provider.py` — EODHD market data fetch + RSI calculation
- `trade_advisor.py` — StrategyEngine (200/50 DMA, RSI, 52w positioning)
- `requirements.txt` — added `psycopg2-binary`, `requests`
- `render.yaml` — Render PostgreSQL + `DATABASE_URL` wiring
- `templates/top_csp.html` — "Scan in progress" cold-start message

## Commits This Session
- `5e955c7` — Fix Yahoo Finance rate limiting: apply User-Agent session to yf.Ticker, escalate 429 back-off

## Commits Previous Session (2026-06-17)
- `a9709ae` — Migrate database layer to support Render PostgreSQL
- `54f13d5` — Move top-csp scan off request path into background thread
- `ce108f9` — Validate DATABASE_URL format before using psycopg2
- `c3f7845` — Expand watchlist to 8 symbols, parallelize scan with ThreadPoolExecutor
