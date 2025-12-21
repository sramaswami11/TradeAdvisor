import os
from flask import Flask, request, jsonify
from trade_advisor import get_trade_advisor_data, get_trade_recommendation

app = Flask(__name__)

@app.route("/tradeadvisor")
def tradeadvisor():
    ticker = request.args.get("ticker")
    response_format = request.args.get("format", "html").lower()

    # ---------- SHOW INPUT FORM ----------
    if not ticker:
        return """
        <html>
        <head>
            <title>TradeAdvisor</title>
            <style>
                body { font-family: Arial, sans-serif; padding: 40px; }
                input[type=text] { padding: 8px; font-size: 16px; }
                input[type=submit] { padding: 8px 16px; font-size: 16px; }
            </style>
        </head>
        <body>
            <h2>TradeAdvisor</h2>
            <form method="get" action="/tradeadvisor">
                <label>Enter Ticker:</label><br><br>
                <input type="text" name="ticker" placeholder="AAPL" required>
                <br><br>
                <input type="submit" value="Analyze">
            </form>
        </body>
        </html>
        """

    # ---------- FETCH DATA ----------
    data = get_trade_advisor_data(ticker)

    if data["current_price"] is None:
        return f"<h3>Invalid ticker: {ticker.upper()}</h3>"

    data["recommendation"] = get_trade_recommendation(data)

    # ---------- JSON RESPONSE ----------
    if response_format == "json":
        return jsonify(data)

    # ---------- HTML RESULT ----------
    rows = ""
    for k, v in data.items():
        rows += f"<tr><td><b>{k}</b></td><td>{v}</td></tr>"

    return f"""
    <html>
    <head>
        <title>TradeAdvisor - {data['ticker']}</title>
        <style>
            body {{ font-family: Arial, sans-serif; padding: 40px; }}
            table {{ border-collapse: collapse; width: 60%; }}
            td {{ border: 1px solid #ddd; padding: 8px; }}
            tr:nth-child(even) {{ background-color: #f9f9f9; }}
        </style>
    </head>
    <body>
        <h2>TradeAdvisor Report: {data['ticker']}</h2>
        <table>
            {rows}
        </table>
        <br>
        <a href="/tradeadvisor">Analyze another ticker</a>
        <br><br>
        <a href="/tradeadvisor?ticker={data['ticker']}&format=json">View as JSON</a>
    </body>
    </html>
    """


@app.route("/")
def home():
    return """
    <h2>TradeAdvisor</h2>
    <p><a href="/tradeadvisor">Launch TradeAdvisor</a></p>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    app.run(host="0.0.0.0", port=port)