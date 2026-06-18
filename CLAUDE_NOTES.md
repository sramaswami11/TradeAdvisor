# TradeAdvisor — Session Notes
Date: 2026-06-17

---

## What We Accomplished Today

### 1. Confirmed Render Start Command Fix (DONE — from previous session)
User confirmed the Render dashboard Start Command was updated to:
```
gunicorn app:app --bind 0.0.0.0:$PORT --workers 2 --timeout 120
```

---

### 2. Migrated Database from SQLite to Render PostgreSQL (DONE — committed & deployed)

**Problem:** `trade_advisor.db` lived in the project folder on Render's server. Every deploy wiped it — all user accounts and watchlists were lost.

**Solution:** Migrated to Render PostgreSQL (free tier).

**Files changed:**
- `database.py` — auto-detects `DATABASE_URL` env var. If set and starts with `postgres://` or `postgresql://`, uses `psycopg2`. Otherwise falls back to SQLite for local dev. Key SQL differences handled: `SERIAL PRIMARY KEY` vs `AUTOINCREMENT`, `%s` vs `?` placeholders, `ON CONFLICT DO NOTHING` vs `INSERT OR IGNORE`.
- `requirements.txt` — added `psycopg2-binary==2.9.9`
- `render.yaml` — added `databases:` block (free-tier Render PostgreSQL) with `DATABASE_URL` wired into the web service via `fromDatabase`

**Caveat:** The `databases:` block in render.yaml only auto-provisions for Blueprint-deployed services. Since this service was created manually via dashboard, the PostgreSQL database had to be created manually in the Render dashboard and `DATABASE_URL` set in the Environment tab.

**Crash fix:** Added URL format validation — `_POSTGRES` only activates if `DATABASE_URL` starts with `postgres://` or `postgresql://`. Prevents crash when Render sets a malformed/empty `DATABASE_URL` before the DB is provisioned.

---

### 3. Moved `/top-csp` Scan Off the Request Path (DONE — committed & deployed)

**Problem:** The CSP scan ran synchronously inside a gunicorn worker, blocking for ~40s on cold cache. With only 2 symbols, this was barely tolerable; with 8 it would be fatal.

**Solution:** Background daemon thread. `get_top_csp_opportunities()` now always returns from cache instantly. The thread starts on first request (avoids gunicorn pre-fork issue), scans immediately, then sleeps for 1 hour and repeats.

**Cold start behavior:** Returns `[]` with a "Scan in progress — check back in a minute" message in the template instead of blocking.

**Files changed:**
- `top_csp.py` — extracted `_do_scan()`, added `_background_refresh_loop()` and `_ensure_bg_thread()`
- `templates/top_csp.html` — added `{% else %}` clause to `{% for %}` loop with "Scan in progress" message

---

### 4. Expanded Watchlist + Parallelized Scan (DONE — committed & deployed)

**WATCHLIST** updated from `["SPY", "QQQ"]` to:
```python
["HOOD", "SOFI", "GDX", "DAL", "IBKR", "SPY", "NVDA", "XLE"]
```

**Performance:** Used `ThreadPoolExecutor(max_workers=3)` to scan 3 symbols concurrently. I/O-bound Yahoo Finance calls benefit from threading (GIL released during network I/O). Worker count capped at 3 to avoid Yahoo Finance 429 rate limits. Scan time stays comparable to the old 2-symbol sequential scan.

---

## Remaining Issues (Priority Order)

### Priority 3 — Low: Duplicate database files (local only)
`trade_advisor.db` and `tradeadvisor.db` both exist locally. `trade_advisor.db` is what the code uses. `tradeadvisor.db` (65KB, Jan 26) is old/dead. Both are gitignored. Can be deleted anytime — irrelevant now that we're on PostgreSQL in production.

### Priority 5 — Low: `/tmp` caches lost on restart
`expiration_cache.json`, `top_csp_cache.json`, and `snapshot_cache_*.json` live in `/tmp`. Render wipes `/tmp` on full redeploy. After a deploy:
- `top_csp` warms automatically via background thread (~40–60s for 8 symbols with 3 workers)
- `expiration_cache` and `snapshot_cache` warm on first real user request

Option if this becomes annoying: store caches in the PostgreSQL `cache` table with `(key, value, timestamp)`.

---

## Key Files
- `database.py` — SQLite/PostgreSQL dual-backend, controlled by `DATABASE_URL`
- `requirements.txt` — added `psycopg2-binary==2.9.9`
- `render.yaml` — Render PostgreSQL database + `DATABASE_URL` wiring
- `top_csp.py` — background refresh thread + ThreadPoolExecutor scan
- `templates/top_csp.html` — "Scan in progress" cold-start message

## Commits This Session
- `a9709ae` — Migrate database layer to support Render PostgreSQL
- `54f13d5` — Move top-csp scan off request path into background thread
- `ce108f9` — Validate DATABASE_URL format before using psycopg2
- `c3f7845` — Expand watchlist to 8 symbols, parallelize scan with ThreadPoolExecutor
