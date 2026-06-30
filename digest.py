import json
import logging
import os
import threading
import time
from datetime import datetime
from zoneinfo import ZoneInfo

from database import get_cache, set_cache, get_all_users
from email_utils import send_email, create_email_template, ENABLE_EMAIL

logger = logging.getLogger(__name__)

_ET = ZoneInfo("America/New_York")
_SEND_HOUR = 9
_SEND_MINUTE = 35
_DIGEST_KEY = "last_digest_date"
_APP_URL = os.environ.get("APP_URL", "https://tradeadvisor-hpfq.onrender.com").rstrip("/")

_lock = threading.Lock()
_fired_date = None  # in-process guard to avoid double-firing


# --------------------------------------------------
# Scheduling helpers
# --------------------------------------------------

def _today_et() -> str:
    return datetime.now(_ET).strftime("%Y-%m-%d")


def _is_due() -> bool:
    now = datetime.now(_ET)
    if now.weekday() >= 5:
        return False
    return now.hour > _SEND_HOUR or (now.hour == _SEND_HOUR and now.minute >= _SEND_MINUTE)


def _already_sent() -> bool:
    try:
        row = get_cache(_DIGEST_KEY)
        if row:
            return row["value"] == _today_et()
    except Exception:
        pass
    return False


def _mark_sent():
    set_cache(_DIGEST_KEY, _today_et(), time.time())


# --------------------------------------------------
# Email content builders
# --------------------------------------------------

_BADGE = {
    "STRONG": "#16a34a",
    "GOOD":   "#2563eb",
    "OK":     "#d97706",
    "WEAK":   "#dc2626",
}

_TH = "padding:8px 12px;text-align:left;background:#f8fafc;font-size:13px;font-weight:600;color:#374151;"
_TD = "padding:8px 12px;font-size:14px;border-bottom:1px solid #e2e8f0;"


def _opp_row(opp: dict, side: str) -> str:
    symbol   = opp.get("symbol", "")
    strike   = opp.get("strike", "")
    expiry   = opp.get("expiry", "")
    dte      = opp.get("dte", "")
    bid      = opp.get("bid", 0)
    ann      = opp.get("annualized", 0)
    dist     = opp.get("distance_pct", 0)
    score    = opp.get("score", 0)
    rec      = opp.get("recommendation", "")
    color    = _BADGE.get(rec, "#6b7280")
    url      = f"{_APP_URL}/{side}/{symbol}"
    sign     = "+" if dist >= 0 else ""

    return (
        f'<tr>'
        f'<td style="{_TD}font-weight:600;">'
        f'  <a href="{url}" style="color:#4a6cf7;text-decoration:none;">{symbol}</a>'
        f'</td>'
        f'<td style="{_TD}">${strike}</td>'
        f'<td style="{_TD}">{expiry}</td>'
        f'<td style="{_TD};text-align:center;">{dte}</td>'
        f'<td style="{_TD}">${bid}</td>'
        f'<td style="{_TD};font-weight:600;color:#16a34a;">{ann}%</td>'
        f'<td style="{_TD}">{sign}{dist}%</td>'
        f'<td style="{_TD}">'
        f'  <span style="background:{color};color:white;padding:2px 8px;border-radius:12px;'
        f'font-size:12px;font-weight:600;">{score} {rec}</span>'
        f'</td>'
        f'</tr>'
    )


def _section_table(opps: list, side: str) -> str:
    if not opps:
        return "<p style='color:#6b7280;font-style:italic;margin:8px 0 16px;'>No opportunities in cache yet.</p>"

    cols = ["Symbol", "Strike", "Expiry", "DTE", "Bid", "Ann%", "Distance%", "Score"]
    header = "".join(f'<th style="{_TH}">{c}</th>' for c in cols)
    rows   = "".join(_opp_row(o, side) for o in opps)

    return (
        f'<table style="width:100%;border-collapse:collapse;margin-bottom:8px;">'
        f'<thead><tr>{header}</tr></thead>'
        f'<tbody>{rows}</tbody>'
        f'</table>'
    )


def _build_email(csp_opps: list, cc_opps: list) -> str:
    date_str = datetime.now(_ET).strftime("%A, %B %-d")
    h2 = "font-size:15px;color:#1e293b;margin:24px 0 8px;"

    content = f"""
<p style="color:#374151;margin-bottom:16px;">
  Good morning! Here are today's top-scored options opportunities as of market open.
  Click any symbol to run a fresh live scan.
</p>

<h2 style="{h2}">&#x1F4C9; Top Cash-Secured Puts (CSP)</h2>
{_section_table(csp_opps, "csp")}

<h2 style="{h2}">&#x1F4C8; Top Covered Calls (CC)</h2>
{_section_table(cc_opps, "cc")}

<p style="color:#9ca3af;font-size:12px;margin-top:24px;">
  Opportunities sourced from hourly background scan &middot;
  data via Yahoo Finance (~15&ndash;75 min delayed) &middot;
  verify with your broker before trading.
</p>
"""
    return create_email_template(f"TradeAdvisor &middot; {date_str}", content)


# --------------------------------------------------
# Send logic
# --------------------------------------------------

def _load_opps(cache_key: str, limit: int = 5) -> list:
    try:
        row = get_cache(cache_key)
        if row:
            return json.loads(row["value"])[:limit]
    except Exception:
        pass
    return []


def _do_send():
    from top_csp import get_top_csp_opportunities
    from top_cc import get_top_cc_opportunities
    csp_opps = get_top_csp_opportunities()[:5]
    cc_opps  = get_top_cc_opportunities()[:5]

    if not csp_opps and not cc_opps:
        logger.info("Digest: both caches empty — skipping")
        return

    users = get_all_users()
    if not users:
        logger.info("Digest: no registered users")
        return

    subject = f"TradeAdvisor · {datetime.now(_ET).strftime('%b %-d')} · Top CSP & CC Opportunities"
    html    = _build_email(csp_opps, cc_opps)

    sent = 0
    for user in users:
        email = user.get("email")
        if not email:
            continue
        try:
            send_email(email, subject, html)
            sent += 1
        except Exception:
            logger.exception("Digest: failed to send to %s", email)

    _mark_sent()
    logger.info("Digest sent to %d user(s) — %d CSP, %d CC opportunities", sent, len(csp_opps), len(cc_opps))


# --------------------------------------------------
# Public entry point — call from before_request
# --------------------------------------------------

def maybe_send_digest():
    """Fire the daily digest if it's due and hasn't been sent yet today.

    Fast path (in-memory flag or time check) returns immediately on most calls.
    Actual send runs in a daemon thread so it never blocks a request.
    """
    global _fired_date

    if not ENABLE_EMAIL:
        return
    if not _is_due():
        return

    today = _today_et()

    with _lock:
        if _fired_date == today:
            return
        if _already_sent():
            _fired_date = today
            return
        _fired_date = today  # claim the slot before leaving the lock

    threading.Thread(target=_do_send, daemon=True, name="digest-send").start()
