from flask import Flask, request, render_template_string
from trade_advisor import get_trade_advisor_data, get_trade_recommendation

app = Flask(__name__)

HTML_TEMPLATE = """
<!DOCTYPE html>
<html>
<head>
    <title>TradeAdvisor</title>
    <style>
        body {
            font-family: Arial, sans-serif;
        }
        table {
            border-collapse: collapse;
            margin-top: 20px;
            width: 420px;
        }
        th, td {
            border: 1px solid #ccc;
            padding: 8px 12px;
            text-align: left;
        }
        th {
            background-color: #f4f4f4;
        }
        .BUY {
            color: white;
            background-color: #2ecc71;
            font-weight: bold;
            text-align: center;
        }
        .HOLD {
            color: white;
            background-color: #f39c12;
            font-weight: bold;
            text-align: center;
        }
        .SELL {
            color: white;
            background-color: #e74c3c;
            font-weight: bold;
            text-align: center;
        }
    </style>
</head>
<body>

<h2>TradeAdvisor</h2>

<form method="get" action="/tradeadvisor">
    <label>Ticker:</label>
    <input type="text" name="ticker" value="{{ ticker }}" required>
    <button type="submit">Analyze</button>
</form>

{% if data %}
<table>
    <tr><th>Metric</th><th>Value</th></tr>
    <tr><td>Ticker</td><td>{{ data.ticker }}</td></tr>
    <tr><td>Current Price</td><td>{{ data.current_price }}</td></tr>
    <tr><td>Previous Close</td><td>{{ data.previous_close }}</td></tr>
    <tr><td>52W Low</td><td>{{ data["52w_low"] }}</td></tr>
    <tr><td>52W High</td><td>{{ data["52w_high"] }}</td></tr>
    <tr><td>Market Cap</td><td>{{ data.market_cap }}</td></tr>
    <tr><td>200 DMA</td><td>{{ data.dma_200 }}</td></tr>
    <tr><td>50 DMA</td><td>{{ data.dma_50 }}</td></tr>
    <tr><td>RSI (14)</td><td>{{ data.rsi_14 }}</td></tr>
    <tr>
        <td><strong>Recommendation</strong></td>
        <td class="{{ recommendation }}">{{ recommendation }}</td>
    </tr>
</table>
{% endif %}

</body>
</html>
"""

@app.route("/tradeadvisor")
def tradeadvisor():
    ticker = request.args.get("ticker", "").upper()

    if not ticker:
        return render_template_string(HTML_TEMPLATE, data=None, recommendation=None, ticker="")

    data = get_trade_advisor_data(ticker)
    recommendation = get_trade_recommendation(data)

    return render_template_string(
        HTML_TEMPLATE,
        data=data,
        recommendation=recommendation,
        ticker=ticker
    )

@app.route("/")
def home():
    return """
    <h2>TradeAdvisor</h2>
    <p>Go to <a href="/tradeadvisor">/tradeadvisor</a> to analyze a stock.</p>
    """

if __name__ == "__main__":
    app.run(debug=True)
