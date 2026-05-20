"""
Trade Advisor Strategy Engine
Quant-style decision engine based on:
- 200 DMA trend
- 50 DMA momentum
- RSI oversold/overbought
- 52 week positioning
"""

class StrategyEngine:

    def __init__(self, data):
        self.data = data

    def evaluate(self):

        price = self.data.get("current_price")
        low = self.data.get("52w_low")
        high = self.data.get("52w_high")
        dma200 = self.data.get("dma_200")
        dma50 = self.data.get("dma_50")
        rsi = self.data.get("rsi_14")

        # ---- numeric validation ----
        for key in ["current_price", "52w_low", "52w_high", "dma_200", "dma_50"]:
            val = self.data.get(key)
            if val is not None and not isinstance(val, (int, float)):
                raise TypeError(f"{key} must be numeric")

        # ---- invalid price safety ----
        if price is None or price <= 0:
            return {
                "action": "HOLD",
                "confidence": 0,
                "signals": {},
                "reasons": ["Invalid or missing price data."]
            }

        # ---- data sufficiency ----
        required_fields = [dma200, dma50, rsi]

        if any(v is None for v in required_fields):
            return {
                "action": "HOLD",
                "confidence": 0,
                "signals": {},
                "reasons": ["Insufficient technical indicator data."]
            }

        # ---- signals ----
        above_200 = price > dma200
        above_50 = price > dma50

        if rsi <= 30:
            rsi_state = "oversold"
        elif rsi > 70:
            rsi_state = "overbought"
        else:
            rsi_state = "neutral"

        position_zone = "middle"

        if low is not None and price <= low * 1.05:
            position_zone = "near_low"

        if high is not None and price >= high * 0.95:
            position_zone = "near_high"

        # ---- scoring ----
        score = 0

        if above_200:
            score += 1

        if above_50:
            score += 1

        if rsi_state == "oversold":
            score += 1

        if position_zone == "near_low":
            score += 1

        if position_zone == "near_high":
            score -= 1

        # ---- decision ----
        action = "HOLD"

        if (
            above_200
            and above_50
            and rsi_state == "oversold"
            and position_zone == "near_low"
        ):
            action = "BUY"

        elif position_zone == "near_high" and rsi_state != "oversold":
            action = "SELL"

        confidence = max(0, min(100, score * 25))

        signals = {
            "above_200_dma": above_200,
            "above_50_dma": above_50,
            "rsi_state": rsi_state,
            "position_zone": position_zone,
            "score": score
        }

        # ---- human-readable reasons ----
        reasons = []

        if above_200:
            reasons.append("Price is above 200-day moving average.")
        else:
            reasons.append("Price is below 200-day moving average.")

        if above_50:
            reasons.append("Price is above 50-day moving average.")
        else:
            reasons.append("Price is below 50-day moving average.")

        if rsi_state == "oversold":
            reasons.append("RSI indicates oversold conditions.")
        elif rsi_state == "overbought":
            reasons.append("RSI indicates overbought conditions.")
        else:
            reasons.append("RSI is neutral.")

        if position_zone == "near_low":
            reasons.append("Price is near 52-week low.")
        elif position_zone == "near_high":
            reasons.append("Price is near 52-week high.")

        return {
            "action": action,
            "confidence": confidence,
            "signals": signals,
            "reasons": reasons
        }


# ---------- compatibility wrappers ----------

def get_trade_recommendation(data):

    engine = StrategyEngine(data)
    result = engine.evaluate()

    return {
        "action": result["action"],
        "confidence": result["confidence"],
        "signals": result.get("signals", {}),
        "reasons": result.get("reasons", [])
    }


def explain_trade_recommendation(data):

    engine = StrategyEngine(data)
    result = engine.evaluate()

    return result.get("reasons", ["No rationale available."])