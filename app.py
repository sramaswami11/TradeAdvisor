from flask import Flask, request, render_template_string
from trade_advisor import get_trade_advisor_data, get_trade_recommendation

app = Flask(__name__)

# =========================
# HTML Template
# =========================

HTML_TEMPLATE = """
<h2>TradeAdvisor Report</h2>
<form method="get" action="/tradeadvisor">
  Ticker: <input type="text" name="ticker" value="{{ ticker }}">
  <input type="submit" value="Get Report">
</form>

{% if data %}
<table border="1" cellpadding="5" cellspacing="0">
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
  <tr><td><strong>Recommendation</strong></td><td><strong>{{ recommendation }}</strong></td></tr>
</table>
{% endif %}
"""

# =========================
# Routes
# =========================

@app.route("/tradeadvisor")
def tradeadvisor():
    ticker = request.args.get("ticker", "").upper()

    if not ticker:
        return render_template_string(HTML_TEMPLATE, data=None, recommendation=None, ticker="")

    data = get_trade_advisor_data(ticker)
    recommendation = get_trade_recommendation(data)

    return render_template_string(HTML_TEMPLATE, data=data, recommendation=recommendation, ticker=ticker)

@app.route("/")
def home():
    return "<h2>TradeAdvisor API</h2><p>Use: /tradeadvisor?ticker=AAPL</p>"

# =========================
# Run app
# =========================

if __name__ == "__main__":
    app.run(debug=True)
