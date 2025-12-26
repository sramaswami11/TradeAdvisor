from flask import Flask, request
import os
from trade_advisor import get_trade_advisor_data, get_trade_recommendation

app = Flask(__name__)

COLOR = {
    "BUY": "#c6f6d5",
    "SELL": "#fed7d7",
    "HOLD": "#edf2f7"
}

@app.route("/", methods=["GET"])
def home():
    ticker = request.args.get("ticker")

    if not ticker:
        return """
        <h2>TradeAdvisor</h2>
        <form method="get">
            <input name="ticker" placeholder="Enter ticker (e.g. AAPL)" />
            <button type="submit">Analyze</button>
        </form>
        """

    data = get_trade_advisor_data(ticker)
    result = get_trade_recommendation(data)
    bg = COLOR[result["action"]]

    rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in data.items()
    )

    reasons = "".join(f"<li>{r}</li>" for r in result["reasons"])

    return f"""
    <h2>TradeAdvisor – {ticker.upper()}</h2>
    <table border="1" cellpadding="6">{rows}</table>
    <h3 style="background:{bg};padding:10px">
        Recommendation: {result['action']}
    </h3>
    <ul>{reasons}</ul>
    <a href="/">Analyze another</a>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("RENDER") is None
    app.run(host="0.0.0.0", port=port, debug=debug)
