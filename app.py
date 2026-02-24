import os
import re
import json
from dotenv import load_dotenv
from flask import Flask, render_template, request, redirect, url_for, session, abort

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

app = Flask(__name__)

# =========================
# Flask Security
# =========================
app.secret_key = os.getenv("FLASK_SECRET_KEY")
if not app.secret_key:
    raise RuntimeError("FLASK_SECRET_KEY environment variable not set")

DEFAULT_TICKERS = ["AAPL", "MSFT", "NVDA"]
#ADMIN_EMAIL = os.getenv("ADMIN_EMAIL", "").lower()

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


def decide_rating(snapshot: dict):
    price = snapshot.get("current_price")
    dma50 = snapshot.get("dma_50")
    dma200 = snapshot.get("dma_200")
    rsi = snapshot.get("rsi_14")

    if price is None:
        return "Hold", 0, "No price data available."

    score = 0
    reasons = []

    if dma50 is not None:
        score += 1 if price >= dma50 else -1
        reasons.append("Price is above the 50 DMA." if price >= dma50 else "Price is below the 50 DMA.")

    if dma200 is not None:
        score += 2 if price >= dma200 else -2
        reasons.append("Price is above the 200 DMA." if price >= dma200 else "Price is below the 200 DMA.")

    if rsi is not None:
        if rsi <= 30:
            score += 1
            reasons.append(f"RSI is low ({rsi}).")
        elif rsi >= 70:
            score -= 1
            reasons.append(f"RSI is high ({rsi}).")
        else:
            reasons.append(f"RSI is neutral ({rsi}).")

    if score >= 3:
        return "Buy", 85, " ".join(reasons)
    elif score >= 1:
        return "Hold", 65, " ".join(reasons)
    else:
        return "Sell", 55, " ".join(reasons)


def build_row(symbol: str):
    snap = fetch_snapshot(symbol)
    rating, confidence, rationale = decide_rating(snap)
    return {
        "symbol": symbol,
        "price": snap.get("current_price", "—"),
        "dma50": snap.get("dma_50", "—"),
        "dma200": snap.get("dma_200", "—"),
        "rating": rating,
        "confidence": confidence,
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

    print("USER OBJECT:", user)

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


@app.route("/remove/<symbol>")
def remove_ticker(symbol):
    remove_ticker_from_user(session["user_id"], normalize_symbol(symbol))
    return redirect(url_for("dashboard"))


# =========================
# ADMIN UPLOAD — FULL IMPLEMENTATION
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


@app.route("/logout")
def logout():
    session.clear()
    return redirect(url_for("login"))


if __name__ == "__main__":
    init_db()
    app.run()