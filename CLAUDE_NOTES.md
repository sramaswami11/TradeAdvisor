# TradeAdvisor — Session Notes
Date: 2026-06-14

---

## What We Accomplished Today

### 1. Architecture Analysis
Produced a full architecture report saved in `ARCHITECTURE.md` covering:
- All Flask routes (10 total)
- Major modules and their responsibilities
- Complete CSP opportunity generation pipeline
- Database schema, caching layers, deployment config

### 2. Root Cause Analysis — "Too Many Requests" on Render
Identified 6 confirmed causes of Yahoo Finance rate limiting:
- `YAHOO_HEADERS` User-Agent was defined but never applied (dead code)
- Up to 5 option chain fetches fired back-to-back with zero delay
- Retry loops re-hit Yahoo after only 3s flat — no awareness of 429 responses
- Two separate `OptionsEngine()` instances with isolated caches (doubled Yahoo calls)
- Unauthenticated `/debug-options` and `/debug-history` endpoints leaked uncached Yahoo calls
- 2-second inter-symbol delay in `/top-csp` was too short for the burst of sub-requests per symbol

### 3. Rate Limiting Fixes Applied
All changes are committed-ready in the working tree.

| Fix | File | Detail |
|-----|------|--------|
| 1-second delay between option chain fetches | `options_engine.py:187` | Eliminates per-scan burst |
| Exponential backoff on retries | `options_engine.py:101, 378` | 15→30→60s on 429, 3→6→12s otherwise |
| Shared singleton `OptionsEngine` | `options_engine.py`, `app.py`, `top_csp.py` | One cache shared across all routes |
| Auth-gate debug endpoints | `app.py:385, 412` | Returns 401 without session |
| Inter-symbol delay raised 2s → 10s | `top_csp.py:43` | Covers the sub-request burst per symbol |

**Note on User-Agent (Fix 1):** We initially added a `requests.Session` with browser headers, then reverted it. Reason: the installed yfinance 0.2.66 already uses `curl_cffi.requests.Session(impersonate="chrome")` which spoofs TLS fingerprints at the SSL level — far stronger than a header. Overriding it with a plain `requests.Session()` would have made things worse.

### 4. Persistent Cache for `/top-csp`
Added `top_csp_cache.json` (1-hour TTL, stored in `/tmp`).
- First load after cold start or expiry: runs full Yahoo scan, saves result
- All subsequent loads within 1 hour: served instantly from cache, zero Yahoo calls
- UI unchanged

---

## Render Deployment Risks Identified (Not Yet Fixed)

### Critical
- **SQLite wiped on every deploy** — `trade_advisor.db` is in the working directory. Render wipes the filesystem on each new deployment. All user accounts and watchlists are lost.
- **`init_db()` won't run under gunicorn** — it's inside `if __name__ == "__main__"` (app.py line 428). If start command is changed to gunicorn, DB tables are never created and the app crashes on first DB call.
- **Wrong start command** — `render.yaml` uses `python app.py` (Flask dev server). Should be `gunicorn app:app --bind 0.0.0.0:$PORT`. Gunicorn is already in `requirements.txt` but unused.

### High
- **`/top-csp` blocks entire app for ~30 seconds** — Flask dev server is single-threaded. While the CSP scan runs, no other request (including login) can be served.
- **Missing env vars not documented** — `FLASK_SECRET_KEY` crashes the app at startup if missing. `EODHD_API_KEY` silently breaks the dashboard. Neither is listed as required in `render.yaml`.

### Medium
- **Two database files** — `trade_advisor.db` and `tradeadvisor.db` both exist. Unclear which the live app uses. Needs investigation.
- **`/tmp` caches lost on restart** — `expiration_cache.json` and `top_csp_cache.json` are in `/tmp`, wiped on Render restart. First post-restart `/top-csp` load triggers a cold Yahoo Finance burst.

---

## Recommended Next Steps (Priority Order)

### Step 1 — Fix `init_db()` placement (5 minutes)
Move it to module level so it runs under both `python app.py` and gunicorn:
```python
# app.py — call at module level, not inside __main__
init_db()

if __name__ == "__main__":
    app.run()
```

### Step 2 — Switch to gunicorn in render.yaml (5 minutes)
```yaml
startCommand: gunicorn app:app --bind 0.0.0.0:$PORT --workers 2
```

### Step 3 — Fix the database persistence problem
Options (pick one):
- **Render PostgreSQL** (free tier available) — replace SQLite with postgres, use `psycopg2` + env var `DATABASE_URL`
- **Render Persistent Disk** (paid, $1/month) — keep SQLite, mount disk at `/data`, point DB path there
- **PlanetScale / Supabase** (free hosted DB) — external managed DB, no Render dependency

### Step 4 — Resolve duplicate database files
Check which file the live app actually reads, delete the other, confirm in code.

### Step 5 — Document required env vars in render.yaml
Add to `render.yaml`:
```yaml
envVars:
  - key: FLASK_SECRET_KEY
    generateValue: true
  - key: EODHD_API_KEY
    sync: false
  - key: ADMIN_EMAIL
    sync: false
```

### Step 6 — Make `/top-csp` non-blocking (longer term)
Options:
- Run the scan in a background thread on app startup, serve stale cache while refreshing
- Use Render's cron job to pre-populate `top_csp_cache.json` on a schedule
- Move to a proper task queue (Celery + Redis) if the watchlist grows

---

## Key Files Changed Today
- `options_engine.py` — rate limit fixes, singleton `get_shared_engine()`
- `app.py` — uses shared engine, debug endpoints auth-gated
- `top_csp.py` — uses shared engine, 10s delay, persistent cache added
- `ARCHITECTURE.md` — full codebase reference (created today)
- `CLAUDE_NOTES.md` — this file
