import os
import re
from flask import Flask, render_template, request, redirect, url_for, session

# If provider.py is in the same folder as app.py:
from market_data.provider import fetch_snapshot  # uses EODHD and computes DMA/RSI/etc  :contentReference[oaicite:2]{index=2}

app = Flask(__name__)

# Flask Security
# Generate with: python -c "import secrets; print(secrets.token_hex(32))"
#Stored it in env.
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable not set")

IS_DEV = True
DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA"]


def normalize_symbol(symbol: str) -> str:
    """Basic cleanup: letters/numbers/dot/dash only; uppercase."""
    s = (symbol or "").strip().upper()
    s = re.sub(r"[^A-Z0-9\.\-]", "", s)
    return s


def fmt_or_dash(x):
    return "—" if x is None else x


def decide_rating(snapshot: dict):
    """
    Simple explainable rules using price vs DMA50/DMA200 and RSI.
    snapshot keys come from provider.fetch_snapshot(). :contentReference[oaicite:3]{index=3}
    """
    price = snapshot.get("current_price")
    dma50 = snapshot.get("dma_50")
    dma200 = snapshot.get("dma_200")
    rsi = snapshot.get("rsi_14")

    if price is None:
        return "Hold", 50, "No price data available from provider."

    reasons = []
    score = 0

    if dma50 is not None:
        if price >= dma50:
            score += 1
            reasons.append("Price is above the 50 DMA (short-term strength).")
        else:
            score -= 1
            reasons.append("Price is below the 50 DMA (short-term weakness).")
    else:
        reasons.append("50 DMA unavailable (need more history).")

    if dma200 is not None:
        if price >= dma200:
            score += 1
            reasons.append("Price is above the 200 DMA (long-term trend supportive).")
        else:
            score -= 1
            reasons.append("Price is below the 200 DMA (long-term trend weak).")
    else:
        reasons.append("200 DMA unavailable (need more history).")

    if rsi is not None:
        if rsi >= 70:
            score -= 1
            reasons.append(f"RSI is high ({rsi}) → potentially overbought.")
        elif rsi <= 30:
            score += 1
            reasons.append(f"RSI is low ({rsi}) → potentially oversold rebound.")
        else:
            reasons.append(f"RSI is neutral ({rsi}).")
    else:
        reasons.append("RSI unavailable.")

    # Rating & confidence
    if score >= 2:
        rating = "Buy"
        confidence = 80
    elif score == 1:
        rating = "Hold"
        confidence = 65
    else:
        rating = "Sell"
        confidence = 55

    rationale = " ".join(reasons)
    return rating, confidence, rationale


def build_row(symbol: str) -> dict:
    snap = fetch_snapshot(symbol)  # cached via lru_cache in provider :contentReference[oaicite:4]{index=4}

    rating, confidence, rationale = decide_rating(snap)

    return {
        "symbol": symbol,
        "price": fmt_or_dash(snap.get("current_price")),
        "dma50": fmt_or_dash(snap.get("dma_50")),
        "dma200": fmt_or_dash(snap.get("dma_200")),
        "rating": rating,
        "confidence": confidence,
        "rationale": rationale,
    }


def ensure_defaults_loaded():
    session.setdefault("tickers", [])
    existing = {t.get("symbol", "").upper() for t in session["tickers"]}

    for sym in DEFAULT_TICKERS:
        if sym not in existing:
            session["tickers"].append(build_row(sym))
            session.modified = True


def add_symbol(symbol: str):
    session.setdefault("tickers", [])
    symbol = normalize_symbol(symbol)
    if not symbol:
        return

    existing = {t.get("symbol", "").upper() for t in session["tickers"]}
    if symbol.upper() in existing:
        return

    session["tickers"].append(build_row(symbol))
    session.modified = True


@app.route("/")
def index():
    if IS_DEV:
        session["user_email"] = "dev@example.com"
        return redirect(url_for("dashboard"))
    return redirect(url_for("login"))


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_email" not in session:
        return redirect(url_for("login"))

    # keep your old behavior: show default tickers on first load
    ensure_defaults_loaded()

    # Add ticker
    if request.method == "POST":
        add_symbol(request.form.get("symbol", ""))
        return redirect(url_for("dashboard"))

    # View rationale (panel below table)
    selected_rationale = None
    view_symbol = normalize_symbol(request.args.get("view", ""))
    if view_symbol:
        for t in session.get("tickers", []):
            if t.get("symbol", "").upper() == view_symbol.upper():
                selected_rationale = t
                break

    return render_template(
        "dashboard.html",
        tickers=session.get("tickers", []),
        selected_rationale=selected_rationale
    )


@app.route("/login")
def login():
    return "Login disabled in dev mode"


if __name__ == "__main__":
    app.run(debug=True)
