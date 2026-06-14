# TradeAdvisor — Architecture & Technical Reference

## Table of Contents
1. [Architecture Overview](#1-architecture-overview)
2. [Major Modules](#2-major-modules)
3. [Flask Routes](#3-flask-routes)
4. [CSP Opportunity Generation](#4-csp-opportunity-generation)
5. [Database Schema](#5-database-schema)
6. [Caching Strategy](#6-caching-strategy)
7. [Configuration & Deployment](#7-configuration--deployment)

---

## 1. Architecture Overview

TradeAdvisor is a synchronous Flask web application that evaluates equities for trading opportunities and scans options chains for Cash Secured Put (CSP) setups. It runs as a single-process server with no background workers.

```
Browser
  │
  ▼
Flask (app.py)
  ├── Session-based auth (no passwords)
  ├── SQLite (users + watchlists via database.py)
  ├── Market snapshots (market_data/ → eodhd.com API)
  ├── Trade signals (trade_advisor.py → StrategyEngine)
  └── Options scanning (options_engine.py → Yahoo Finance via yfinance)
```

**Data source split:**
- **Equity snapshots** (price, DMAs, RSI): `eodhd.com` REST API — cached to SQLite + LRU
- **Option chains & history**: Yahoo Finance via `yfinance` — cached in memory (30 min) + disk (24 h for expirations)

**Auth model:** Email-only login creates a user row on first visit. User ID is stored in the Flask session cookie. No passwords. Admin is identified by matching `ADMIN_EMAIL` env var.

---

## 2. Major Modules

### `app.py` — Flask Application (430 lines)
Entry point. Declares all routes, initializes a singleton `OptionsEngine`, and wires together authentication, database calls, and rendering.

Notable helpers:
- `normalize_symbol(symbol)` — uppercases and strips non-alphanumeric chars before any ticker is used
- `build_row(symbol)` — calls market snapshot + StrategyEngine for a single ticker, returns a dict suitable for the dashboard table
- `ensure_default_tickers_for_user(user_id)` — seeds `["SPY", "QQQ"]` for new accounts

### `trade_advisor.py` — StrategyEngine (164 lines)
Pure scoring logic with no I/O. Accepts a market data dict and emits a BUY / SELL / HOLD signal with 0–100 % confidence.

Scoring (max 4 points → 100 %):
| Signal | Points |
|--------|--------|
| Price > 200 DMA | 1 |
| Price > 50 DMA | 1 |
| RSI oversold | 1 |
| Price near 52-week low | 1 |

BUY requires score ≥ 3 and above both DMAs. SELL requires near 52-week high and not oversold. HOLD is the fallback.

### `options_engine.py` — OptionsEngine (619 lines)
CSP scanner. Fetches 1-year price history, validates the trend, iterates option expirations, filters puts, scores each contract, and returns a sorted list of opportunities.

Key constants:
| Constant | Value | Purpose |
|----------|-------|---------|
| `MAX_EXPIRATIONS_TO_SCAN` | 5 | Caps yfinance calls per symbol |
| `EXPIRATION_CACHE_SECONDS` | 86 400 (24 h) | Disk TTL for expiration dates |
| `OPTION_CHAIN_CACHE_SECONDS` | 1 800 (30 min) | Memory TTL for option chains |

### `top_csp.py` — Watchlist Screener (71 lines)
Iterates a hardcoded `WATCHLIST = ["SPY", "QQQ"]`, collects the top 3 CSP opportunities per symbol (2-second delay between symbols for rate limiting), and returns the top 15 overall ranked by score.

### `database.py` — SQLite Layer (144 lines)
Thin wrapper around sqlite3. All functions return plain dicts or lists; no ORM.

### `market_data/` — Market Snapshot Pipeline
| File | Role |
|------|------|
| `provider.py` | Calls `eodhd.com`, computes RSI, returns snapshot dict |
| `cache.py` | Dual-layer (memory dict + SQLite `market_cache` table) with EOD expiry |
| `service.py` | Thin `get_market_snapshot(ticker)` facade |

### `email_utils.py` — Mailjet Integration (235 lines)
Disabled by default (`ENABLE_EMAIL=false`). Provides single and bulk send with retry logic and an HTML template builder.

### `validators.py` — Input Sanitization (265 lines)
Centralizes all validation: email regex, ticker sanitization (blocks SQL/XSS patterns), name normalization, HTML escaping.

---

## 3. Flask Routes

| Method | Path | Handler | Auth Required | Description |
|--------|------|---------|---------------|-------------|
| GET | `/` | `index` | No | Redirects to `/dashboard` if logged in, else `/login` |
| GET / POST | `/login` | `login` | No | Email sign-in / sign-up; creates user on first visit |
| GET / POST | `/dashboard` | `dashboard` | Yes | Watchlist table with BUY/SELL/HOLD ratings; POST adds a ticker |
| GET | `/csp/<symbol>` | `view_csp` | Yes | CSP opportunities for a single symbol |
| GET | `/remove/<symbol>` | `remove_ticker` | Yes | Removes a ticker from the user's watchlist |
| GET / POST | `/admin/upload-users` | `admin_upload_users` | Admin only | Bulk import users + tickers from JSON |
| GET | `/top-csp` | `top_csp` | Yes | Top 15 CSP opportunities across the hardcoded watchlist |
| GET | `/logout` | `logout` | No | Clears session |
| GET | `/debug-options` | `debug_options` | No | Returns SPY option count (dev only) |
| GET | `/debug-history` | `debug_history` | No | Returns SPY history row count (dev only) |

---

## 4. CSP Opportunity Generation

### What is a CSP?
A **Cash Secured Put** is a neutral-to-bullish options strategy: sell a put option below the current price, collect premium, and accept the obligation to buy the stock only if it falls to the strike. The risk is defined; the profit is the premium received.

### End-to-End Pipeline

```
GET /csp/<symbol>
  │
  └─ options_engine.find_csp_opportunities(symbol)
       │
       ├─ [1] Fetch Price History
       │     yf.Ticker(symbol).history(period="1y")
       │     Retries: 3×, 3-second delay
       │     Output: DataFrame with daily Close prices
       │
       ├─ [2] Calculate Indicators
       │     _build_indicator_data_from_hist(hist, price)
       │     ├── dma_50  = Close.rolling(50).mean().iloc[-1]
       │     ├── dma_200 = Close.rolling(200).mean().iloc[-1]
       │     ├── 52w_high = Close.max()
       │     └── 52w_low  = Close.min()
       │
       ├─ [3] Evaluate Trend
       │     StrategyEngine(data).evaluate()
       │     Emits: above_200_dma, above_50_dma, rsi_state, position_zone
       │
       ├─ [4] Trend Gate  ← HARD FILTER
       │     If NOT above_200_dma → return []
       │     (Only scan stocks in an established uptrend)
       │
       ├─ [5] Fetch & Cache Expirations
       │     _get_expirations(ticker, symbol)
       │     ├── Check expiration_cache.json (24-h TTL)
       │     └── On miss: yf.Ticker.options → list of date strings
       │
       ├─ [6] Filter Expirations
       │     Keep: 5 ≤ DTE ≤ 45
       │     Sort ascending by DTE
       │     Take first 5 (MAX_EXPIRATIONS_TO_SCAN)
       │
       ├─ [7] For Each Expiration — Fetch & Filter Puts
       │     _get_cached_option_chain(ticker, expiry)  ← 30-min memory cache
       │     chain.puts DataFrame → iterate each row:
       │
       │     a) OTM Range Filter:
       │        distance_pct = (strike − price) / price
       │        Keep if: −0.18 ≤ distance_pct ≤ −0.02
       │        (2 % to 18 % below spot price)
       │
       │     b) Liquidity Filter:
       │        spread_pct = (ask − bid) / ask
       │        Keep if: spread_pct < 0.50 (spread < 50 %)
       │
       │     c) Return Calculation:
       │        premium     = max(lastPrice, mid_price, bid)
       │        yield_pct   = premium / strike
       │        annualized  = yield_pct × (365 / dte)
       │
       ├─ [8] Score Each Candidate
       │     _score_csp(signals, yield_pct, annualized, distance_pct)
       │
       │     Trend signals (max 3):
       │       +2  above_200_dma
       │       +1  above_50_dma
       │       +1  rsi_state == "neutral"
       │
       │     Yield (max 3):
       │       +1  yield_pct > 0.5 %
       │       +2  yield_pct > 1.0 %
       │       +1  annualized > 10 %
       │       +1  annualized > 20 %
       │
       │     Safety margin (max 2):
       │       +1  distance_pct < −7 %
       │       +1  distance_pct < −15 %
       │
       │     Labels:
       │       ≥ 8 → STRONG
       │       ≥ 5 → GOOD
       │       ≥ 3 → OK
       │        < 3 → WEAK
       │
       ├─ [9] Build Result Dicts
       │     Each passing put becomes:
       │     {
       │       symbol, strategy="CSP",
       │       price, strike, expiry, dte,
       │       premium, yield_pct, annualized,
       │       distance_pct, score, recommendation
       │     }
       │
       └─ [10] Sort & Return
             Sort all opportunities by score DESC
             → render csp_results.html
```

### Hard Filters Summary
| Filter | Rule |
|--------|------|
| Trend gate | Stock must be above 200-day MA |
| DTE window | 5 – 45 days to expiration |
| OTM range | Strike 2 % – 18 % below spot |
| Liquidity | Bid-ask spread < 50 % |
| Premium | Non-zero bid, ask, or last price |

### Top-CSP Screener (`/top-csp`)
Runs the same pipeline for each symbol in `WATCHLIST`, takes the top 3 per symbol, merges, and returns the top 15 by score. A 2-second sleep between symbols avoids Yahoo Finance rate limits.

---

## 5. Database Schema

```sql
CREATE TABLE users (
  id    INTEGER PRIMARY KEY AUTOINCREMENT,
  email TEXT    UNIQUE NOT NULL,
  name  TEXT
);

CREATE TABLE user_tickers (
  id      INTEGER PRIMARY KEY AUTOINCREMENT,
  user_id INTEGER NOT NULL REFERENCES users(id),
  symbol  TEXT    NOT NULL,
  UNIQUE (user_id, symbol)
);

-- market_data/cache.py
CREATE TABLE market_cache (
  ticker    TEXT PRIMARY KEY,
  payload   TEXT,     -- JSON-serialized snapshot
  timestamp INTEGER   -- Unix epoch seconds
);
```

---

## 6. Caching Strategy

| Layer | Storage | TTL | What is cached |
|-------|---------|-----|----------------|
| LRU (memory) | Python `@lru_cache(256)` | Process lifetime | `fetch_snapshot()` results |
| Dual-layer | Memory dict + `market_cache` SQLite table | End-of-day (calendar day boundary) | Market snapshots from eodhd.com |
| Disk JSON | `expiration_cache.json` | 24 hours | Option expiration date lists per symbol |
| Memory dict | `OptionsEngine._option_chain_cache` | 30 minutes | Full option chains per (symbol, expiry) |

The expiration cache survives process restarts; the option chain cache is ephemeral and rebuilds on each deployment.

---

## 7. Configuration & Deployment

### Environment Variables (`.env`)
| Variable | Default | Purpose |
|----------|---------|---------|
| `ENABLE_EMAIL` | `false` | Feature flag for Mailjet email sending |
| `MAILJET_API_KEY` | — | Mailjet credential |
| `MAILJET_API_SECRET` | — | Mailjet credential |
| `EMAIL_FROM` | `alerts@tradeadvisor.com` | Sender address |
| `EMAIL_FROM_NAME` | `TradeAdvisor` | Sender display name |
| `ADMIN_EMAIL` | `tradeadvisor2025@gmail.com` | Email that gets admin privileges |
| `EODHD_API_KEY` | — | API key for eodhd.com market data |
| `DATABASE_URL` | `sqlite:///tradeadvisor.db` | SQLite path |

### Key Dependencies
| Package | Version | Role |
|---------|---------|------|
| Flask | 3.0.0 | Web framework |
| yfinance | 0.2.66 | Option chains + price history |
| pandas | 2.3.3 | Rolling averages, DataFrame ops |
| gunicorn | 21.2.0 | Production WSGI server |
| Flask-Limiter | 3.5.0 | Rate limiting |
| mailjet-rest | — | Email API client |

### Render Deployment (`render.yaml`)
- Runtime: Python 3.11.8
- Build command: `pip install -r requirements.txt`
- Start command: `python app.py`
- No background workers configured; all processing is synchronous and on-request.

### Templates
| Template | Route | Purpose |
|----------|-------|---------|
| `login.html` | `/login` | Email sign-in / sign-up |
| `dashboard.html` | `/dashboard` | Watchlist with trade ratings |
| `csp_results.html` | `/csp/<symbol>` | CSP opportunities table for one stock |
| `top_csp.html` | `/top-csp` | Cross-watchlist CSP screener results |

Color coding in `csp_results.html`: STRONG = green, GOOD = teal, OK = orange, WEAK = red.
