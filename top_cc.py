import json
import os
import threading
import time
from concurrent.futures import ThreadPoolExecutor, as_completed
from options_engine import get_shared_engine
from database import get_cache, set_cache, get_all_tickers

_CACHE_DIR = "/tmp" if os.path.exists("/tmp") else "."
_TOP_CC_CACHE_FILE = os.path.join(_CACHE_DIR, "top_cc_cache.json")
_TOP_CC_CACHE_SECONDS = 3600  # 1 hour

options_engine = get_shared_engine()

_DEFAULT_WATCHLIST = ["AAPL", "MSFT", "NVDA", "SPY"]

_SCAN_WORKERS = 1

_bg_thread = None
_thread_lock = threading.Lock()


def _load_top_cc_cache(allow_stale=False):
    try:
        if os.path.exists(_TOP_CC_CACHE_FILE):
            with open(_TOP_CC_CACHE_FILE, "r") as f:
                data = json.load(f)
            age = time.time() - data.get("timestamp", 0)
            if age < _TOP_CC_CACHE_SECONDS:
                return data["opportunities"]
            if allow_stale and data.get("opportunities"):
                return data["opportunities"]
    except Exception:
        pass

    try:
        row = get_cache("top_cc_cache")
        if row:
            age = time.time() - row["timestamp"]
            opps = json.loads(row["value"])
            if age < _TOP_CC_CACHE_SECONDS:
                return opps
            if allow_stale and opps:
                return opps
    except Exception:
        pass

    return None


def _save_top_cc_cache(opportunities):
    ts = time.time()
    data = {"timestamp": ts, "opportunities": opportunities}
    try:
        with open(_TOP_CC_CACHE_FILE, "w") as f:
            json.dump(data, f)
    except Exception:
        pass

    try:
        set_cache("top_cc_cache", json.dumps(opportunities), ts)
    except Exception:
        pass


def _scan_symbol(symbol):
    try:
        opps, _ = options_engine.find_cc_opportunities(symbol)
        return opps[:3] if opps else []
    except Exception:
        return []


def _do_scan():
    watchlist = get_all_tickers() or _DEFAULT_WATCHLIST
    per_symbol = {}

    with ThreadPoolExecutor(max_workers=_SCAN_WORKERS) as executor:
        futures = {executor.submit(_scan_symbol, sym): sym for sym in watchlist}
        for future in as_completed(futures):
            sym = futures[future]
            result = future.result()
            if result:
                per_symbol[sym] = result

    guaranteed = [opps[0] for opps in per_symbol.values()]
    overflow = sorted(
        [opp for opps in per_symbol.values() for opp in opps[1:]],
        key=lambda x: x["score"],
        reverse=True
    )
    results = guaranteed + overflow
    results.sort(key=lambda x: x["score"], reverse=True)

    if results:
        _save_top_cc_cache(results)


def _background_refresh_loop():
    while True:
        try:
            _do_scan()
        except Exception:
            pass
        time.sleep(_TOP_CC_CACHE_SECONDS)


def _ensure_bg_thread():
    global _bg_thread
    with _thread_lock:
        if _bg_thread is None or not _bg_thread.is_alive():
            _bg_thread = threading.Thread(
                target=_background_refresh_loop,
                daemon=True,
                name="top-cc-refresh"
            )
            _bg_thread.start()


def get_top_cc_opportunities():
    _ensure_bg_thread()
    cached = _load_top_cc_cache(allow_stale=True)
    return cached if cached is not None else []
