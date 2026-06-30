import os
import re
import json
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, abort
from trade_advisor import get_trade_recommendation
from options_engine import get_shared_engine

import yfinance as yf
import pandas as pd
import logging

load_dotenv()

logging.basicConfig(level=logging.INFO)
_startup_logger = logging.getLogger(__name__)
_startup_logger.info(f"yfinance version: {yf.__version__}")

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
from top_cc import get_top_cc_opportunities
from digest import maybe_send_digest

options_engine = get_shared_engine()

_SCAN_REASON_MESSAGES = {
    "no_history":    "Could not fetch price history from Yahoo Finance — try again in a moment.",
    "no_indicators": "Insufficient price history to calculate indicators (need 200+ trading days).",
    "below_dma":     "Stock is in a downtrend (below both 50-day and 200-day moving averages) — not ideal for selling premium.",
    "no_expirations": "No option expirations found within the scan window (up to 45 days).",
    "no_strikes":    "No contracts found in the 0.25–0.30 delta range within the scan window.",
    "scan_error":    "Scan error — Yahoo Finance may be rate-limiting. Try again in a few minutes.",
}

app = Flask(__name__)

# =========================
# Flask Security
# =========================
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable not set")

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA"]
MAG7 = ["AAPL", "MSFT", "GOOGL", "AMZN", "NVDA", "META", "TSLA"]


@app.before_request
def check_daily_digest():
    if not request.path.startswith("/static/"):
        maybe_send_digest()


# =========================
# Helpers
# =========================

def is_authenticated() -> bool:
    return "user_id" in session or bool(session.get("guest"))


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
        "price": snap.get("current_price"),
        "change_pct": snap.get("change_pct"),
        "rsi": snap.get("rsi_14"),
        "as_of": snap.get("as_of"),
        "dma50": snap.get("dma_50"),
        "dma200": snap.get("dma_200"),
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

@app.route("/favicon.ico")
def favicon():
    return app.send_static_file("favicon.png")


@app.route("/")
def index():
    return redirect(url_for("dashboard")) if is_authenticated() else redirect(url_for("login"))


@app.route("/guest")
def guest():
    session.clear()
    session["guest"] = True
    return redirect(url_for("dashboard"))


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

        session.clear()
        session["user_id"] = user["id"]
        ensure_default_tickers_for_user(user["id"])

        return redirect(url_for("dashboard"))

    return render_template("login.html")


@app.route("/dashboard", methods=["GET", "POST"])
def dashboard():
    if not is_authenticated():
        return redirect(url_for("login"))

    if "user_id" in session:
        session.pop("guest", None)

    is_guest = bool(session.get("guest"))

    if is_guest:
        user = {"id": None, "name": "Guest", "email": None}
        symbols = MAG7
    else:
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
        user=user,
        guest=is_guest,
    )


@app.route("/csp/<symbol>")
def view_csp(symbol):
    if not is_authenticated():
        return redirect(url_for("login"))

    if not session.get("guest"):
        user = get_user_by_id(session["user_id"])
        if not user:
            session.clear()
            return redirect(url_for("login"))

    try:
        opportunities, scan_reason = options_engine.find_csp_opportunities(symbol.upper())
    except Exception:
        opportunities, scan_reason = [], "scan_error"

    scan_message = _SCAN_REASON_MESSAGES.get(scan_reason, "No qualifying opportunities found.")

    return render_template(
        "csp_results.html",
        symbol=symbol.upper(),
        opportunities=opportunities,
        scan_message=scan_message,
    )


@app.route("/remove/<symbol>")
def remove_ticker(symbol):
    if not is_authenticated():
        return redirect(url_for("login"))
    if not session.get("guest"):
        remove_ticker_from_user(session["user_id"], normalize_symbol(symbol))
    return redirect(url_for("dashboard"))


# =========================
# ADMIN UTILITIES
# =========================

@app.route("/admin/clear-cache")
def admin_clear_cache():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])
    if not is_admin(user):
        abort(403)

    from database import set_cache
    import time
    ts = time.time()
    set_cache("top_csp_cache", "[]", ts)
    set_cache("top_cc_cache", "[]", ts)
    return "top_csp_cache and top_cc_cache cleared — background scans will repopulate within a few minutes.", 200


@app.route("/admin/send-digest")
def admin_send_digest():
    """Trigger the daily digest immediately (for testing)."""
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])
    if not is_admin(user):
        abort(403)

    from top_csp import get_top_csp_opportunities
    from top_cc import get_top_cc_opportunities
    from digest import _do_send
    import threading

    csp = get_top_csp_opportunities()
    cc = get_top_cc_opportunities()

    if not csp and not cc:
        return (
            "Both caches are empty — background scan just started. "
            "Wait 10-15 minutes for the scan to finish, then try again."
        ), 202

    threading.Thread(target=_do_send, daemon=True, name="digest-manual").start()
    return "Digest send triggered — check Render logs and your inbox in ~30s.", 200


@app.route("/admin/cc-status")
def admin_cc_status():
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])
    if not is_admin(user):
        abort(403)

    from database import get_cache
    import time, json as _json
    row = get_cache("top_cc_cache")
    if not row:
        return "top_cc_cache: not in DB\n", 200
    age = int(time.time() - row["timestamp"])
    try:
        opps = _json.loads(row["value"])
        return f"top_cc_cache: {len(opps)} opportunities, {age}s old\n\n{row['value'][:1000]}", 200
    except Exception as e:
        return f"top_cc_cache parse error: {e}\nRaw: {row['value'][:500]}", 200


@app.route("/admin/cc-debug")
def admin_cc_debug():
    """Synchronous single-symbol CC scan — slow (~30s) but shows exactly what the scanner sees."""
    if "user_id" not in session:
        return redirect(url_for("login"))
    user = get_user_by_id(session["user_id"])
    if not is_admin(user):
        abort(403)

    symbol = request.args.get("symbol", "AAPL").upper()
    try:
        opps, reason = options_engine.find_cc_opportunities(symbol)
        lines = [f"Symbol: {symbol}", f"Reason: {reason}", f"Count: {len(opps)}", ""]
        for o in opps[:5]:
            lines.append(
                f"  strike={o.get('strike')} expiry={o.get('expiry')} "
                f"dte={o.get('dte')} delta={o.get('delta')} "
                f"bid={o.get('bid')} ann={o.get('annualized')}% score={o.get('score')}"
            )
        return "\n".join(lines), 200, {"Content-Type": "text/plain"}
    except Exception as e:
        return f"Error scanning {symbol}: {e}", 500


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

    if not is_authenticated():
        return redirect(url_for("login"))

    is_guest = bool(session.get("guest"))
    opportunities = get_top_csp_opportunities()
    if is_guest:
        opportunities = [o for o in opportunities if o.get("symbol") in MAG7]

    return render_template(
        "top_csp.html",
        opportunities=opportunities,
        guest=is_guest,
    )


@app.route("/cc/<symbol>")
def view_cc(symbol):
    if not is_authenticated():
        return redirect(url_for("login"))

    if not session.get("guest"):
        user = get_user_by_id(session["user_id"])
        if not user:
            session.clear()
            return redirect(url_for("login"))

    try:
        opportunities, scan_reason = options_engine.find_cc_opportunities(symbol.upper())
    except Exception:
        opportunities, scan_reason = [], "scan_error"

    scan_message = _SCAN_REASON_MESSAGES.get(scan_reason, "No qualifying opportunities found.")

    return render_template(
        "cc_results.html",
        symbol=symbol.upper(),
        opportunities=opportunities,
        scan_message=scan_message,
    )


@app.route("/top-cc")
def top_cc():

    if not is_authenticated():
        return redirect(url_for("login"))

    is_guest = bool(session.get("guest"))
    opportunities = get_top_cc_opportunities()
    if is_guest:
        opportunities = [o for o in opportunities if o.get("symbol") in MAG7]

    return render_template(
        "top_cc.html",
        opportunities=opportunities,
        guest=is_guest,
    )


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))

init_db()

if __name__ == "__main__":
    app.run()