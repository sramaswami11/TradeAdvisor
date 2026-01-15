from flask import Flask, request, session, redirect, url_for
from flask_limiter import Limiter
from flask_limiter.util import get_remote_address
from flask_wtf.csrf import CSRFProtect, generate_csrf
import os
import secrets
from datetime import timedelta, datetime
import sys

# =========================
# Load .env (local only)
# =========================
try:
    from dotenv import load_dotenv
    load_dotenv(override=False)
    print(">>> .env file loaded (Windows env vars take precedence if set)")
except ImportError:
    print(">>> python-dotenv not installed, using system environment variables")

print(">>> app.py started")

# =========================
# STARTUP SANITY CHECKS
# =========================

REQUIRED_ENV_VARS = [
    "FLASK_SECRET",
    "EMAIL_HOST",
    "EMAIL_PORT",
    "EMAIL_USER",
    "EMAIL_PASSWORD"
]

missing = [k for k in REQUIRED_ENV_VARS if not os.environ.get(k)]

if missing:
    print("❌ Startup configuration error")
    print("Missing environment variables:")
    for k in missing:
        print(f"  - {k}")
    sys.exit(1)

print("✅ Required environment variables present")

# =========================
# Verify market data pipeline
# =========================
try:
    from market_data.provider import fetch_snapshot

    print(">>> Running market data sanity check (AAPL)")
    test = fetch_snapshot("AAPL")

    required_fields = ["current_price", "rsi_14", "dma_50", "dma_200", "volume"]
    missing_fields = [f for f in required_fields if test.get(f) is None]

    if missing_fields:
        raise ValueError(f"Market data missing fields: {missing_fields}")

    print(
        f"✅ Market data OK | "
        f"RSI={test['rsi_14']} "
        f"DMA50={test['dma_50']} "
        f"DMA200={test['dma_200']} "
        f"VOL={test['volume']}"
    )

except Exception as e:
    print("❌ Market data provider failed startup validation")
    print(f"Reason: {e}")
    sys.exit(1)

# =========================
# Imports that rely on config
# =========================

from trade_advisor import (
    get_trade_advisor_data,
    get_trade_recommendation
)

from email_utils import send_email
from database import (
    init_db,
    get_user_by_email,
    save_magic_link,
    verify_magic_link,
    save_recommendation
)
from validators import validate_email, validate_ticker

# =========================
# Flask App Setup
# =========================

app = Flask(__name__)

app.secret_key = os.environ["FLASK_SECRET"]

app.config.update(
    SESSION_COOKIE_SECURE=os.environ.get("RENDER") is not None,
    SESSION_COOKIE_HTTPONLY=True,
    SESSION_COOKIE_SAMESITE="Lax",
    PERMANENT_SESSION_LIFETIME=timedelta(hours=2)
)

csrf = CSRFProtect(app)

limiter = Limiter(
    app=app,
    key_func=get_remote_address,
    default_limits=["200 per day", "50 per hour"],
    storage_uri="memory://"
)

init_db()

# =========================
# Security Headers
# =========================

@app.after_request
def set_security_headers(response):
    response.headers["X-Content-Type-Options"] = "nosniff"
    response.headers["X-Frame-Options"] = "DENY"
    response.headers["X-XSS-Protection"] = "1; mode=block"
    if os.environ.get("RENDER"):
        response.headers["Strict-Transport-Security"] = "max-age=31536000; includeSubDomains"
    return response

# =========================
# UI Helpers
# =========================

COLOR = {
    "BUY": "#c6f6d5",
    "SELL": "#fed7d7",
    "HOLD": "#edf2f7"
}

def confidence_color(conf):
    if conf >= 75:
        return "#38a169"
    if conf >= 50:
        return "#d69e2e"
    return "#e53e3e"

# =========================
# Routes (unchanged below)
# =========================
# (Your existing routes continue exactly as before)
# No behavioral changes beyond safer startup
# =========================

if __name__ == "__main__":
    print(">>> Starting TradeAdvisor server")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("RENDER") is None
    app.run(host="0.0.0.0", port=port, debug=debug)
