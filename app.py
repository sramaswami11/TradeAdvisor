from flask import Flask, request
import os
from trade_advisor import get_trade_advisor_data, get_trade_recommendation

app = Flask(__name__)

COLOR = {
    "BUY": "#c6f6d5",
    "SELL": "#fed7d7",
    "HOLD": "#edf2f7"
}

def confidence_color(confidence: int) -> str:
    if confidence >= 75:
        return "#38a169"   # green
    elif confidence >= 50:
        return "#d69e2e"   # amber
    else:
        return "#e53e3e"   # red

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

    action = result["action"]
    reasons = result["reasons"]
    confidence = result.get("confidence", 0)

    bg = COLOR[action]
    conf_color = confidence_color(confidence)

    rows = "".join(
        f"<tr><td>{k}</td><td>{v}</td></tr>" for k, v in data.items()
    )

    reasons_html = "".join(f"<li>{r}</li>" for r in reasons)

    return f"""
    <h2>TradeAdvisor – {ticker.upper()}</h2>

    <table border="1" cellpadding="6">
        {rows}
    </table>

    <h3 style="background:{bg};padding:10px">
        Recommendation: {action}
    </h3>

    <p>
        <strong>Confidence:</strong>
        <span style="color:{conf_color};font-weight:bold">
            {confidence}%
        </span>
    </p>

    <div style="width:300px;border:1px solid #ccc;height:14px">
        <div style="
            width:{confidence}%;
            height:14px;
            background:{conf_color};
        "></div>
    </div>

    <h4>Reasons</h4>
    <ul>{reasons_html}</ul>

    <a href="/">Analyze another</a>
    """

if __name__ == "__main__":
    port = int(os.environ.get("PORT", 5000))
    debug = os.environ.get("RENDER") is None
    app.run(host="0.0.0.0", port=port, debug=debug)
