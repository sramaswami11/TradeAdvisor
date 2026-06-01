from options_engine import OptionsEngine

options_engine = OptionsEngine()

WATCHLIST = [
    "SPY",
    "QQQ",
    "NVDA",
    "MSFT",
    "META"
    
]

# WATCHLIST = [
#     "SPY",
#     "QQQ",
#     "NVDA",
#     "MSFT",
#     "META",
#     "GOOGL",
#     "AMZN",
#     "AAPL",
#     "AVGO",
#     "TSM",
#     "AMD",
#     "PLTR",
#     "JPM",
#     "COST",
#     "V"
# ]

def get_top_csp_opportunities():

    results = []

    for symbol in WATCHLIST:

        try:

            opportunities = (
                options_engine
                .find_csp_opportunities(symbol)
            )

            print(
            f"{symbol}: {len(opportunities)} opportunities"
            )


            if opportunities:

                results.extend(
                    opportunities[:3]
                )

        except Exception as ex:
            print(f"TOP CSP ERROR {symbol}: {ex}")

    results.sort(
        key=lambda x: x["score"],
        reverse=True
    )

    return results[:15]