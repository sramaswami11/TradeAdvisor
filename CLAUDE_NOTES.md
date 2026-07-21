# TradeAdvisor — Session Notes

---

## Session: 2026-07-20

### 1. yfinance IP Blocking — Hosting Change Not Worth It

Investigated whether a paid Render plan or different hosting provider (DigitalOcean, Hetzner, etc.) could avoid Yahoo Finance's data center IP blocking.

**Conclusion: No hosting change reliably solves this under $29/mo.**
- Yahoo blocks data center IP ranges (AWS, GCP, independent VPS) — it's IP classification, not request volume
- Render paid plans still use AWS — upgrading doesn't change the outbound IP range
- Smaller VPS (Hetzner, DigitalOcean) might work temporarily but Yahoo expands blocklists over time
- Residential proxies are the only reliable fix, but cost $50–200+/mo — more than Massive
- **Confirmed: Massive $29/mo is the right path. Proceeding tomorrow.**

---

### 2. Earnings Penalty in CSP/CC Scoring — BUILT & DEPLOYED (commits `98ec07a`, `aaf1621`)

**Problem identified:** IBKR showing score 10 STRONG on Top CSP despite earnings the next day (July 21). Scoring function had no awareness of earnings proximity — the `near_earnings` flag was display-only (⚠ EARN badge) with zero effect on score. Pre-earnings IV inflation was actually boosting the score by inflating annualized yield.

**Fix 1 — Add -2 penalty (commit `98ec07a`):**
- `_score_csp` and `_score_cc` both accept `near_earnings=False` parameter
- Deduct 2 points when `near_earnings=True`; floor at 0 via `max(score, 0)`
- Call site in `_find_opportunities` passes `near_earnings` to whichever scorer runs
- 3 new tests: deduction for CSP, deduction for CC, floor at zero

**Bug found during verification:** IBKR still showed 10 STRONG after deploy + cache clear.
Root cause: original check was `abs(expiry - earnings) <= 5 days`. IBKR expiry July 31, earnings July 21 = 10 days apart → no flag, no penalty. But the contract spans the earnings event — holder is fully exposed.

**Fix 2 — Correct the earnings check (commit `aaf1621`):**
- Changed from `abs((expiry_date_obj - earnings_date).days) <= 5`
- To `earnings_date <= expiry_date_obj`
- Meaning: flag any contract whose expiry is on or after earnings date (earnings fall within the hold period)
- Contracts expiring before earnings are correctly unaffected
- Updated 3 tests to match new semantics (spans, expires-before, same-day cases)

**Verified on Render:** IBKR July 31 contract dropped from 10 STRONG → 8 STRONG, ⚠ EARN badge showing in Expiry column. Cache cleared via `/admin` after each deploy.

**76/76 tests passing.**

---

## Current State (end of 2026-07-20)

- **App:** Live on Render ✓ · latest commit `aaf1621`
- **Earnings penalty:** Active — CSP/CC contracts spanning an earnings event score -2 ✓
- **Data source:** Still on yfinance — blocked on Render for options (Massive $29/mo is next)
- **Tradier sandbox URL support:** Committed (`98ec07a`) · NOT activated (no key)
- **Report page:** `/report/<symbol>` live — `/report/CSCO` still unverified (EPS fields, all four cards)
- **Wheel Candidate fix:** Not started — deferred again

---

## Pending for Next Session (2026-07-21)

### 1. Sign up for Massive Options Starter ($29/mo) — first thing
Email-only signup at massive.com. Grab API key. Run `polygon_poc/` locally to confirm greeks populate. Then integrate `MassiveOptionsProvider` into TradeAdvisor using same 2-method interface (`get_expirations`, `get_chain`).

### 2. Verify `/report/CSCO` on Render (carried over 5 days)
Confirm EPS fields show `$1.06 actual / $1.04 estimate / +2.29%` and all four cards render.

### 3. Wheel Candidate verdict fix (carried over 5 days)
In report route, change `is_wheel_candidate`:
```python
# current
bool(csp_opps) and confidence >= 50
# proposed
bool(csp_opps) and (confidence >= 50 or (top_csp.score >= 8 and signals.get("above_200_dma")))
```

### 4. Agentic build — Phase 1 (when ready)
Formalize tool contracts for `fetch_snapshot`, `fetch_options_chain`, `score_csp` into explicit input/output schemas per `TAredesign.md`.

---

## Commits This Session (2026-07-20)
- `98ec07a` — Add Tradier sandbox support; penalize CSP/CC score -2 when near earnings
- `aaf1621` — Fix earnings penalty — flag any contract that spans an earnings event

---

## Session: 2026-07-19

### 1. Tradier SSN/DOB Risk — Decision Made

Evaluated whether giving PII (SSN, DOB) to Tradier to open a brokerage account was worth it for API access.

**Conclusion: Not worth it for this use case.**
- Tradier is FINRA-regulated — SSN/DOB collection is legally required (KYC/AML), not optional
- Risk is real: adds SSN to another data store, may trigger credit pull, creates an ongoing brokerage account relationship
- The purpose mismatch is the key issue: high PII exposure just to avoid a $29/mo API fee for a dev tool
- **Massive $29/mo (email-only signup, POC already built) is the clear preferred path**

---

## Current State (end of 2026-07-19)

- **App:** Live on Render ✓ · commit `bc776c1` (unchanged today)
- **Tradier sandbox URL support:** Code complete, 72 tests passing — NOT committed, NOT activated
- **Data source:** Still on yfinance — blocked on Render for options
- **Report page:** `/report/<symbol>` live — `/report/CSCO` still unverified on Render (EPS fields, all four cards)
- **Wheel Candidate fix:** Not started — deferred again

---

## Pending for Next Session (2026-07-20)

### 1. Sign up for Massive Options Starter ($29/mo) — first thing
Email-only signup at massive.com. Grab API key. Run `polygon_poc/` locally to confirm greeks populate. Then integrate `MassiveOptionsProvider` into TradeAdvisor using the same 2-method interface (`get_expirations`, `get_chain`).

### 2. Verify `/report/CSCO` on Render (carried over 4 days)
Confirm EPS fields show `$1.06 actual / $1.04 estimate / +2.29%` and all four cards render.

### 3. Wheel Candidate verdict fix (carried over 4 days)
In report route, change `is_wheel_candidate`:
```python
# current
bool(csp_opps) and confidence >= 50
# proposed
bool(csp_opps) and (confidence >= 50 or (top_csp.score >= 8 and signals.get("above_200_dma")))
```

### 4. Agentic build — Phase 1 (when ready)
Formalize tool contracts for `fetch_snapshot`, `fetch_options_chain`, `score_csp` into explicit input/output schemas per `TAredesign.md`.

---

## Commits This Session (2026-07-19)
- None — research and decision session only

---

## Session: 2026-07-18

### 1. Massive.com Pricing — Checked

**Options Basic ($0/mo):** Includes All US Options Tickers, 5 API Calls/Minute, 2 Years Historical,
Technical Indicators. But **Snapshot is crossed out** — the exact endpoint the POC needs.
Free tier won't work for our use case.

**Options Starter ($29/mo):** Includes everything — Snapshot ✓, Real-time Greeks and IV ✓,
Daily Open Interest ✓, Unlimited API Calls ✓, 15-minute delayed data ✓.
This tier unblocks the `polygon_poc/` immediately.

**Decision deferred** — see section 3 below.

---

### 2. Tradier Sandbox — Researched

**Data quality confirmed from docs:** Tradier sandbox uses **real market data, 15-minute delayed**
(not simulated). Greeks available via ORATS integration (delta, gamma, theta, vega, rho, phi).
`greeks=true` param already in our `tradier.py` — no changes needed there.

**Blocker discovered:** Tradier requires a **full brokerage account even for sandbox access** —
SSN, DOB, the works. It's a FINRA-regulated broker-dealer. There is no lightweight
developer-only signup path.

---

### 3. Tradier Sandbox URL Support — BUILT (not yet activated)

Added `TRADIER_SANDBOX=true` env var support so the base URL switches between production
and sandbox without code changes.

**`market_data/tradier.py`:**
- Replaced module-level `_BASE` constant with `_BASE_PROD` and `_BASE_SANDBOX`
- `TradierOptionsProvider.__init__` now accepts `sandbox: bool = False`
- Constructor sets `self._base` accordingly; both `get_expirations` and `get_chain` use `self._base`

**`options_engine.py`:**
- `_make_options_provider()` reads `TRADIER_SANDBOX` env var
- Passes `sandbox=True` to constructor when set

**`.env`:**
- Added `TRADIER_API_KEY=` and `TRADIER_SANDBOX=true` placeholders

**72/72 tests passing** — no `TRADIER_API_KEY` in test env so yfinance/mock path runs as before.

---

### 4. Data Source Decision — Pending

| Option | Cost | Data | Friction |
|---|---|---|---|
| Massive Options Starter | $29/mo | Real, 15-min delayed | Email signup, POC already built |
| Tradier (sandbox or prod) | Free | Real, 15-min delayed | Full brokerage account (SSN required) |
| Keep yfinance | Free | 15-min delayed, blocked on Render | No change |

**Leaning toward Massive $29/mo** — email-only signup, POC already built and working mechanically,
no personal data required. $29/mo is reasonable to validate before committing.

---

## Current State (end of 2026-07-18)

- **App:** Live on Render ✓ · commit `bc776c1` (unchanged today)
- **Tradier sandbox URL support:** Code complete, 72 tests passing — NOT activated (no key)
- **Data source:** Still on yfinance — blocked on Render for options
- **Report page:** `/report/<symbol>` live — still unverified (lxml install, EPS fields)
- **Wheel Candidate fix:** Not started — deferred again

---

## Pending for Next Session (2026-07-19)

### 1. Pick a data source (first decision of the day)
- **Massive $29/mo** → sign up, grab API key, run `polygon_poc/` locally to confirm greeks populate,
  then integrate `MassiveOptionsProvider` into TradeAdvisor using the same 2-method interface
- **Tradier** → open free brokerage account (no funding needed, but SSN required),
  grab sandbox token, drop into `.env` as `TRADIER_API_KEY`, hit `/csp/NVDA` locally

### 2. Verify `/report/CSCO` on Render (carried over 3 days)
Confirm EPS fields show `$1.06 actual / $1.04 estimate / +2.29%` and all four cards render.

### 3. Wheel Candidate verdict fix (carried over 3 days)
In report route, change `is_wheel_candidate`:
```python
# current
bool(csp_opps) and confidence >= 50
# proposed
bool(csp_opps) and (confidence >= 50 or (top_csp.score >= 8 and signals.get("above_200_dma")))
```

### 4. Agentic build — Phase 1 (when ready)
Formalize tool contracts for `fetch_snapshot`, `fetch_options_chain`, `score_csp`
into explicit input/output schemas per `TAredesign.md`.

---

## Commits This Session (2026-07-18)
- None — research + code change for Tradier sandbox URL support (uncommitted)

---

## Session: 2026-07-17

### 1. Schwab Trader API — Commercial Use Research

Investigated whether Schwab Trader API (formerly TD Ameritrade API) could power a shared
data feed for TradeAdvisor (one set of credentials, serve all users).

**Website ToS analyzed** — turned out to be the developer portal ToS only, not the API agreement.
The actual governing document is the **Developer Program Agreement** (accepted at registration).

**Searched for TD Ameritrade / Schwab API commercial terms. Key findings:**

Two tiers exist:
- **Individual (free)** — requires Schwab brokerage account, OAuth per-user, personal/restricted-distribution only. **Explicitly prohibits data redistribution and large-scale integrations.**
- **Commercial / Redistribution** — custom contract + exchange-data agreements. Likely $thousands/month.

**Verdict:** Using one set of Schwab credentials to serve multiple users = prohibited under free tier.

**The one permitted architecture:** Per-user OAuth — each TradeAdvisor user connects their own Schwab account. This is permitted but narrows the audience to Schwab account holders.

---

### 2. What People Actually Build with Schwab Trader API

Researched real use cases:
- Personal algo bots (most common) — fetch signal, auto-place trade
- Portfolio monitors — track positions and P&L in custom UI
- Backtesting engines — historical options chains
- Open-source wrappers — `schwab-py`, `schwabr`, `lumibot`

**The real unlock is order execution** — not just better data quality. Per-user OAuth becomes a
*feature* ("connect your Schwab account to trade directly from scan results") rather than a limitation.
This turns TradeAdvisor from a screener into a trading workflow.

**Near-term verdict:** Tradier for data (designed for multi-user apps, ~$10–50/mo or free sandbox).
**Long-term direction:** Schwab per-user OAuth + order execution = compelling product differentiator.

---

### 3. Agentic AI Redesign — Blueprint Created

Discussed transforming TradeAdvisor into a production-grade agentic AI system, using the
framework from Aishwarya Srinivasan's (Gen Academy) agentic AI system design video.

**Full blueprint written to `TAredesign.md`** in the project root.

Key design decisions documented:
- **Single-agent** to start (workflow is linear enough)
- **Model routing**: Haiku for intent classification/routing, Sonnet/Opus only for synthesis and ambiguous-signal reasoning
- **Tool contracts**: read tools (no gate), low-risk write tools, high-risk write tools (approval gate)
- **State vs memory**: workflow state in Redis/Postgres per session; long-term memory in existing Postgres tables
- **Orchestration**: deterministic state machine first, agentic reasoning only where genuinely needed
- **Approval gates**: `place_order` always requires explicit user confirmation — never fires from model inference alone
- **Build order**: tool contracts → orchestration → synthesis Claude call → Schwab order execution → evals

**What already exists (no rework needed):** fetch_snapshot, fetch_options_chain, score_csp/cc,
fetch_fundamentals, iv_history, background scanner, 72 pytest tests.
What's missing: orchestration layer + synthesis model call.

---

## Current State (end of 2026-07-17)

- **App:** Live on Render ✓ · commit `bc776c1` (unchanged today)
- **Report page:** `/report/<symbol>` live — not re-verified today
- **polygon_poc/:** Built, blocked on free tier — Massive pricing still unchecked
- **Tradier:** Code complete, not yet activated
- **TAredesign.md:** Agentic AI system design blueprint created ✓
- **Wheel Candidate fix:** Not started — deferred again

---

## Pending for Next Session (2026-07-18)

### 1. Check Massive.com/pricing → Options tab (2 min — carried over 2 days)
- ≤ $29/mo → upgrade, run POC, integrate into TradeAdvisor
- $79+/mo → drop Massive, go Tradier path

### 2. Tradier path (if Massive too expensive)
Add `TRADIER_SANDBOX=true` env var support to `market_data/tradier.py` to flip base URL
to `https://sandbox.tradier.com/v1`. Set key on Render, hit `/csp/NVDA` to verify.

### 3. Verify `/report/CSCO` on Render
Confirm EPS fields show `$1.06 actual / $1.04 estimate / +2.29%` (lxml in requirements.txt).
Confirm all four cards render correctly.

### 4. Wheel Candidate verdict fix
In report route, change `is_wheel_candidate` logic:
```python
# current
bool(csp_opps) and confidence >= 50
# proposed
bool(csp_opps) and (confidence >= 50 or (top_csp.score >= 8 and signals.get("above_200_dma")))
```

### 5. Agentic build — Phase 1 (when ready to start)
Formalize tool contracts: clean up `fetch_snapshot`, `fetch_options_chain`, `score_csp`
into explicit input/output schemas. First step toward the TAredesign.md blueprint.

---

## Commits This Session (2026-07-17)
- None — research, brainstorming, and design session only. `TAredesign.md` created (untracked).

---

## Session: 2026-07-16

### 1. `/report/CSCO` Render Verification — DEFERRED

Carried over from 2026-07-15 but not verified today — session pivoted to the Polygon/Massive POC.
Still pending: confirm EPS fields populate (lxml installed), all four cards render correctly.

---

### 2. Wheel Candidate Verdict Logic — DEFERRED

Also carried over. Not started today.

Current logic: `bool(csp_opps) and confidence >= 50` — too conservative.
Proposed: `bool(csp_opps) and (confidence >= 50 or (top_csp.score >= 8 and signals.get("above_200_dma")))`
File: wherever `is_wheel_candidate` is set in `app.py` or the report route.

---

### 3. Polygon/Massive POC — BUILT, Data Access Blocked on Free Tier

Built a standalone Flask POC at `polygon_poc/` (subdirectory of TradeAdvisor repo).
Single-file app: fetches `/v3/snapshot/options/{symbol}` and renders a table with
strike, expiry, DTE, bid, ask, mid, delta, IV, OI. Handles pagination, null greeks warning.

**Two fixes made during the session:**
- f-string backslash syntax error (Python 3.11 — removed redundant conditional, `_fmt` handles None)
- Form submitted to `/` instead of `/chain/<symbol>` — added redirect in index route

**Findings:**
- `api.polygon.io` is dead — TLS handshake timeout (domain moved post-rebrand)
- `api.massive.com` is the correct base URL — key authenticates fine
- Free tier error: *"You are not entitled to this data. Please upgrade your plan at https://massive.com/pricing"*
- `/v3/snapshot/options` (greeks + live quotes) requires a paid options plan

**Decision pending:** Check massive.com/pricing → Options tab to see tier prices.
- If ≤ ~$29/mo → upgrade, POC immediately works, integrate into TradeAdvisor
- If $79+/mo → skip Massive, pivot to Tradier (code already in repo, needs URL fix only)

**POC is ready to run:** `polygon_poc/app.py` + `requirements.txt` + `runtime.txt` committed.
Render deploy: new web service from same repo, Root Directory = `polygon_poc`, add `POLYGON_API_KEY`.
`POLYGON_BASE_URL` env var overrides the default `api.massive.com` if needed.

---

## Current State (end of 2026-07-16)

- **App:** Live on Render ✓ · commit `bc776c1` (unchanged today)
- **Report page:** `/report/<symbol>` live — not re-verified today (lxml install unconfirmed)
- **polygon_poc/:** Built and working mechanically — blocked on free tier for options data
- **Wheel Candidate fix:** Not started — deferred to tomorrow

---

## Pending for Next Session (2026-07-17)

### 1. Check Massive options pricing (first thing — 2 minutes)
Go to https://massive.com/pricing → click **Options** tab.
- ≤ $29/mo → upgrade, run POC, verify greeks populate, then integrate into TradeAdvisor
- $79+/mo → go Tradier path instead

### 2. Tradier path (if Massive too expensive)
`market_data/tradier.py` hardcodes `_BASE = "https://api.tradier.com/v1"`.
Add `TRADIER_SANDBOX=true` env var support to flip base URL to `https://sandbox.tradier.com/v1`.
Then set key on Render and hit `/csp/NVDA` to confirm live data returns.

### 3. Verify `/report/CSCO` on Render
Confirm EPS fields populate (should show `$1.06 actual / $1.04 estimate / +2.29%`).
Confirm all four cards render correctly.

### 4. Wheel Candidate verdict fix (quick code change)
`bool(csp_opps) and (confidence >= 50 or (top_csp.score >= 8 and signals.get("above_200_dma")))`
Find `is_wheel_candidate` in the report route and apply the fix. Test on CSCO.

---

## Commits This Session (2026-07-16)
- None — polygon_poc built locally, not yet committed

---

## Session: 2026-07-15

### 1. Vision Assessment — Full Ticker Report

Assessed the app against a vision of a unified per-ticker report (price, trend, business, earnings, options, recommendation). Gap analysis:

| Section | Status before today |
|---|---|
| Current Price | Done |
| Trend: DMA positioning | Done |
| Trend: RSI | Done |
| Options: CSP strike, yield | Done |
| Recommendation: confidence % | Done |
| Trend: volatility direction | Partial — computed but not stored or shown |
| Options: P(Assignment) | Partial — delta existed, just needed relabeling |
| Wheel Candidate verdict | Partial — action + score existed but never joined |
| The report page itself | Missing — data scattered across dashboard, CSP page, admin |
| Business: revenue segments | Missing — needs premium data source |
| Latest Earnings: beat/miss | Missing — yfinance has it, just not wired up |
| Risks: qualitative bullets | Missing — needs LLM + news source |

---

### 2. `/report/<symbol>` Page — BUILT (commit `bc776c1`)

New unified report page at `/report/<symbol>` with four cards:

**Trend card:** vs 200 DMA and 50 DMA (with dollar values), RSI with label, 30-day realized vol with Low/Moderate/High label and declining/stable/rising direction, 52-week range.

**Latest Earnings card** (new data via `fetch_fundamentals()`): EPS actual vs estimate, EPS surprise %, revenue growth YoY, gross margin, operating margin.

**Options — Top CSP card:** Strike, expiry, DTE, bid, annualized yield, distance, P(Assignment) = `|delta| × 100`, IV Rank, score badge. Links to full CSP and CC scan pages.

**Recommendation card:** BUY/HOLD/SELL signal, confidence %, Wheel Candidate verdict (green/red badge), reason bullets from StrategyEngine.

**Dashboard change:** "Report" column added between View and CSP. Loading spinner extended to report links.

---

### 3. `fetch_fundamentals()` Added to `market_data/provider.py`

Fetches from yfinance `.info` and `.earnings_dates`: sector, industry, gross/operating margins, revenue growth, earnings growth, trailing/forward EPS, and most recent quarter EPS estimate/actual/surprise. Cached in DB at `fundamentals:{symbol}` with 4-hour TTL.

**lxml dependency:** `ticker.earnings_dates` uses `pandas.read_html()` internally which requires `lxml`. Was missing → EPS silently returned None for all three fields. Added `lxml` to `requirements.txt`. Verified: AAPL shows $2.01 actual / $1.94 estimate / +3.46% surprise.

---

### 4. Realized Vol + Vol Direction Added to Snapshot

`fetch_snapshot` now stores `realized_vol` (30-day annualized) and `vol_direction` ("declining"/"stable"/"rising" — comparing last 30 days vs prior 30 days with 10% threshold) in the snapshot cache. Were computed before but discarded.

---

### 5. CSCO Report — Sample Output (matches original vision ticker)

- Price $111.77 · Above 200 DMA ($86.13) · Below 50 DMA ($114.90) · RSI 40 Neutral · Vol 43.4% High stable
- EPS: $1.06 actual / $1.04 estimate → +2.29% beat · Revenue +12.0% YoY · Gross margin 64.3% · Operating margin 25.0%
- Top CSP: Strike $108 · 8 DTE · $1.18 bid · **52.38% annualized** · P(Assignment) 26% · IV Rank **100** · Score **10 STRONG**
- Verdict: HOLD / 25% confidence / Not a Wheel Candidate

**Open issue:** Wheel Candidate verdict is too conservative. CSCO has IV Rank 100 + STRONG 10-point CSP + solid earnings but scores "Not a Wheel Candidate" because StrategyEngine confidence is 25% (penalized for being below 50 DMA). Verdict should factor in CSP score + above-200-DMA status. Deferred.

---

## Current State (end of 2026-07-15)

- **App:** Live on Render ✓ · deployed commit `bc776c1`
- **Report page:** `/report/<symbol>` live — price, trend, earnings, options, wheel verdict ✓
- **lxml:** added to requirements.txt — installs on Render on next deploy ✓
- **PostgreSQL / IV / digest:** unchanged and working ✓

---

## Pending for Next Session (2026-07-16)

### 1. Verify Render deploy
Check `/report/CSCO` on live Render. Confirm EPS fields populate (lxml now in requirements.txt). Confirm all four cards render correctly.

### 2. Improve Wheel Candidate verdict logic
Current: `bool(csp_opps) and confidence >= 50`. Too conservative — rejects CSCO (IV Rank 100, STRONG 10 score) because StrategyEngine confidence is 25%.
Proposed: `is_wheel_candidate = bool(csp_opps) and (confidence >= 50 or (top_csp.score >= 8 and signals.get("above_200_dma")))`. Above 200 DMA + STRONG CSP score should be sufficient.

### 3. Remaining vision gaps (medium-term)
- **Business segment breakdown** — yfinance doesn't have it. SEC EDGAR XBRL API is a free option.
- **Risks: qualitative bullets** — needs Claude API call summarizing recent news/SEC language. The "AI-powered" differentiator piece.

---

## Commits This Session (2026-07-15)
- `bc776c1` — Add /report/<symbol> — unified ticker analysis report page

---

## Session: 2026-07-13

### 1. Tradier Rate Limits Verified (from docs)

Before building, confirmed production limits from the live Tradier docs:
- Market data (`/markets/*`): **120 req/min** per API key, rolling window
- No daily limits
- Response headers: `X-Ratelimit-Used`, `X-Ratelimit-Available`, `X-Ratelimit-Expiry`
- `get_chain` is **per expiration** (one call per expiry, not per symbol) — `get_expirations` returns all dates in one call

**Usage math:** 8 symbols × (1 expiry call cached + 2 chain calls) = ~24 calls/hourly scan = 0.3% of budget. Not a concern.

---

### 2. Tradier Integration — BUILT (commit `1631f29`)

**`market_data/tradier.py`** (new file)
- `TradierOptionsProvider` with `get_expirations(symbol)` and `get_chain(symbol, expiry)`
- `get_chain` requests `greeks=true` and maps Tradier field names to yfinance column names (`lastPrice` ← `last`, `openInterest` ← `open_interest`, `impliedVolatility` ← `greeks.mid_iv`)
- Returns `SimpleNamespace` with `.puts` / `.calls` DataFrames — same shape as yfinance so `OptionsEngine` needs no changes in the contract loop

**`options_engine.py`** changes:
- `_make_options_provider()` — reads `TRADIER_API_KEY` env var at init; returns provider or `None`
- `OptionsEngine.__init__` — stores `self._provider`
- `_get_expirations(symbol)` — removed `ticker` param; dispatches to provider or yfinance
- `_get_cached_option_chain(symbol, expiry)` — same pattern
- `time.sleep(2)` / `time.sleep(1)` throttles are skipped when provider is set (they were yfinance-only workarounds)
- yfinance stays for `ticker.history()` (price/indicators) and `ticker.calendar` (earnings)

**72/72 tests pass unchanged** — no `TRADIER_API_KEY` in test env → `self._provider = None` → yfinance/mock path runs as before.

---

### 3. Tradier Sandbox vs Production — Decision Pending

Discovered during account signup that the **production API key requires a full brokerage account** (SSN, DOB, etc.) — it's a FINRA-regulated broker-dealer, same as Schwab. That's more commitment than expected.

**Two options being considered:**
- **Tradier sandbox** — sign up at `https://web.tradier.com/user/api` with just email/password; get sandbox token on that page; 60 req/min, delayed/simulated data. Base URL: `https://sandbox.tradier.com/v1` (different from production `https://api.tradier.com/v1`). Our current code hardcodes production URL — needs a `sandbox` flag or `TRADIER_SANDBOX=true` env var before using sandbox key.
- **Polygon.io free tier** — email-only signup, no brokerage account needed, 15-min delayed options data (same delay as yfinance anyway), already in roadmap.md as the `~$30/mo` option but free tier exists.

**Code change needed before using sandbox key:** `market_data/tradier.py` currently hardcodes `_BASE = "https://api.tradier.com/v1"`. Need to add sandbox support (either a constructor param or read `TRADIER_SANDBOX` env var) before setting the key on Render.

**Left unresolved — decision deferred to 2026-07-14.**

---

## Current State (end of 2026-07-13)

- **App:** Live ✓
- **PostgreSQL:** Live ✓ · 3 digest subscribers ✓ · 8 watchlist symbols ✓
- **IV readings:** All 8 symbols at 70–93+ readings ✓ · IV Rank scoring active ✓
- **Tests:** 72 passing ✓
- **Tradier integration:** Code complete and committed — NOT yet activated (no `TRADIER_API_KEY` set on Render)
- **Per-symbol scans:** Still on yfinance / may still be rate-limited — unverified today

---

## Pending for Next Session (first thing 2026-07-14)

### 1. Decide: Tradier sandbox or Polygon.io free tier?
- **Tradier sandbox:** Get key at `https://web.tradier.com/user/api` (email only). Then add `TRADIER_SANDBOX` env var support to `market_data/tradier.py` before setting key on Render.
- **Polygon.io:** Different provider implementation needed — same pluggable interface, different API.

### 2. Fix sandbox URL before activating (if going Tradier sandbox)
`market_data/tradier.py` needs to switch base URL to `https://sandbox.tradier.com/v1` when sandbox key is in use. Add `TRADIER_SANDBOX=true` env var support (read in `_make_options_provider`, pass `sandbox=True` to constructor).

### 3. Set key on Render and verify
Once URL is correct: set `TRADIER_API_KEY` (and `TRADIER_SANDBOX=true` if sandbox) in Render environment, redeploy, hit `/csp/NVDA` and confirm results come back.

### 4. Carry-over verifications (from earlier sessions)
- `/csp/NVDA` and `/cc/NVDA` — confirm rate limit has cleared (or confirm Tradier is working)
- `/admin/iv-status` — confirm all 8 symbols still at 70–93+ readings

---

## Commits This Session (2026-07-13)
- `1631f29` — Add Tradier options provider — replaces yfinance for options fetches on Render

---

## Session: 2026-07-12

### 1. Admin Dashboard — IV Rank Accumulation Card Clarified

Two questions answered about the IV Rank Accumulation card on `/admin`:

**What "readings" means:** Each reading is one `record_iv()` call — one volatility data point written to `iv_history`. Two sources produce them:
- Background scanner (hourly) — `options_engine.py` calls `record_iv(symbol, realized_vol)` once per symbol per scan cycle
- Dashboard snapshot (every 15 min) — `provider.py` calls `record_iv(symbol, realized_vol)` on each `fetch_snapshot` triggered by a dashboard load

**What the ✓ checkmark means:** Symbol has ≥ 5 readings (the `_IV_RANK_MIN_SAMPLES` threshold). Below 5 it shows `3/5` style. At or above 5, IV Rank is actively computed and the +1/+2 scoring bonus can apply. Defined in `templates/admin.html:80–83`.

**Where the +1/+2 IV Rank bonus is visible:** It is NOT a separate column — it's baked silently into the Score number. The only directly verifiable thing in the UI is that the IV Rank column shows a number (not `—`). If it does, the scoring bonus is being applied.

---

### 2. roadmap.md Created

Created `roadmap.md` in the project root with the full production/monetization roadmap discussed in a prior session. Three tiers:
- **Tier 1 — Foundation:** Reliable data source, proper auth, mobile-responsive UI
- **Tier 2 — Sticky features:** Trade journal, alerts, PoP/max loss, backtesting summary
- **Tier 3 — Monetization:** Freemium gating, broker integration (referral revenue), weekly digest

Key insight documented: Reliable data + trade journal turns this from a screener into a workflow tool — the jump from "nice demo" to "I pay for this."

---

### 3. Tradier Integration — Researched & Decided (not yet built)

**Agreed approach:**
- Keep yfinance for stock price history (works fine, no rate limiting issues there)
- Integrate Tradier for option chains (the part that gets blocked on Render)
- Make the options provider pluggable behind a 2-method interface:
  ```python
  def get_expirations(symbol: str) -> list[str]: ...
  def get_chain(symbol: str, expiry: str) -> tuple[pd.DataFrame, pd.DataFrame]: ...
  ```
  `YFinanceOptionsProvider` and `TradierOptionsProvider` both implement it. `options_engine.py` only ever sees the interface. Makes tests cleaner — mock the interface, not yfinance internals.

**Why yfinance rate limits but Tradier won't:**
Yahoo Finance has no official API — yfinance reverse-engineers web endpoints and Yahoo actively blocks data center IP ranges (AWS/Render). It's not request volume, it's IP-based blocking. Tradier is an official REST API with key-based auth — Render's IP is irrelevant.

**Tradier rate limits confirmed (from docs):**
- Production: **120 requests/minute** per API key
- Sandbox: 60 requests/minute
- Response headers: `X-Ratelimit-Used`, `X-Ratelimit-Available`, `X-Ratelimit-Expiry` — full visibility
- Rolling 1-minute window (not fixed clock intervals)

**Usage math:** 8 symbols × ~3 requests per hourly scan = ~24 requests/hour total. That's 0.3% of the allowed rate. Not a concern even with many concurrent users.

**Tradier account note:** Real-time options data requires a **brokerage account** (free to open, no funding needed) — not just the developer portal API key. The developer sandbox gives delayed/simulated data.

Source: https://docs.tradier.com/docs/rate-limiting

---

## Current State (end of 2026-07-12)

- **App:** Live ✓
- **PostgreSQL:** Live ✓ · 3 digest subscribers ✓ · 8 watchlist symbols ✓
- **IV readings:** All 8 symbols at 70–93+ readings ✓ · IV Rank scoring active ✓
- **Tests:** 72 passing ✓
- **Per-symbol scans:** Still unverified — rate limit may or may not have cleared overnight
- **roadmap.md:** Created in project root ✓
- **Tradier research:** Complete — ready to build next session

---

## Pending for Next Session (first thing 2026-07-13)

### 1. Verify rate limit has cleared (carry-over from 2026-07-12)
Hit `/csp/NVDA` and `/cc/NVDA`. Should return results. If still blocked, check Render logs for `"Too Many Requests"` during last background scan. Diagnostic: `/admin/chain-raw?symbol=NVDA&side=calls`.

### 2. Verify IV Rank scoring in production (carry-over)
Once per-symbol scans work: IV Rank column should show a number (not `—`) on `/csp/TSLA` or `/csp/NVDA`. That's the only direct confirmation — the +1/+2 bonus is baked into the Score total.

### 3. Check `/admin/iv-status` (carry-over)
All 8 symbols should still be at 70–93+ readings.

### 4. Build Tradier integration
- Open a free Tradier brokerage account if not already done (needed for real-time data API key)
- Implement pluggable options provider interface (2 methods: `get_expirations`, `get_chain`)
- `YFinanceOptionsProvider` wraps existing calls
- `TradierOptionsProvider` calls `https://api.tradier.com/v1/markets/options/chains`
- Wire into `options_engine.py` via dependency injection or config flag

---

## Commits This Session (2026-07-12)
- None — research and planning session only

---

## Session: 2026-07-11

### 1. Yahoo Finance Rate Limiting Diagnosed

Per-symbol scans (`/csp/NVDA`, `/csp/TSLA`, etc.) were returning the misleading message "No qualifying contracts found within the scan window." Root cause diagnosed via the new `/admin/chain-raw` route.

**What was happening:**
- `_get_expirations` succeeded (expiration cache hit — no live call needed)
- Every subsequent `ticker.option_chain(expiry)` was rate limited by Yahoo Finance, returning `None`
- All expirations skipped → `opportunities` and `fallback_opps` both empty → fell through to `"no_strikes"`
- `chain-raw` confirmed: `ticker.options` returned `"Too Many Requests. Rate limited. Try after a while."` — NVDA price fetch (5d history) succeeded at $210.96

**Rate limiting is Render IP-specific.** Per-symbol on-demand scans hit Yahoo Finance immediately; background scanner spaces calls over the hour and is less affected.

---

### 2. Rate-Limit Detection Added (commits `e7269bc`, `d243cf2`)

**commit `e7269bc` — `/admin/chain-raw` route**
New diagnostic endpoint: fetches raw option chain (bypasses all filters) for the nearest expiration. Shows price, expirations list, columns, and raw bid/ask/lastPrice per contract. Use when seeing `no_strikes` to determine if it's a data or rate-limit issue.
URL: `/admin/chain-raw?symbol=NVDA&side=calls`

**commit `d243cf2` — `rate_limited` reason code**
`_find_opportunities` now tracks `chains_fetched`. If expirations exist but every chain fetch returns `None` (rate limited), returns `"rate_limited"` instead of `"no_strikes"`.
User now sees: *"Yahoo Finance is rate-limiting options data from this server — try again in a few minutes, or check Top CSP / Top CC for cached results."*
`"no_strikes"` is now reserved for the genuine case: chain fetched successfully but all contracts filtered out.

---

## Current State (end of 2026-07-11)

- **App:** Live ✓
- **PostgreSQL:** Live ✓ · 3 digest subscribers ✓ · 8 watchlist symbols ✓
- **IV readings:** All 8 symbols at 70–93+ readings ✓ · IV Rank scoring active ✓
- **Tests:** 72 passing ✓
- **Per-symbol scans:** Rate limited by Yahoo Finance on Render IP — shows correct error message now
- **Top CSP / Top CC:** Background scanner caches results hourly — should still have data

---

## Pending for Next Session (first thing 2026-07-12)

### 1. Verify rate limit has cleared
Hit `/csp/NVDA` and `/cc/NVDA`. Should return results (not the rate-limited message). If still blocked, check Render logs for `"Too Many Requests"` during the last background scan cycle.

### 2. Verify IV Rank scoring in production
Once per-symbol scans work again:
- Check `/csp/TSLA` or `/csp/NVDA` — IV Rank column should show a number
- Score should reflect +1/+2 bonus for IV Rank ≥ 50/70
- Check `/top-csp` and `/top-cc` — high-IV symbols should rank higher

### 3. Check `/admin/iv-status`
Confirm all 8 symbols still at 70–93+ readings after deploy.

### 4. URL alias (optional)
Custom domain or leave as-is.

---

## Commits This Session (2026-07-11)
- `e7269bc` — Add /admin/chain-raw — dump raw option chain before filters for rate-limit diagnosis
- `d243cf2` — Detect rate limiting — return rate_limited reason instead of no_strikes when all chain fetches fail

---

## Session: 2026-07-10

### 1. IV Rank Scoring Integration — DONE (commit `2a82f5c`)

`iv_history` had 70–93 readings per symbol (~2 weeks of data), making IV Rank meaningful enough to affect scoring.

**Changes to `options_engine.py`:**
- `get_iv_rank(symbol)` moved to before the contract loop so `iv_rank` is available during per-contract scoring
- Removed the duplicate `get_iv_rank` call that was previously after the loop
- `_score_csp` and `_score_cc` both gain an `iv_rank=None` parameter:
  - `+1` if IV Rank ≥ 50
  - `+1` more if IV Rank ≥ 70 (total +2 at ≥70)
- Scoring call updated to pass `iv_rank`

**Tests:** 4 new tests added (`test_score_csp_iv_rank_adds_one_at_50`, `test_score_csp_iv_rank_adds_two_at_70`, `test_score_cc_iv_rank_adds_one_at_50`, `test_score_cc_iv_rank_adds_two_at_70`). **72 total, all passing.**

**Note:** `iv_rank` used for scoring is fetched before the new reading is recorded for the session — it reflects prior accumulated data, not the current scan's reading. Difference is negligible (one reading).

---

## Current State After This Session (end of 2026-07-10)

- **App:** Live and share-ready ✓
- **Render URL:** https://tradeadvisor-hpfq.onrender.com (slug unchanged by design)
- **PostgreSQL:** Live ✓ · **3 digest subscribers** ✓ · **8 watchlist symbols** ✓
- **IV readings:** All 8 symbols at 70–93 readings (~2 weeks of data accumulated) ✓
- **IV Rank scoring:** Active — high IV environments now rank CSP/CC opportunities higher ✓
- **Tests:** 72 passing ✓

---

## Pending for Next Session

### URL alias (optional)
Custom domain or leave as-is.

---

## Commits This Session (2026-07-10)
- `2a82f5c` — Wire IV Rank into CSP/CC scoring — +1 at rank ≥50, +2 at rank ≥70

---

## Session: 2026-07-09

### 1. Render URL Suffix — Explained (no code change)

User noticed the Render URL has `-hpfq` appended despite the service being named "TradeAdvisor". Explained that Render's **service display name** and **URL slug** are separate — the slug is assigned at service creation time and cannot be changed on an existing service.

Options to get a cleaner URL:
- **Custom domain** (~$10/yr via Namecheap + Render custom domains) — cleanest path
- **Delete and recreate the service** — choose slug `tradeadvisor` on creation, but requires re-adding all env vars and reconnecting PostgreSQL
- **Bit.ly short link** — instant, free

Decision: leave as-is for now.

---

### 2. Admin Grid Card Overflow — FIXED (commit `fe83dfe`)

**Problem:** On wide screens, `repeat(auto-fill, minmax(300px, 1fr))` was creating 3+ columns, making the Scan Caches card too narrow. The CSP/CC opp counts and ages (`12 opps`, `77m old`, etc.) were overflowing outside the card's right border and appearing to float between the two cards.

**Fix:** Changed `.admin-grid` in `static/style.css` to `repeat(2, 1fr)` — exactly 2 equal columns always. Digest card already spans `1 / -1` so it remains full width.

**File:** `static/style.css` line 385

---

## Current State After This Session (end of 2026-07-09)

- **App:** Live and share-ready ✓
- **Render URL:** https://tradeadvisor-hpfq.onrender.com (slug unchanged by design)
- **PostgreSQL:** Live ✓ · **3 digest subscribers** ✓ · **8 watchlist symbols** ✓
- **IV readings:** All 8 symbols at 70–93 readings (~2 weeks of data accumulated) ✓
- **Admin dashboard:** Card overflow fixed, clean 2-column layout ✓

---

## Pending for Next Session

### P4 — IV Rank scoring integration (ready now)
`iv_history` has 70–93 readings per symbol (~2 weeks). Ready to wire in:
- `+1` if IV Rank ≥ 50, `+2` if IV Rank ≥ 70 in `_score_csp` / `_score_cc` in `options_engine.py`

### URL alias (optional)
Custom domain or leave as-is.

---

## Commits This Session (2026-07-09)
- `fe83dfe` — Fix admin grid card overflow — lock to 2 columns instead of auto-fill

---

## Session: 2026-07-07

### 1. Digest Card — Full Width on Admin Dashboard (commit `ea9bffa`)

Added `grid-column: 1 / -1` to the Digest card so it spans the full row width.
Previously the Digest and CC Debug cards were side-by-side (~300px each), clipping subscriber emails.

**After:** Scan Caches | IV Rank · Digest (full width) · CC Debug (own row)

---

### 2. Dashboard Nav Link on Per-Symbol CSP/CC Pages (commit `2b1c6af`)

Added explicit **Dashboard** link to nav bar on `csp_results.html` and `cc_results.html`.
Top CSP and Top CC already had it — only the per-symbol pages were missing it.

---

### 3. Delta Fallback for CSP/CC Scans (commits `2b1c6af`, `73ccfbb`)

**Problem:** When no contracts were found in the 0.25–0.30 delta range (e.g. SPY with low VIX),
the scan returned "No contracts found" instead of showing the nearest available options.

**Fix (two iterations):**
- First pass: added 0.20–0.35 secondary range — still missed SPY in some conditions
- Final fix: made fallback a true catch-all — if primary range (0.25–0.30) is empty,
  show ANY contract that passed the OTM window + liquidity filters, regardless of delta.
  A note appears: "No contracts found in 0.25–0.30 delta range — showing nearest available. Check the Delta column."

**Also fixed:** `no_strikes` scan message no longer hardcodes "0.25–0.30" — now says options data
may be unavailable or illiquid (since that's the only remaining case where nothing shows).

**Files:** `options_engine.py`, `app.py`, `csp_results.html`, `cc_results.html`

---

### 4. sellToFriends.md Created (gitignored)

Created `sellToFriends.md` with competitive landscape, feature talking points, pitch language,
objection handling, and honest caveats for sharing with friends.
Added to `.gitignore` along with `response.md` (commit `c74a782`).

---

### 5. App Declared Ready to Share with Friends

All core features working. Discussed URL alias options:
- **Option A (free):** Rename Render service to `tradeadvisor` → `tradeadvisor.onrender.com`
- **Option B (~$10/yr):** Custom domain (e.g. `tradeadvisor.app`) via Namecheap + Render custom domains
- **Option C (instant):** bit.ly short link

---

## Current State After This Session (end of 2026-07-07)

- **App:** Ready to share with friends ✓
- **Render URL:** https://tradeadvisor-hpfq.onrender.com
- **PostgreSQL:** Live ✓ · **3 digest subscribers** ✓ · **8 watchlist symbols** ✓
- **IV readings:** All 8 symbols at 5+ readings, IV Rank displaying ✓
- **Admin dashboard:** Full-width Digest card, CC Debug on its own row ✓
- **Delta fallback:** CSP/CC now always return results if options data exists ✓
- **Nav:** Dashboard link on all pages ✓

---

## Pending for Next Session

### URL alias (optional, before wider sharing)
Rename Render service to `tradeadvisor` for cleaner URL, or buy a custom domain.

### P4 — IV Rank scoring integration (~2026-07-18)
Once `iv_history` has 2 weeks of data, add `+1` if IV Rank ≥ 50, `+2` if IV Rank ≥ 70
to `_score_csp` / `_score_cc` in `options_engine.py`. Currently display-only.

---

## Commits This Session (2026-07-07)
- `ea9bffa` — Expand Digest card to full width so subscriber emails aren't clipped
- `2b1c6af` — Add Dashboard nav link to CSP/CC pages; widen delta range as fallback
- `73ccfbb` — Make delta fallback a true catch-all — show any OTM contract if target range is empty
- `c74a782` — Add sellToFriends.md and response.md to .gitignore

---

## Session: 2026-07-06

### 1. PostgreSQL Was Never Connected — Root Cause of All Data Loss

**Problem:** Render's `DATABASE_URL` env var was set to `sqlite:///tradeadvisor.db` (manually, at some point during initial setup). The app's `load_dotenv()` picked up this value, so the live Render app was writing to ephemeral SQLite on disk — not PostgreSQL. Every redeploy wiped all data. This explained why subscribers, watchlist symbols, and IV readings kept disappearing.

**Fix:**
- Created a new Render PostgreSQL service (`tradeadvisor-db`)
- Set `DATABASE_URL` on the **tradeadvisor** web service to the Internal Database URL from that PostgreSQL service
- Admin page now shows green **PostgreSQL** badge confirming the correct backend

**Commits:** `78821bf` — DB backend indicator on admin dashboard (PostgreSQL vs SQLite)

---

### 2. Admin "Add Subscriber" Form — DONE (commit `0d974a4`)

**Problem:** Adding digest recipients required logging into the Render app with each email address, which silently wrote to the local SQLite instead of Render PostgreSQL when done from localhost.

**Fix:** Added `/admin/add-subscriber` POST route + email input form directly on the `/admin` Digest card. Admin can now add any email address as a digest subscriber without requiring a login flow.

---

### 3. DB Backend Indicator on Admin Dashboard — DONE (commit `78821bf`)

Added green **PostgreSQL** / red **SQLite — LOCAL** badge next to the "Admin Dashboard" heading. Prevents silently writing to the wrong database when running locally vs on Render.

---

### 4. Login Page Tagline — DONE (commit `47e5ef7`)

Changed subtitle from "Sign in to manage your tickers" to "Options scanner for cash-secured puts & covered calls on your watchlist" — gives first-time visitors context before signing up.

---

### 5. DATABASE_URL Removed from Local .env

`DATABASE_URL=sqlite:///tradeadvisor.db` was committed to the repo in `.env`. Removed the value and replaced with a comment explaining the correct behavior: app falls back to SQLite automatically when unset locally; Render sets it via the environment dashboard.

---

## Current State After This Session (end of day 2026-07-06)

- **PostgreSQL:** Live and connected on Render ✓
- **3 digest subscribers:** tradeadvisor2025@gmail.com, sramaswami2021@gmail.com, sramaswami2025@gmail.com ✓
- **Digest verified:** All 3 inboxes received the email ✓
- **8 watchlist symbols:** AAPL, MSFT, NVDA, SPY, GOOGL, AMZN, META, TSLA ✓
- **IV readings:** NVDA/SPY/AAPL/MSFT/TSLA all at 5+ ✓ · GOOGL/AMZN/META at 4 (one more cycle needed)
- **Scan cache:** 9 CSP opps, 9 CC opps ✓
- **Admin dashboard:** PostgreSQL badge, clean card layout, no clipping ✓
- **App:** Ready to share with friends — best to share Monday after market open

---

## Pending for Next Session (Monday 2026-07-07)

### Share with friends
App is ready. Share link after market open (~9:45 AM ET) once scan cache refreshes with live Monday data. Per-symbol scans return "no expirations" on weekends — Top CSP/CC pages use cache so those work anytime.

### P4 — IV Rank scoring integration (~2026-07-18)
Once `iv_history` has 2 weeks of data, add `+1` if IV Rank ≥ 50, `+2` if IV Rank ≥ 70 to `_score_csp` / `_score_cc` in `options_engine.py`.

---

## Commits This Session (2026-07-06)
- `0d974a4` — Add admin form to add digest subscribers directly from /admin
- `47e5ef7` — Update login page tagline to describe the app
- `78821bf` — Show DB backend (PostgreSQL vs SQLite) on admin dashboard

---

## Session: 2026-07-05

### 1. Admin Dashboard — Verified Working

Tested the consolidated `/admin` page live on Render. Card grid loads correctly (Scan Caches, IV Rank Accumulation, Digest, CC Debug). Action buttons redirect back to `/admin?msg=...` with confirmation messages — no bare text returns. No issues found.

---

### 2. IV Scanner — Confirmed Active, Watchlist Gap Found

Checked `/admin/iv-status` during this session:

```
Symbol   Readings   First (h ago)  Last (m ago)
--------------------------------------------------
NVDA            1             0.0           0.4
MSFT            1             0.0           0.4

Total symbols: 2  |  Min readings needed for IV Rank: 5
```

**Findings:**
- Scanner IS recording realized vol (commit `764f8a1` confirmed working)
- Only NVDA and MSFT in `user_tickers` at time of check — AAPL was also present on dashboard but hadn't yet produced a reading
- Readings were brand-new (0.4 min old) — scanner had just completed its first cycle of the session

**Fix applied (manual):** Added `SPY`, `GOOGL`, `AMZN`, `META`, `TSLA` to watchlist via dashboard UI. These will be picked up on the next hourly scanner cycle.

---

## Pending for Next Session (Monday 2026-07-07)

### Verify digest sends to 3 users (highest priority)
Markets reopen Monday. After scan cache warms (~10–15 min of trading), hit **Send Digest** from `/admin`. Confirm Render logs show `"Digest sent to 3 user(s)"` and email arrives at all three addresses: `tradeadvisor2025@gmail.com`, `sramaswami2021@gmail.com`, `sramaswami2025@gmail.com`.

### Verify IV readings reach 5+ per symbol
Check IV Rank card on `/admin` after a few hours of trading. Watchlist now has 8 symbols (AAPL, MSFT, NVDA, SPY, GOOGL, AMZN, META, TSLA). All 8 should appear in `/admin/iv-status`. Once any symbol hits 5 readings, IV Rank displays on its CSP/CC page.

### P4 — IV Rank scoring integration
Deferred until ~2026-07-18 (needs 2 weeks of `iv_history` data). Once ready: +1 if rank ≥ 50, +2 if rank ≥ 70 to CSP/CC score.

---

## Commits This Session (2026-07-05)
- None — verification session only

---

## Session: 2026-07-04

### 1. IV Readings — Background Scanner Now Records Passively (commit `764f8a1`)

**Problem:** `record_iv` was only called from `fetch_snapshot` in `provider.py`, which fires on dashboard loads. UptimeRobot pings unauthenticated → login redirect → no snapshot fetch → IV readings only accumulated when a real user visited the dashboard. After hours of uptime, symbols still had 0–1 readings.

**Fix:** Added `calculate_realized_vol` call in `_find_opportunities` in `options_engine.py`, right after `_build_indicator_data_from_hist` and before `del hist`. The 1-year price history is already in memory at that point — computing realized vol is free. Every background scanner cycle (top_csp + top_cc, hourly, all watchlist symbols) now writes an `iv_history` row regardless of dashboard visits.

**Import added:** `calculate_realized_vol` imported from `market_data.provider` in `options_engine.py`.

**Tests:** All 68 passing.

**Expected result:** Check `/admin/iv-status` in ~5 hours — should show 5+ readings per symbol, at which point IV Rank displays on CSP/CC pages.

---

### 2. Digest Recipients Registered — DONE (manual)

Signed into the Render app with `sramaswami2021@gmail.com` and `sramaswami2025@gmail.com`. Both are now in the `users` table with `digest_opt_in = TRUE`. Future weekday 9:35 AM digests will go to all 3 registered users.

**Pending verification:** `/admin/send-digest` returned "Both caches are empty — background scan just started" during this session. Re-test after scan warms up (~10–15 min after deploy) to confirm digest sends to 3 recipients and all 3 receive it.

---

## Pending for Next Session

### Verify digest sends to 3 users
After scan cache warms up, hit `/admin/send-digest` and check Render logs for `"Digest sent to 3 user(s)"`. Confirm email arrives at all three addresses.

### Verify IV readings reach 5+ per symbol
Check `/admin/iv-status` after a few hours. Once 5 readings exist per symbol, IV Rank will display on CSP/CC pages.

### P4 — IV Rank scoring integration
Once `iv_history` has 2+ weeks of data, plug IV Rank into CSP/CC scoring: +1 if rank ≥ 50, +2 if rank ≥ 70. Currently display-only.

---

### 3. Watchlist Reordering — DONE (commit `dc1c62a`)

**Feature:** ▲ ▼ arrows on each dashboard row let users reorder their watchlist. First row ▲ and last row ▼ are shown greyed out (disabled).

**Schema change:** Added `sort_order INTEGER DEFAULT 0` to `user_tickers`. Migration runs on startup: `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (PostgreSQL) / try-except (SQLite), then `UPDATE user_tickers SET sort_order = id WHERE sort_order = 0` to seed existing rows.

**Files changed:**
- `database.py` — `sort_order` in CREATE TABLE; migration; `get_tickers_for_user` now `ORDER BY sort_order, id`; `add_ticker_to_user` sets `sort_order = MAX(sort_order)+1` per user; new `move_ticker(user_id, symbol, direction)` swaps sort_order with adjacent row
- `app.py` — imported `move_ticker as db_move_ticker`; added `/ticker/move/<symbol>/<direction>` GET route
- `templates/dashboard.html` — ▲ ▼ per row using `loop.first`/`loop.last`; combined with ✖ in last cell
- `static/style.css` — `.move-btn`, `.move-btn.disabled`, `.row-controls` styles

**All 68 tests passing.**

---

### 4. Admin Dashboard — DONE (commit `9a35596`)

**Feature:** Consolidated `/admin` page replaces navigating to 5 separate bare-text URLs. Shows live status in a card grid and action buttons that redirect back with confirmation messages.

**Cards:**
- **Scan Caches** — CSP and CC cache count + age (or "empty"), with Clear Cache button
- **IV Rank Accumulation** — per-symbol reading count, ✓ when ≥ 5, with Raw IV Status link
- **Digest** — email enabled status, subscriber count + addresses, Send Digest + Test Email buttons
- **CC Debug** — symbol input form → opens `/admin/cc-debug` in new tab; links to CC Cache Raw and Upload Users

**Action route changes:** `admin_clear_cache`, `admin_send_digest`, `admin_test_email` now redirect to `/admin?msg=...` instead of returning bare text. `/admin/cc-debug` and `/admin/iv-status` unchanged (diagnostic data, not actions).

**Admin nav link** added to dashboard header — visible only to the admin user (`ADMIN_EMAIL` env var match).

**Files changed:** `app.py`, `templates/admin.html` (new), `templates/dashboard.html`, `static/style.css`

**All 68 tests passing.**

---

## Pending for Next Session

### Verify digest sends to 3 users
Markets reopen Monday. Once scan caches warm up (options data available on trading days), hit **Send Digest** from `/admin` and confirm "Digest sent to 3 user(s)" in Render logs. All 3 addresses should receive it.

### Verify IV readings reach 5+ per symbol
Check IV Rank card on `/admin` after a few hours of trading. Background scanner now records realized vol on every hourly cycle. Once 5 readings per symbol, IV Rank displays on CSP/CC pages.

### P4 — IV Rank scoring integration
Once `iv_history` has 2+ weeks of data, plug IV Rank into CSP/CC scoring: +1 if rank ≥ 50, +2 if rank ≥ 70. Currently display-only.

---

## Commits This Session (2026-07-04)
- `764f8a1` — Record realized vol in background scanner to accumulate IV readings passively
- `dc1c62a` — Add watchlist reordering with up/down buttons
- `9a35596` — Add consolidated admin dashboard at /admin

---

## Session: 2026-07-02

### 1. Digest Subscription — Committed & Pushed — DONE (commit `a31194e`)

The 2026-07-01 session work (digest opt-in toggle) had never been committed. Ran 64 tests (all passing), committed, and pushed. Deployed to Render.

---

### 2. `/admin/iv-status` Diagnostic Route — DONE (commit `e9784da`)

Added route that queries `iv_history` reading counts per symbol and returns a plain-text table showing readings, first/last timestamps. Carried over from three prior sessions. Confirmed on Render: **`iv_history` table is completely empty.**

---

### 3. IV History Empty — Root Cause Diagnosed & Fixed (commit `d337105`)

**Root cause:** `record_iv` in `options_engine.py` only fires when `atm_iv` is set, which requires at least one contract with `impliedVolatility > 0`. Yahoo Finance returns `impliedVolatility = 0` on Render's data center IPs under rate limiting. So options scans run and produce bid/ask results, but IV is always 0 → `atm_iv` stays `None` → `record_iv` never called → `iv_history` stays empty forever.

**Fix:** Added `calculate_realized_vol()` to `market_data/provider.py`. Computes 30-day annualized realized volatility from the 1-year price history already fetched by `fetch_snapshot`. Calls `record_iv(symbol, vol)` on every fresh snapshot fetch (every 15 min per symbol, triggered by dashboard loads). Works entirely independently of options data or rate limiting.

**Scale:** Realized vol is in decimal form (e.g., 0.254 = 25.4%) — same scale as yfinance `impliedVolatility`, so IV Rank formula is compatible.

**Tests:** 4 new tests in `test_provider.py` — 68 total, all passing.

---

### 4. `/admin/test-email` Route — DONE (commit `d2698f5`)

Added admin route that sends a hardcoded sample digest (2 CSP + 2 CC rows) to the logged-in admin's email. Bypasses scan cache entirely — useful for verifying Mailjet delivery when `top_csp/cc_cache` are empty (e.g. fresh Render instance). Subject prefixed `[TEST]` to distinguish from real sends.

---

### 5. UptimeRobot Keep-Alive — SET UP

Configured free UptimeRobot monitor pinging `https://tradeadvisor-hpfq.onrender.com` every 5 minutes. Prevents Render free-tier spin-downs. Ensures background scanner runs continuously and dashboard snapshot fetches fire regularly to accumulate IV readings.

---

## Pending for Next Session

### Verify IV readings are accumulating
Check `/admin/iv-status` — should show 5+ readings per symbol after a few hours of UptimeRobot pings. Once 5 readings exist per symbol, IV Rank will display on CSP/CC pages.

### Register additional digest recipients
Sign into Render app with `sramaswami2021@gmail.com` and `sramaswami2025@gmail.com` to register them as users. They'll receive the digest automatically once registered.

### P4 — IV Rank scoring integration
Once iv_history has 2+ weeks of data, plug IV Rank into CSP/CC scoring: +1 if rank ≥ 50, +2 if rank ≥ 70. Currently display-only.

---

## Commits This Session (2026-07-02)
- `a31194e` — Add digest subscription/unsubscription toggle for users
- `e9784da` — Add /admin/iv-status diagnostic route for IV Rank accumulation
- `d2698f5` — Add /admin/test-email route to verify Mailjet delivery independently of scan cache
- `d337105` — Record realized vol from price history to seed iv_history reliably

---

## Session: 2026-07-01

### 1. Digest Subscription / Unsubscription — DONE

**Feature:** Users can now subscribe or unsubscribe from the daily digest email directly from the dashboard.

**Schema change:** Added `digest_opt_in BOOLEAN DEFAULT TRUE` to the `users` table. Existing rows auto-migrated on first request after deploy via `ALTER TABLE ... ADD COLUMN IF NOT EXISTS` (PostgreSQL) / try-except (SQLite). All existing users default to subscribed.

**Files changed:**
- `database.py` — added `digest_opt_in` to both `CREATE TABLE` variants + migration; updated `get_user_by_id` and `get_user_by_email` to return `digest_opt_in`; added `get_digest_users()` (filters `digest_opt_in = TRUE`) and `set_digest_opt_in(user_id, bool)`
- `digest.py` — switched from `get_all_users()` to `get_digest_users()` so unsubscribed users are excluded from sends
- `app.py` — imported `set_digest_opt_in`; added `/settings/digest` POST route that toggles preference and redirects to dashboard; passes `digest_opt_in` to dashboard template
- `templates/dashboard.html` — "Daily digest email (9:35 AM ET on weekdays): **On** [Unsubscribe]" / "**Off** [Subscribe]" toggle bar below watchlist table (hidden for guests)
- `static/style.css` — added `.digest-bar`, `.digest-status`, `.digest-btn-on/off` styles

**All 64 tests still passing.**

---

### 2. Email Delivery — CLARIFIED (no code issue)

**Mailjet sender addresses ≠ registered users.** Mailjet "sender addresses" (`sramaswami2021@gmail.com`, `sramaswami2025@gmail.com`, `tradeadvisor2025@gmail.com`) are addresses Mailjet allows as FROM — they are not digest recipients.

**Digest recipients** = rows in the `users` table with `digest_opt_in = TRUE`. The only registered user is `tradeadvisor2025@gmail.com`, which is why only that address received the digest.

**Self-send concern was wrong:** `tradeadvisor2025@gmail.com` (FROM = TO) DID receive the email. Gmail is not dropping it. Mailjet delivery is working correctly.

**To add other recipients:** Simply sign in to the Render app once with each email address (`sramaswami2021@gmail.com`, `sramaswami2025@gmail.com`). They'll be created as users with `digest_opt_in = TRUE` and will receive future digests automatically.

---

## Pending for Next Session

### Register additional users for digest
Sign in to Render app with `sramaswami2021@gmail.com` and/or `sramaswami2025@gmail.com` to add them as registered users. They'll receive the digest automatically once registered.

### IV Rank Diagnostic (`/admin/iv-status`) — still pending
IV Rank still shows `—` on all symbols. Add route to query `iv_history` reading counts:
```sql
SELECT symbol, COUNT(*), MIN(recorded_at), MAX(recorded_at) FROM iv_history GROUP BY symbol;
```

---

## Commits This Session (2026-07-01)
- pending push — digest subscription/unsubscription feature

---

## Session: 2026-06-30

### 1. yfinance Upgraded 0.2.66 → 1.5.1 (commits `ffc0d67`)

**Root cause:** Yahoo Finance changed their authentication API (cookie + crumb system). yfinance 0.2.x gets an empty response body from every call, causing `"Expecting value: line 1 column 1 (char 0)"` on all symbols — not rate limiting, not Render-specific, a global auth failure.

**Fix:** Upgraded to yfinance 1.5.1 (latest). curl_cffi also bumped 0.14.0 → 0.15.0. `requirements.txt` pinned to `yfinance==1.5.1`.

**Code compatibility:** `_get_next_earnings()` in `options_engine.py` already handled `Earnings Date` as a list (line 313: `isinstance(earnings, (list, tuple))`). No other code changes needed.

**Added startup version log** to `app.py` so we can confirm which version Render is actually running:
```
INFO:app:yfinance version: 1.5.1
```

**Render note:** curl_cffi 0.15.0 compiled successfully on Render — no issues.

**Gotcha:** User was running Flask via system Python (yfinance 0.2.28) instead of `.venv`. Always run via `.venv\Scripts\python -m flask run` or activate `.venv` first.

---

### 2. Snapshot Cache Persisted to PostgreSQL (commit `dcdeff9`)

**Problem:** Render wipes `/tmp` on every cold start. Dashboard triggers yfinance fetches for all 7+ symbols simultaneously → Yahoo Finance 429 rate limit → all fetches fail.

**Fix:** `market_data/provider.py` now writes snapshots to the existing `cache` table in PostgreSQL (key: `snapshot:{symbol}`) in addition to the `/tmp` file. On load: tries file first (fast path), falls back to DB (survives restarts).

**Behavior:** First cold start after deploy still hits Yahoo Finance (DB empty), but populates DB. Every subsequent cold start reads from DB instantly — no burst, no 429.

**Staleness:** 15-minute TTL is enforced on DB reads the same as file reads. The `ignore_ttl=True` fallback (used when live fetch fails) can serve stale data, but that's intentional degradation — better than showing `—` everywhere.

---

### 3. Mailjet Email Digest — Wired Up on Render

**Env vars added to Render:**
- `ENABLE_EMAIL=true`
- `MAILJET_API_KEY` / `MAILJET_API_SECRET` (from Mailjet dashboard)
- `EMAIL_FROM=tradeadvisor2025@gmail.com` (verified sender in Mailjet)
- `ADMIN_EMAIL=tradeadvisor2025@gmail.com`

**`/admin/send-digest` fixes (commit `a138c46`):**
- Was: silently skipped if caches empty, returned generic "triggered" message regardless
- Now: calls `get_top_csp_opportunities()` / `get_top_cc_opportunities()` first (which kick off background scanner threads if not running). Returns HTTP 202 with clear message if caches empty: *"Both caches are empty — background scan just started. Wait 10-15 minutes..."*

**`_do_send()` in `digest.py`:** Now uses `get_top_csp/cc_opportunities()` instead of raw `_load_opps()` — consistent with admin route and ensures threads are always running.

**Status:** Mailjet confirmed `Status: success` and assigned a MessageID. Logs show `"Digest sent to 1 user(s) — 5 CSP, 5 CC opportunities"`. However, email not received at `tradeadvisor2025@gmail.com`.

**Likely cause:** FROM and TO are the same address (`tradeadvisor2025@gmail.com`). Gmail may silently drop self-sent emails from third-party senders. Need to test with a different recipient.

---

## Pending for Next Session

### Investigate Email Not Received
- Check Mailjet dashboard → Transactional → Message Statistics for MessageID `288230414370833970` — look for "delivered", "soft bounce", or "blocked"
- Test with a different recipient email (a user registered with a different address)
- If confirmed Gmail self-send issue: register a second user with a different email and test delivery to that address

### IV Rank Diagnostic (`/admin/iv-status`)
IV Rank still shows `—` on all symbols. Add route to query `iv_history` reading counts:
```sql
SELECT symbol, COUNT(*), MIN(recorded_at), MAX(recorded_at) FROM iv_history GROUP BY symbol;
```

---

## Commits This Session (2026-06-30)
- `ffc0d67` — Upgrade yfinance 0.2.66 → 1.5.1; add startup version log
- `dcdeff9` — Persist snapshot cache to PostgreSQL to survive Render restarts
- `a138c46` — Fix digest skipping when caches empty after cold start

---

## Session: 2026-06-29

### 1. Top-CC Stuck on "Scan in Progress" — FIXED (commit `b920351`)

**Root cause:** CC OTM filter capped at 10% above price. For high-IV stocks (NVDA, META), the 0.25-delta call strike sits 11–15% OTM on 14–30 DTE options. Every CC strike was filtered before the delta check ran, so results were always `[]`, cache was never written, page stayed stuck.

**Fix:** Raised CC OTM ceiling from 10% → 20% in `options_engine.py` line ~223. The delta filter (0.25–0.30) is still the real constraint.

Also updated `/admin/clear-cache` to flush `top_cc_cache` alongside `top_csp_cache`.

---

### 2. CC Scan Diagnostics Added (commit `60d3fa3`)

Added three tools for ongoing visibility:
- **`top_cc.py` logging**: `_scan_symbol` now logs reason code and opp count per symbol to Render logs
- **`/admin/cc-status`**: instant DB read showing what's in `top_cc_cache` (count, age, raw JSON)
- **`/admin/cc-debug?symbol=AAPL`**: synchronous single-symbol CC scan (~30s), returns strike/delta/bid/ann%/score or reason code

---

### 3. Yahoo Finance Blocking Render for Options Data — DIAGNOSED

**Symptom:** Both CSP and CC scans returning `no_expirations` for all symbols on Render. Works fine locally.

**Root cause:** Yahoo Finance rate-limits or blocks data center IPs (Render's AWS infrastructure) for their options endpoint (`ticker.options`). History endpoint (`ticker.history()`) uses a different Yahoo Finance API path that is less aggressively gated. Three rapid redeploys today likely triggered the block by causing burst yfinance calls on startup.

**Fix applied:** Extended `EXPIRATION_CACHE_SECONDS` from 24h → 7 days (`options_engine.py`). Expiration dates are set by the exchange months in advance; DTE is always computed fresh from `datetime.today()`. Once the rate limit clears and the cache is seeded, it survives a full week of deploys without re-fetching.

**Expected recovery:** Rate limit should clear overnight. On next successful `ticker.options` call, PostgreSQL `expiration_cache` is populated with 7-day TTL. No manual action needed — background scanner auto-populates on next hourly cycle.

---

### 4. Daily Market-Open Email Digest — DONE (commit `4629c5a`, **NOT YET PUSHED**)

**Behaviour:** At 9:35 AM ET on weekdays, reads `top_csp_cache` and `top_cc_cache` from PostgreSQL, builds an HTML email with top 5 CSP and top 5 CC opportunities (inline styles, score badges, links to per-symbol scan pages), sends to every registered user via Mailjet. Skips if both caches are empty.

**Scheduling mechanism:** `@app.before_request` hook in `app.py` — checks time on every non-static request. In-process `_fired_date` flag + DB `last_digest_date` cache key prevent double-sends even across Render restarts.

**Files changed:**
- `digest.py` — new file; all scheduling, HTML building, send logic
- `database.py` — added `get_all_users()` (returns all registered email addresses)
- `app.py` — `before_request` hook; `/admin/send-digest` test route (bypasses time check)

**Admin test route:** `/admin/send-digest` triggers an immediate send for testing without waiting for 9:35 AM.

**Render env vars required (not yet set):**
| Var | Value |
|---|---|
| `ENABLE_EMAIL` | `true` |
| `MAILJET_API_KEY` | from Mailjet dashboard |
| `MAILJET_API_SECRET` | from Mailjet dashboard |
| `EMAIL_FROM` | verified sender in Mailjet (e.g. `tradeadvisor2025@gmail.com`) |
| `ADMIN_EMAIL` | `tradeadvisor2025@gmail.com` (already set — admin access control only) |

**Note:** `email_utils.py` was an existing file from the original app using Mailjet (not SendGrid as previously discussed). Reused as-is.

---

## Pending for Next Session

### Push Commits
Run `git push` — commits `b920351`, `60d3fa3`, `743b6ca`, `4629c5a` are local only.

### Set Mailjet Env Vars on Render
Add `ENABLE_EMAIL`, `MAILJET_API_KEY`, `MAILJET_API_SECRET`, `EMAIL_FROM` to Render environment. Verify `tradeadvisor2025@gmail.com` as a sender in Mailjet first.

### Test Email Digest
After deploy + env vars set, hit `/admin/send-digest` and confirm email arrives in inbox. Check Render logs for `"Digest sent to N user(s)"`.

### Confirm Yahoo Finance Rate Limit Cleared
Check `/csp/SPY` and `/top-csp` tomorrow morning. If still returning `no_expirations`, the block may be persistent rather than temporary — would need to investigate alternatives (proxy, different yfinance version, or Render paid tier with static IP).

### IV Rank Diagnostic Route (carried over)
Add `/admin/iv-status` to query `iv_history` reading counts per symbol.

---

## Commits This Session (2026-06-29)
- `b920351` — Fix top-cc stuck on 'Scan in progress' — widen CC OTM window to 20%
- `60d3fa3` — Add CC scan diagnostics: per-symbol logging + /admin/cc-status + /admin/cc-debug
- `743b6ca` — Extend expiration cache TTL from 24h to 7 days
- `4629c5a` — Add daily market-open email digest to all registered users

---

## Session: 2026-06-28

### 1. CSP Fixes Committed & Deployed — DONE

The two `options_engine.py` fixes from 2026-06-27 were sitting uncommitted. Committed and pushed as part of `6d3fbc7` today.
- **DTE fallback widening** (`options_engine.py:142–145`): tries max_dte → 30 → 45 until valid expirations found
- **200 DMA gate softened** (`options_engine.py:115`): requires below BOTH 50 and 200 DMA to block (not just 200)

Render deployed and `/csp/SPY` confirmed returning results.

---

### 2. Structured Scan Reason Codes — DONE (commit `6d3fbc7`)

`_find_opportunities` was returning bare `[]` at every failure point with no explanation. Changed to return `(list, reason_str)` at every exit.

**Reason codes:**
| Code | Trigger |
|---|---|
| `no_history` | yfinance couldn't fetch 1-year price history |
| `no_indicators` | `<200` trading days in history |
| `below_dma` | stock below both 50-day and 200-day MA |
| `no_expirations` | no option expirations within 45-day window |
| `no_strikes` | contracts exist but none passed delta/OTM/liquidity filters |
| `scan_error` | outer exception (rate limit, network, etc.) |
| `ok` | results found |

**Callers updated:**
- `app.py`: unpacks tuple, maps reason → human-readable `scan_message`, passes to template. `_SCAN_REASON_MESSAGES` dict in `app.py`.
- `top_csp.py` / `top_cc.py`: `opps, _ = ...` (background scanner discards reason)
- `templates/csp_results.html` + `cc_results.html`: empty-state now shows `{{ symbol }} — {{ scan_message }}`
- `tests/test_options_engine.py`: both integration tests updated to unpack tuple and assert reason code (`"ok"` and `"below_dma"`)

This also resolved item **D — Better Empty Scan Message** from the backlog: `"no_strikes"` maps to "No contracts found in the 0.25–0.30 delta range within the scan window."

---

### 3. Column Hover Tooltips — DONE (commit `a00f951`)

Added `title` attributes to every non-obvious `<th>` across all 5 templates:
- **Options pages** (`csp_results.html`, `cc_results.html`, `top_csp.html`, `top_cc.html`): DTE, Bid, Ask, Ann%, Distance%, Delta, OI, IV Rank, Earnings, Score
- **Dashboard** (`dashboard.html`): Change, 50 DMA, 200 DMA, RSI, Rating, Confidence, CSP, CC
- Delta tooltip wording differs: "put delta" for CSP, "call delta" for CC. Distance% wording differs: "below price" for CSP, "above price / before shares get called away" for CC.
- `static/style.css`: added `th[title] { cursor: help; text-decoration: underline dotted #aaa; }` so users know headers are hoverable.

---

### 4. NVDA Typo — CONFIRMED FIXED

User confirmed NVDIA → NVDA is correct on live Render. No code change needed.

---

### 5. IV Rank Not Showing — DIAGNOSED (not fixed)

**Symptom:** IV Rank shows `—` on all symbols on Render.

**Root cause:** Render free tier spins the instance down after ~15 min of no traffic. Each spin-down kills the background scanner thread. When traffic restarts the instance, the thread restarts too — but the missed hours are lost. Instead of ~96 hourly readings over 4 days, the actual count may be well below the 5-reading minimum required by `get_iv_rank()`.

**Next step:** Query the `iv_history` table on Render PostgreSQL to see actual reading counts:
```sql
SELECT symbol, COUNT(*) as readings, MIN(recorded_at), MAX(recorded_at)
FROM iv_history
GROUP BY symbol
ORDER BY readings DESC;
```

**Proposed fix:** Add `/admin/iv-status` route that runs this query and renders the result in the browser — easier than digging into the Render PostgreSQL console every time.

---

## Pending for Next Session

### IV Rank Diagnostic Route
Add `/admin/iv-status` route to query `iv_history` reading counts per symbol. Confirm whether the background scanner is accumulating readings on Render's free tier. If counts are consistently low, may need a different accumulation strategy (e.g. record IV on every per-symbol user scan, not just background scanner).

### Future Enhancement: Daily Market-Open Alert (Email Digest)
Discussed but not started. Plan:
- At 9:35 AM ET on weekdays, pull top-scored CSP/CC from existing cache
- Format as HTML email (top 3–5 opportunities per side)
- Send via **SendGrid** free tier (100 emails/day) to user's email
- Each opportunity links directly to `/csp/<symbol>` or `/cc/<symbol>`
- Estimated effort: ~half a session
- Alternative: SMS via Twilio (more intrusive, adds paid dependency)
- Skip PWA push notifications — too complex for a personal tool

---

## Commits This Session (2026-06-28)
- `6d3fbc7` — Add structured scan reason codes to replace silent empty returns
- `a00f951` — Add hover tooltips to all table column headers

---

## Session: 2026-06-27

### 1. CSP Scan Returning Empty Results on Render — DIAGNOSED & FIXED

**Symptom:** `/csp/SPY` returned 200 with only 944 bytes — empty results page. No errors in logs because the route swallows all exceptions silently (`except Exception: opportunities = []`).

**Three silent gates identified (all return `[]` with no explanation):**
1. **200 DMA filter** (`options_engine.py:115`) — hard blocks if stock below 200-day MA
2. **DTE window** (`options_engine.py:141`) — only scanned 5–14 DTE; on a weekend with few upcoming expirations this can be empty
3. **Delta filter** — if yfinance returns IV=0 or NaN, no strikes land in 0.25–0.30 delta band

**Fix 1 — DTE fallback widening** (`options_engine.py`):
- Was: only scan expirations with `5 <= DTE <= 14`, give up if none
- Now: try 14 DTE first; if no valid expirations found, widen to 30, then 45
- History fetch and 200 DMA check still run only once — the widening only retries the cheap expiration-list filter step

**Fix 2 — Soften 200 DMA gate** (`options_engine.py`):
- Was: `if not above_200_dma: return []` — blocked entirely if below 200-day MA
- Now: `if not above_200_dma and not above_50_dma: return []` — only blocks if below both DMAs
- Rationale: below 200 but above 50 = recovering; score already docks points for it. Below both = genuine downtrend, worth blocking.

**Not yet committed — deploy tomorrow.**

---

## Pending for Next Session

### Verify CSP fixes on Render
Deploy the two `options_engine.py` changes and confirm `/csp/SPY` returns results.
- DTE fallback: `options_engine.py` lines ~135–145
- 200 DMA softened: `options_engine.py` line ~115

### C — Column Tooltips / Legend (optional)
Friends unfamiliar with options won't know what Delta, IV Rank, or "8 STRONG" mean.
Options: hover tooltips on `<th>` headers, or a small legend paragraph below the table.
Skip if all friends are options-literate.

### D — Better Empty Scan Message (optional)
Currently: "No suitable CSP opportunities found for AAPL."
Better: "No contracts found in the 0.25–0.30 delta range expiring within 14 days."

---

## Commits This Session (2026-06-27)
- None — changes staged locally, not yet committed

---

## Session: 2026-06-26

### 1. Data Disclaimer on Results Pages — DONE

**Why:** Yahoo options data is ~15 min delayed during market hours. Per-symbol scans fetch live from Yahoo (~15 min lag). Top CSP/CC background scan runs hourly, so worst case ~75 min stale. Disclaimer sets right expectation and makes the app feel more credible to friends.

**Fix:** Reused existing `.freshness-note` CSS class (12px, gray). Added a `<p class="freshness-note">` below each results table:
- `csp_results.html` / `cc_results.html`: "Data via Yahoo Finance · ~15 min delayed · verify with your broker before trading"
- `top_csp.html` / `top_cc.html`: "Data via Yahoo Finance · up to ~75 min delayed (hourly scan + Yahoo delay) · verify with your broker before trading"

**Commits:** `0b3505b`

---

### 2. Favicon — DONE

**Why:** All browser tabs showed a blank icon.

**Implementation:**
- Started with `static/favicon.svg` (blue trend-line SVG), but SVG favicons aren't reliably picked up by all browsers/tabs.
- Switched to `static/favicon.png` — 32×32 blue square (#4a6cf7), generated via Python stdlib (`struct` + `zlib`, no PIL needed).
- Added `<link rel="icon" type="image/png">` to all 6 templates (`login.html`, `dashboard.html`, `csp_results.html`, `cc_results.html`, `top_csp.html`, `top_cc.html`).
- Added `/favicon.ico` Flask route (`app.send_static_file("favicon.png")`) — browsers that probe the root URL for a favicon also find it.

**Commits:** `0b3505b`, `7f7840e`

---

### 3. Guest Session Persisting After Login — FIXED

**Bug:** If a user visited as guest first (`session["guest"] = True`), then signed in with name/email, the dashboard still showed guest mode. Root cause: the `/login` POST handler set `session["user_id"]` without clearing the existing session, so `guest` flag persisted alongside `user_id`. The dashboard check `is_guest = bool(session.get("guest"))` picked up the stale flag.

**Fix (two layers):**
- `app.py` login route: `session.clear()` before `session["user_id"] = user["id"]` — prevents the bleed-through on new logins.
- `app.py` dashboard route: `session.pop("guest", None)` whenever `user_id` is in session — heals stale cookies already out in the wild without requiring a logout.

**Commits:** `0b3505b`, `7f7840e`

---

## Pending for Next Session

### C — Column Tooltips / Legend (optional)
Friends unfamiliar with options won't know what Delta, IV Rank, or "8 STRONG" mean.
Options: hover tooltips on `<th>` headers, or a small legend paragraph below the table.
Skip if all friends are options-literate.

### D — Better Empty Scan Message (optional)
Currently: "No suitable CSP opportunities found for AAPL."
Better: "No contracts found in the 0.25–0.30 delta range expiring within 14 days."

---

## Commits This Session (2026-06-26)
- `0b3505b` — Add favicon, data disclaimers, and fix guest session persisting after login
- `7f7840e` — Fix favicon (PNG), /favicon.ico route, and guest session bleed-through

---

## Session: 2026-06-25

### 1. P5 — UI Polish / Mobile Responsive — DONE

**Changes:**
- Created `static/style.css` — single shared stylesheet for all pages. Replaces per-template inline `<style>` blocks. Covers: sticky header/nav, table styling, score badges, signal colours (positive/negative, RSI, IV Rank, earnings), responsive breakpoints.
- All 6 templates rewritten to use shared CSS:
  - `login.html` — added viewport meta, links `style.css`, uses `.login-body` + `.card`
  - `dashboard.html` — uses `.site-header`, `.container`, `.table-wrap`; heading changed to `{{ user.name }}'s Watchlist`
  - `top_csp.html` / `top_cc.html` — now have a proper header with nav links (previously had none); wrapped in `.container` + `.table-wrap`; score badges
  - `csp_results.html` / `cc_results.html` — same header pattern, score badges, removed standalone back link (brand logo in header links to dashboard)
- Score column changed from plain colored text `"9 STRONG"` to pill badges: `<span class="badge badge-strong">9 STRONG</span>`
- All tables wrapped in `<div class="table-wrap">` — `overflow-x: auto` on mobile
- Sticky header on all data pages
- Dashboard link added to Top CSP and Top CC nav
- `test_app_auth.py` updated: `"Tickers for"` → `"Watchlist"` to match new heading

**Commits:** `5ba5c8f`

---

### 2. Guest Mode — DONE

**Why:** Friends demoing the app shouldn't need to provide an email or type credentials.

**Implementation:**
- `app.py`: Added `MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]` constant. Added `is_authenticated()` helper (`user_id` in session OR `session.guest`). Added `/guest` route — clears session, sets `session["guest"] = True`, redirects to dashboard.
- Dashboard with guest session: shows Mag 7 watchlist, hides add-ticker form and remove (✖) buttons, shows blue guest banner with "Sign in" nudge.
- Top CSP / Top CC: results filtered to Mag 7 symbols when guest, same guest banner shown.
- All 5 data templates: nav shows "Sign in → /login" instead of "Logout" when `session.get('guest')`. Uses Flask's `session` global in Jinja2 — no extra variable needed.
- `login.html`: "Continue as Guest" link below form with "Mag 7 stocks · no sign-in needed" hint.
- Guests have full access to per-symbol `/csp/<symbol>` and `/cc/<symbol>` scan pages.
- `remove_ticker` silently redirects guests back to dashboard (no-op).

**Commits:** `bf84828`, `d7bc77e`, `9cf5e6a`

---

### 3. Loading Spinner for Per-Symbol Scans — DONE

**Why:** Per-symbol CSP/CC scans take 15–45s with no feedback. Friends thought the app was broken.

**Fix:**
- `static/style.css`: Added `.scan-overlay`, `.spinner`, `@keyframes spin`.
- `dashboard.html`: Full-page overlay div (hidden by default). JS listens for clicks on `a[href^="/csp/"]` and `a[href^="/cc/"]`, shows overlay with "Scanning AAPL — CSP…" text. `pageshow` listener removes overlay on browser back-button bfcache restore.

**Commit:** `34ceff9`

---

## Pending for Next Session (2026-06-26)

### A — Data Disclaimer on Results Pages (quick)
Add one line to `csp_results.html` and `cc_results.html`:
`"Data via Yahoo Finance · ~15 min delayed · verify with your broker before trading"`
- Yahoo options data is ~15 min delayed during market hours
- Top CSP/CC background scan runs hourly, so those can be up to ~75 min stale
- Disclaimer sets right expectation; makes app feel more credible

### B — Favicon (quick)
All tabs show blank icon. Simple `.ico` or SVG favicon in `static/`, linked from all templates (or via `<link>` in shared base if we add one).

### C — Column tooltips / legend (optional, depends on audience)
Friends unfamiliar with options won't know what Delta, IV Rank, or "8 STRONG" mean.
Options: hover tooltips on `<th>` headers, or a small legend paragraph below the table.
Skip if all friends are options-literate.

### D — Better empty scan message (optional)
Currently: "No suitable CSP opportunities found for AAPL."
Better: "No contracts found in the 0.25–0.30 delta range expiring within 14 days."

---

## Data Quality Notes (for reference)

- **Bid/ask on per-symbol scans**: fetched live from Yahoo Finance at scan time. Yahoo is ~15 min delayed during market hours. `_option_chain_cache` has 30-min TTL but is cleared after every scan, so each user click fetches fresh from Yahoo.
- **Top CSP/CC**: background scanner runs hourly. Results up to ~60 min old + Yahoo's 15-min delay = ~75 min worst case.
- **IV Rank**: accumulates from hourly scan readings. Shows `—` until 5 readings per symbol. Meaningful after ~1 week. Not suitable for real trading decisions yet.
- **Expiration dates**: cached 24h (they don't change intraday).
- **OTM strikes with low OI**: bid/ask can be stale on Yahoo regardless of app caching. `ask * 0.95` fallback used when bid = 0.
- **ThinkorSwim/Schwab API**: would improve data quality but migration is substantial. Not worth doing until user feedback validates the tool.

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
