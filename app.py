from flask import Flask, request, session, redirect, url_for, render_template_string
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

app = Flask(__name__)
# =========================
# Security Configuration
# =========================

# Ensure secure secret key
app.secret_key = os.environ.get("FLASK_SECRET")
if not app.secret_key or app.secret_key == "dev-secret":
    if os.environ.get("RENDER") is None:  # Development mode
        print("WARNING: Using insecure dev secret key. Set FLASK_SECRET in production!")
        app.secret_key = "dev-secret-change-me"
    else:
        raise ValueError("FLASK_SECRET must be set to a secure random value in production!")

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
    response.headers['X-Content-Type-Options'] = 'nosniff'
    response.headers['X-Frame-Options'] = 'DENY'
    response.headers['X-XSS-Protection'] = '1; mode=block'
    if os.environ.get("RENDER"):
        response.headers['Strict-Transport-Security'] = 'max-age=31536000; includeSubDomains'
    return response

# =========================
# UI helpers
# =========================

COLOR = {
    "BUY": "#c6f6d5",
    "SELL": "#fed7d7",
    "HOLD": "#edf2f7"
}

def confidence_color(confidence: int) -> str:
    if confidence >= 75:
        return "#38a169"
    elif confidence >= 50:
        return "#d69e2e"
    else:
        return "#e53e3e"

# =========================
# ROOT ROUTE
# =========================

@app.route("/")
def index():
    """Entry point for the app."""
    if "user_email" in session:
        return redirect("/batch-json")
    return redirect("/login")

@app.route("/login", methods=["GET", "POST"])
@limiter.limit("5 per minute")  # Prevent brute force
@csrf.exempt  # Disable CSRF for login route
def login():
    if request.method == "POST":
        email = request.form.get("email", "").strip()
        
        # Validate email
        if not validate_email(email):
            return "Invalid email format", 400

        user = get_user_by_email(email)
        if not user:
            return "Email not found", 404

        # Generate secure token
        token = secrets.token_urlsafe(32)
        
        # Save to database with expiration
        if not save_magic_link(token, email, expires_minutes=15):
            return "Error generating login link", 500

        link = url_for("magic_login", token=token, _external=True)

        try:
            send_email(
                email,
                "Your TradeAdvisor Magic Link",
                f"""
                <html>
                <body>
                    <p>Hello {user['name']},</p>
                    <p>Click below to access your TradeAdvisor dashboard:</p>
                    <p><a href="{link}" style="background:#4299e1;color:white;padding:10px 20px;text-decoration:none;border-radius:5px;display:inline-block;">Login to TradeAdvisor</a></p>
                    <p>This link expires in 15 minutes.</p>
                    <p style="color:#666;font-size:12px;">If you didn't request this, please ignore this email.</p>
                </body>
                </html>
                """
            )
        except Exception as e:
            print(f"Email error: {e}")
            return "Error sending email. Please try again.", 500

        return """
        <html>
        <body style="font-family:Arial,sans-serif;max-width:600px;margin:50px auto;padding:20px;">
            <h2>✓ Magic link sent!</h2>
            <p>Check your email inbox for the login link.</p>
            <p style="color:#666;">The link expires in 15 minutes.</p>
        </body>
        </html>
        """

    return """
    <html>
    <head>
        <title>TradeAdvisor Login</title>
        <style>
            body { font-family: Arial, sans-serif; max-width: 400px; margin: 100px auto; padding: 20px; }
            input { width: 100%; padding: 10px; margin: 10px 0; box-sizing: border-box; }
            button { width: 100%; padding: 12px; background: #4299e1; color: white; border: none; cursor: pointer; font-size: 16px; }
            button:hover { background: #3182ce; }
        </style>
    </head>
    <body>
        <h2>🔐 TradeAdvisor Login</h2>
        <form method="post">
            <input type="email" name="email" placeholder="Enter your email" required />
            <button type="submit">Send Magic Link</button>
        </form>
    </body>
    </html>
    """

@app.route("/magic-login")
@limiter.limit("10 per minute")
def magic_login():
    token = request.args.get("token")
    
    if not token:
        return "Invalid link", 400

    email = verify_magic_link(token)
    if not email:
        return """
        <html>
        <body style="font-family:Arial,sans-serif;max-width:600px;margin:50px auto;padding:20px;">
            <h2>⚠️ Invalid or expired link</h2>
            <p>This login link has expired or been used already.</p>
            <p><a href="/login">Request a new link</a></p>
        </body>
        </html>
        """, 400

    session["user_email"] = email
    session.permanent = True
    return redirect("/batch-json")

@app.route("/logout")
def logout():
    session.clear()
    return redirect("/login")
    
# =========================
# Batch helper (user-aware)
# =========================

def analyze_user_tickers(user):
    results = []

    for ticker in user["tickers"]:
        # Validate ticker
        clean_ticker = validate_ticker(ticker)
        if not clean_ticker:
            results.append({
                "ticker": ticker.upper(),
                "price": None,
                "rsi": None,
                "dma_50": None,
                "dma_200": None,
                "macd": None,
                "macd_signal": None,
                "52w_low": None,
                "52w_high": None,
                "volume_trend": None,
                "action": "ERROR",
                "confidence": 0,
                "reasons": ["Invalid ticker symbol"]
            })
            continue

        try:
            data = get_trade_advisor_data(clean_ticker)
            rec = get_trade_recommendation(data)

            # Save recommendation to database
            if data.get("current_price"):
                save_recommendation(
                    user["id"],
                    clean_ticker,
                    rec["action"],
                    rec["confidence"],
                    data["current_price"]
                )

            results.append({
                "ticker": clean_ticker,
                "price": data.get("current_price"),
                "rsi": data.get("rsi_14"),
                "dma_50": data.get("dma_50"),
                "dma_200": data.get("dma_200"),
                "macd": data.get("macd"),
                "macd_signal": data.get("macd_signal"),
                "52w_low": data.get("52w_low"),
                "52w_high": data.get("52w_high"),
                "volume_trend": data.get("volume"),
                "action": rec["action"],
                "confidence": rec["confidence"],
                "reasons": rec["reasons"]
            })
        except Exception as e:
            print(f"Error analyzing {clean_ticker}: {e}")
            results.append({
                "ticker": clean_ticker,
                "price": None,
                "rsi": None,
                "dma_50": None,
                "dma_200": None,
                "macd": None,
                "macd_signal": None,
                "52w_low": None,
                "52w_high": None,
                "volume_trend": None,
                "action": "ERROR",
                "confidence": 0,
                "reasons": ["Failed to fetch data"]
            })

    return results

# =========================
# Batch route (protected)
# =========================

@app.route("/batch-json")
def batch_json():
    if "user_email" not in session:
        return redirect("/login")

    user = get_user_by_email(session["user_email"])
    if not user:
        session.clear()
        return redirect("/login")
    
    results = analyze_user_tickers(user)
    explain_ticker = request.args.get("explain")

    rows = ""
    explanation_html = ""

    for r in results:
        rows += f"""
        <tr style="background:{COLOR.get(r['action'], '#fff')}">
            <td><b>{r['ticker']}</b></td>
            <td>${r['price'] if r['price'] else '-'}</td>
            <td>{round(r['rsi'], 1) if r['rsi'] else "-"}</td>
            <td>${round(r['dma_50'], 2) if r['dma_50'] else "-"}</td>
            <td>${round(r['dma_200'], 2) if r['dma_200'] else "-"}</td>
            <td>{r['volume_trend'] if r['volume_trend'] else "-"}</td>
            <td>${r['52w_low'] if r['52w_low'] else '-'}</td>
            <td>${r['52w_high'] if r['52w_high'] else '-'}</td>
            <td><b>{r['action']}</b></td>
            <td style="color:{confidence_color(r['confidence'])}">
                <b>{r['confidence']}%</b>
            </td>
            <td>
                <a href="/batch-json?explain={r['ticker']}" style="color:#4299e1;text-decoration:none;">📊 Explain</a>
            </td>
        </tr>
        """

        if explain_ticker == r["ticker"]:
            reasons = "".join(f"<li>{x}</li>" for x in r["reasons"])
            explanation_html = f"""
            <div style="background:#f7fafc;padding:20px;margin:20px 0;border-left:4px solid #4299e1;border-radius:5px;">
                <h3>📊 Explanation for {r['ticker']}</h3>
                <ul style="line-height:1.8;">{reasons}</ul>
                <p style="color:#666;font-size:14px;">Confidence: <b style="color:{confidence_color(r['confidence'])}">{r['confidence']}%</b></p>
            </div>
            """

    return f"""
    <html>
    <head>
        <title>TradeAdvisor Dashboard</title>
        <style>
            body {{ font-family: Arial, sans-serif; max-width: 1400px; margin: 0 auto; padding: 20px; background: #f7fafc; }}
            h2 {{ color: #2d3748; }}
            table {{ width: 100%; border-collapse: collapse; background: white; box-shadow: 0 1px 3px rgba(0,0,0,0.1); }}
            th, td {{ padding: 12px; text-align: left; border-bottom: 1px solid #e2e8f0; }}
            th {{ background: #4299e1; color: white; font-weight: bold; }}
            .header {{ display: flex; justify-content: space-between; align-items: center; margin-bottom: 20px; }}
            .button {{ background: #4299e1; color: white; padding: 10px 20px; text-decoration: none; border-radius: 5px; border: none; cursor: pointer; }}
            .button:hover {{ background: #3182ce; }}
            .logout {{ background: #e53e3e; }}
            .logout:hover {{ background: #c53030; }}
        </style>
    </head>
    <body>
        <div class="header">
            <div>
                <h2>📈 TradeAdvisor Dashboard</h2>
                <p style="color:#666;">Welcome, {user['name']} ({user['email']})</p>
            </div>
            <div>
                <form method="post" action="/email-results" style="display:inline;">
                    <button class="button">📧 Email Results</button>
                </form>
                <a href="/logout" class="button logout">🚪 Logout</a>
            </div>
        </div>

        <table>
            <tr>
                <th>Ticker</th>
                <th>Price</th>
                <th>RSI</th>
                <th>50 DMA</th>
                <th>200 DMA</th>
                <th>Volume</th>
                <th>52W Low</th>
                <th>52W High</th>
                <th>Action</th>
                <th>Confidence</th>
                <th>Details</th>
            </tr>
            {rows}
        </table>

        {explanation_html}
        
        <p style="color:#666;margin-top:30px;font-size:14px;">
            💡 Data cached until end of day. Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}
        </p>
    </body>
    </html>
    """

# =========================
# Email batch results
# =========================

@app.route("/email-results", methods=["POST"])
@limiter.limit("10 per hour")  # Prevent email spam
@csrf.exempt  # FIXED: Disable CSRF for this route
def email_results():
    if "user_email" not in session:
        return redirect("/login")

    user = get_user_by_email(session["user_email"])
    if not user:
        return redirect("/login")
    
    results = analyze_user_tickers(user)

    rows = "".join(
        f"""<tr style="background:{COLOR.get(r['action'], '#fff')}">
            <td><b>{r['ticker']}</b></td>
            <td><b>{r['action']}</b></td>
            <td style="color:{confidence_color(r['confidence'])}">{r['confidence']}%</td>
            <td>${r['price'] if r['price'] else '-'}</td>
        </tr>"""
        for r in results
    )

    html = f"""
    <html>
    <body style="font-family:Arial,sans-serif;max-width:800px;margin:0 auto;padding:20px;">
        <h2 style="color:#2d3748;">📈 Your TradeAdvisor Results</h2>
        <p>Generated on: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}</p>
        <table border="1" cellpadding="12" style="width:100%;border-collapse:collapse;">
            <tr style="background:#4299e1;color:white;">
                <th>Ticker</th>
                <th>Action</th>
                <th>Confidence</th>
                <th>Price</th>
            </tr>
            {rows}
        </table>
        <p style="color:#666;margin-top:20px;font-size:14px;">
            This is an automated report from TradeAdvisor. Not financial advice.
        </p>
    </body>
    </html>
    """

    try:
        send_email(user["email"], "Your TradeAdvisor Results", html)
        return """
        <html>
        <body style="font-family:Arial,sans-serif;max-width:600px;margin:50px auto;padding:20px;">
            <h2>✓ Email sent successfully!</h2>
            <p><a href="/batch-json">← Back to dashboard</a></p>
        </body>
        </html>
        """
    except Exception as e:
        print(f"Email error: {e}")
        return "Error sending email. Please try again.", 500

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
# =========================

if __name__ == "__main__":
    print(">>> Starting TradeAdvisor server")
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("RENDER") is None
    app.run(host="0.0.0.0", port=port, debug=debug)
