"""
Tradier options data provider.

Implements get_expirations / get_chain using Tradier's official REST API.
Auth is per API key — no IP-based rate limiting.
"""

import logging
import pandas as pd
import requests
from types import SimpleNamespace

logger = logging.getLogger(__name__)

_BASE_PROD    = "https://api.tradier.com/v1"
_BASE_SANDBOX = "https://sandbox.tradier.com/v1"


class TradierOptionsProvider:

    def __init__(self, api_key: str, sandbox: bool = False):
        self._base = _BASE_SANDBOX if sandbox else _BASE_PROD
        self._session = requests.Session()
        self._session.headers.update({
            "Authorization": f"Bearer {api_key}",
            "Accept": "application/json",
        })

    def get_expirations(self, symbol: str) -> list:
        """Return list of expiration date strings (YYYY-MM-DD) for the symbol."""
        try:
            resp = self._session.get(
                f"{self._base}/markets/options/expirations",
                params={"symbol": symbol.upper(), "includeAllRoots": "false"},
                timeout=10,
            )
            resp.raise_for_status()
            dates = (resp.json().get("expirations") or {}).get("date", [])
            if isinstance(dates, str):
                dates = [dates]
            return [d for d in (dates or []) if d]
        except Exception as e:
            logger.warning(f"Tradier expirations failed for {symbol}: {e}")
            return []

    def get_chain(self, symbol: str, expiry: str):
        """
        Return a SimpleNamespace with .puts and .calls DataFrames using the
        same column names as yfinance (strike, bid, ask, lastPrice,
        openInterest, impliedVolatility) so OptionsEngine needs no changes.
        """
        try:
            resp = self._session.get(
                f"{self._base}/markets/options/chains",
                params={
                    "symbol": symbol.upper(),
                    "expiration": expiry,
                    "greeks": "true",
                },
                timeout=15,
            )
            resp.raise_for_status()
            options = (resp.json().get("options") or {}).get("option", [])
            if not options:
                return None
            if isinstance(options, dict):
                options = [options]

            puts_rows, calls_rows = [], []
            for opt in options:
                greeks = opt.get("greeks") or {}
                row = {
                    "strike": opt.get("strike"),
                    "bid": opt.get("bid"),
                    "ask": opt.get("ask"),
                    "lastPrice": opt.get("last"),
                    "openInterest": opt.get("open_interest"),
                    "impliedVolatility": greeks.get("mid_iv"),
                }
                if opt.get("option_type") == "put":
                    puts_rows.append(row)
                else:
                    calls_rows.append(row)

            return SimpleNamespace(
                puts=pd.DataFrame(puts_rows) if puts_rows else pd.DataFrame(),
                calls=pd.DataFrame(calls_rows) if calls_rows else pd.DataFrame(),
            )
        except Exception as e:
            logger.warning(f"Tradier chain failed for {symbol} {expiry}: {e}")
            return None
