import os
import re
import json
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, abort
from trade_advisor import get_trade_recommendation
from options_engine import get_shared_engine

import yfinance as yf
import pandas as pd

print("\n" + "=" * 60)
print("YFINANCE VERSION:", yf.__version__)
print("PANDAS VERSION:", pd.__version__)
print("=" * 60 + "\n")

load_dotenv()

from market_data.provider import fetch_snapshot
from database import (
    init_db,
    create_user,
    get_user_by_email,
    get_user_by_id,
    get_tickers_for_user,
    add_ticker_to_user,
    remove_ticker_from_user,
    update_user_name_if_missing
)

from top_csp import get_top_csp_opportunities

options_engine = get_shared_engine()

app = Flask(__name__)

# =========================
# Flask Security
# =========================
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable not set")

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA"]

# =========================
# Helpers
# =========================

def normalize_symbol(symbol: str) -> str:
    return re.sub(r"[^A-Z0-9\.\-]", "", (symbol or "").upper())


def is_admin(user: dict) -> bool:
    if not user or not user.get("email"):
        return False

    admin_email = os.getenv("ADMIN_EMAIL", "").lower()
    return user["email"].lower() == admin_email


EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def validate_user_import_json(payload: dict):
    errors = []
    preview = []

    if not isinstance(payload, dict):
        return ["Top-level JSON must be an object"], None

    users = payload.get("users")
    if not isinstance(users, list):
        return ["'users' must be a list"], None

    for idx, u in enumerate(users):
        if not isinstance(u, dict):
            errors.append(f"users[{idx}] must be an object")
            continue

        name = u.get("name")
        email = u.get("email")
        tickers = u.get("tickers")

        if not name or not isinstance(name, str):
            errors.append(f"users[{idx}].name is required")

        if not email or not isinstance(email, str) or not EMAIL_RE.match(email):
            errors.append(f"users[{idx}].email is invalid")

        if not isinstance(tickers, list) or not tickers:
            errors.append(f"users[{idx}].tickers must be a non-empty list")

        normalized = []
        for t in tickers or []:
            if not isinstance(t, str):
                errors.append(f"users[{idx}].tickers must be strings")
                continue
            normalized.append(normalize_symbol(t))

        preview.append({
            "name": name,
            "email": email.lower(),
            "tickers": normalized
        })

    return errors, preview


def build_row(symbol: str):
    snap = fetch_snapshot(symbol)
    result = get_trade_recommendation(snap)

    # DEBUG: inspect actual trade engine payload
    print(f"{symbol} TRADE RESULT:", result)

    rationale = ""

    # -------------------------
    # Flexible rationale parser
    # -------------------------

    # Legacy reasons list
    if result.get("reasons"):
        rationale = " ".join(map(str, result["reasons"]))

    # Explanation field (string or list)
    elif result.get("explanation"):
        if isinstance(result["explanation"], list):
            rationale = " ".join(map(str, result["explanation"]))
        else:
            rationale = str(result["explanation"])

    # StrategyEngine rationale field
    elif result.get("rationale"):
        if isinstance(result["rationale"], list):
            rationale = " ".join(map(str, result["rationale"]))
        else:
            rationale = str(result["rationale"])

    # Signals dict fallback
    elif result.get("signals"):
        signals = result["signals"]

        if isinstance(signals, dict):
            signal_parts = []

            for key, value in signals.items():
                signal_parts.append(f"{key}: {value}")

            rationale = " | ".join(signal_parts)

        else:
            rationale = str(signals)

    # Full fallback
    else:
        rationale = "No rationale available."

    return {
        "symbol": symbol,
        "price": snap.get("current_price", "—"),
        "dma50": snap.get("dma_50", "—"),
        "dma200": snap.get("dma_200", "—"),
        "rating": result.get("action", "HOLD").capitalize(),
        "confidence": result.get("confidence", 0),
        "rationale": rationale,
    }


def ensure_default_tickers_for_user(user_id: int):
    if get_tickers_for_user(user_id):
        return
    for sym in DEFAULT_TICKERS:
        add_ticker_to_user(user_id, sym)


# =========================
# Routes
# =========================

@app.route("/")
def index():
    return redirect(url_for("dashboard")) if "user_id" in session else redirect(url_for("login"))


@app.route("/login", methods=["GET", "POST"])
def login():
    if request.method == "POST":
        name = request.form.get("name", "").strip()
        email = request.form.get("email", "").strip().lower()

        if not name or not email:
            return "Name and email required", 400

        create_user(email=email, name=name)
        user = get_user_by_email(email)

        update_user_name_if_missing(user["id"], name)
        user = get_user_by_email(email)

        session["user_id"] = user["id"]
        ensure_default_tickers_for_user(user["id"])

        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])

    if not user:
        session.clear()
        return redirect(url_for("login"))

    if request.method == "POST":
        symbol = normalize_symbol(request.form.get("symbol"))
        if symbol:
            add_ticker_to_user(user["id"], symbol)
        return redirect(url_for("dashboard"))

    symbols = get_tickers_for_user(user["id"])
    tickers = [build_row(sym) for sym in symbols]

    selected_rationale = None
    view = normalize_symbol(request.args.get("view"))
    if view:
        selected_rationale = next((t for t in tickers if t["symbol"] == view), None)

    return render_template(
        "dashboard.html",
        tickers=tickers,
        selected_rationale=selected_rationale,
        user=user
    )


@app.route("/csp/<symbol>")
def view_csp(symbol):
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])

    if not user:
        session.clear()
        return redirect(url_for("login"))

    #engine = OptionsEngine()

    try:
        opportunities = options_engine.find_csp_opportunities(symbol.upper())

        # -------------------------
        # DEBUGGING OUTPUT
        # -------------------------
        print(f"========== CSP DEBUG FOR {symbol.upper()} ==========")
        print("TOTAL OPPORTUNITIES:", len(opportunities))

        for idx, opp in enumerate(opportunities):
            print(f"#{idx+1}: {opp}")

        if not opportunities:
            print("NO CSP OPPORTUNITIES FOUND")
            print("Possible causes:")
            print("- Stock not above 200 DMA")
            print("- No valid option expirations")
            print("- No strikes within 5–15% OTM range")
            print("- Premium too low")
            print("- yfinance option chain empty")

    except Exception as e:
        print("========== CSP ENGINE ERROR ==========")
        print(e)
        opportunities = []

    return render_template(
        "csp_results.html",
        symbol=symbol.upper(),
        opportunities=opportunities,
        user=user
    )


@app.route("/remove/<symbol>")
def remove_ticker(symbol):
    remove_ticker_from_user(session["user_id"], normalize_symbol(symbol))
    return redirect(url_for("dashboard"))


# =========================
# ADMIN UPLOAD
# =========================

@app.route("/admin/upload-users", methods=["GET", "POST"])
def admin_upload_users():
    if "user_id" not in session:
        return redirect(url_for("login"))

    user = get_user_by_id(session["user_id"])

    if not is_admin(user):
        abort(403)

    if request.method == "POST":
        file = request.files.get("file")
        if not file:
            return "No file uploaded", 400

        try:
            payload = json.load(file)
        except Exception as e:
            return f"Invalid JSON: {e}", 400

        errors, preview = validate_user_import_json(payload)

        if errors:
            return {
                "status": "error",
                "errors": errors
            }, 400

        inserted_users = 0
        inserted_tickers = 0

        for u in preview:
            create_user(email=u["email"], name=u["name"])
            db_user = get_user_by_email(u["email"])

            update_user_name_if_missing(db_user["id"], u["name"])

            for sym in u["tickers"]:
                add_ticker_to_user(db_user["id"], sym)
                inserted_tickers += 1

            inserted_users += 1

        return {
            "status": "success",
            "users_processed": inserted_users,
            "tickers_added": inserted_tickers
        }

    return """
    <h2>Admin: Upload Users (JSON)</h2>
    <form method="POST" enctype="multipart/form-data">
        <input type="file" name="file" accept=".json" required>
        <button type="submit">Upload & Import</button>
    </form>
    """

@app.route("/top-csp")
def top_csp():

    if "user_id" not in session:
        return redirect(url_for("login"))


    opportunities = get_top_csp_opportunities()

    for r in opportunities[:5]:
        print(r["symbol"], r["score"])

    print("TOP CSP COUNT:", len(opportunities))

    return render_template(
        "top_csp.html",
        opportunities=opportunities
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

@app.route("/debug-options")
def debug_options():
    if "user_id" not in session:
        return {"error": "unauthorized"}, 401

    import yfinance as yf

    ticker = yf.Ticker("SPY")

    try:
        opts = ticker.options

        print("OPTIONS:", opts)

        return {
            "count": len(opts),
            "options": list(opts[:5])
        }

    except Exception as ex:

        print("OPTION ERROR:", ex)

        return {
            "error": str(ex)
        }

@app.route("/debug-history")
def debug_history():
    if "user_id" not in session:
        return {"error": "unauthorized"}, 401

    import yfinance as yf

    ticker = yf.Ticker("SPY")

    try:

        hist = ticker.history(period="5d")

        return {
            "rows": len(hist)
        }

    except Exception as ex:

        return {
            "error": str(ex)
        }

init_db()

if __name__ == "__main__":
    app.run()