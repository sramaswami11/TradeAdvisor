# market_data/service.py
from market_data.provider import fetch_snapshot

def get_market_snapshot(ticker: str) -> dict:
    return fetch_snapshot(ticker)
