import time
from options_engine import get_shared_engine

options_engine = get_shared_engine()

""" WATCHLIST = [
    "SPY",
    "QQQ",
    "NVDA",
    "MSFT",
    "META",
    "GOOGL",
    "AMZN",
    "AAPL",
    "AVGO",
    "TSM",
    "AMD",
    "PLTR",
    "JPM",
    "COST",
    "V"
] """

WATCHLIST = [
    "SPY",
    "QQQ",
    
]


def get_top_csp_opportunities():

    results = []

    for idx, symbol in enumerate(WATCHLIST):

        # -----------------------------------
        # Stagger requests to avoid Yahoo
        # rate-limiting on Render's shared IPs.
        # Skip delay on the first ticker.
        # -----------------------------------
        if idx > 0:
            time.sleep(10)

        try:

            opportunities = (
                options_engine
                .find_csp_opportunities(symbol)
            )

            print(
                f"{symbol}: {len(opportunities)} opportunities"
            )

            if opportunities:
                results.extend(opportunities[:3])

        except Exception as ex:
            print(f"TOP CSP ERROR {symbol}: {ex}")

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results[:15]
