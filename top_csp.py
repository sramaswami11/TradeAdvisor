import json
import os
import threading
import time
from options_engine import get_shared_engine

_CACHE_DIR = "/tmp" if os.path.exists("/tmp") else "."
_TOP_CSP_CACHE_FILE = os.path.join(_CACHE_DIR, "top_csp_cache.json")
_TOP_CSP_CACHE_SECONDS = 3600  # 1 hour

options_engine = get_shared_engine()

WATCHLIST = [
    "SPY",
    "QQQ",
]

_bg_thread = None
_thread_lock = threading.Lock()


def _load_top_csp_cache(allow_stale=False):
    try:
        if not os.path.exists(_TOP_CSP_CACHE_FILE):
            return None
        with open(_TOP_CSP_CACHE_FILE, "r") as f:
            data = json.load(f)
        age = time.time() - data.get("timestamp", 0)
        if age < _TOP_CSP_CACHE_SECONDS:
            print(f"TOP CSP CACHE HIT (age={int(age)}s)")
            return data["opportunities"]
        if allow_stale and data.get("opportunities"):
            print(f"TOP CSP STALE CACHE (age={int(age)}s)")
            return data["opportunities"]
        print(f"TOP CSP CACHE EXPIRED (age={int(age)}s)")
        return None
    except Exception as ex:
        print("TOP CSP CACHE LOAD ERROR:", ex)
        return None


def _save_top_csp_cache(opportunities):
    try:
        with open(_TOP_CSP_CACHE_FILE, "w") as f:
            json.dump({
                "timestamp": time.time(),
                "opportunities": opportunities
            }, f)
        print(f"TOP CSP CACHE SAVED ({len(opportunities)} opportunities)")
    except Exception as ex:
        print("TOP CSP CACHE SAVE ERROR:", ex)


def _do_scan():
    results = []
    for symbol in WATCHLIST:
        try:
            opportunities = options_engine.find_csp_opportunities(symbol)
            print(f"TOP CSP SCAN {symbol}: {len(opportunities)} opportunities")
            if opportunities:
                results.extend(opportunities[:3])
        except Exception as ex:
            print(f"TOP CSP SCAN ERROR {symbol}: {ex}")

    results.sort(key=lambda x: x["score"], reverse=True)
    results = results[:15]

    if results:
        _save_top_csp_cache(results)


def _background_refresh_loop():
    while True:
        try:
            _do_scan()
        except Exception as ex:
            print("TOP CSP BG THREAD ERROR:", ex)
        time.sleep(_TOP_CSP_CACHE_SECONDS)


def _ensure_bg_thread():
    global _bg_thread
    with _thread_lock:
        if _bg_thread is None or not _bg_thread.is_alive():
            _bg_thread = threading.Thread(
                target=_background_refresh_loop,
                daemon=True,
                name="top-csp-refresh"
            )
            _bg_thread.start()
            print("TOP CSP: background refresh thread started")


def get_top_csp_opportunities():
    _ensure_bg_thread()
    cached = _load_top_csp_cache(allow_stale=True)
    return cached if cached is not None else []
