def get_trade_recommendation(data: dict) -> dict:
    """
    Core decision engine.
    Strict on types, fail-safe on missing/invalid market data.
    """

    # -----------------------------
    # Extract fields
    # -----------------------------
    price = data.get("current_price")
    low = data.get("52w_low")
    high = data.get("52w_high")
    dma_200 = data.get("dma_200")
    dma_50 = data.get("dma_50")
    rsi = data.get("rsi_14")

    # -----------------------------
    # STRICT type validation
    # -----------------------------
    numeric_fields = {
        "current_price": price,
        "52w_low": low,
        "52w_high": high,
        "dma_200": dma_200,
        "dma_50": dma_50,
        "rsi_14": rsi,
    }

    for name, value in numeric_fields.items():
        if value is not None and not isinstance(value, (int, float)):
            raise TypeError(f"{name} must be numeric, got {type(value).__name__}")

    # -----------------------------
    # Fail-safe guards
    # -----------------------------
    if (
        price is None
        or price <= 0
        or low is None
        or high is None
        or dma_200 is None
        or dma_50 is None
        or rsi is None
    ):
        return {
            "action": "HOLD",
            "confidence": 0,
            "reasons": ["Invalid or insufficient market data"],
        }

    if high == low:
        return {
            "action": "HOLD",
            "confidence": 0,
            "reasons": ["Invalid 52-week range"],
        }

    # -----------------------------
    # Scoring logic
    # -----------------------------
    score = 0
    reasons = []

    # 52-week positioning (needed early for RSI logic)
    position = (price - low) / (high - low)

    # Long-term trend (200 DMA)
    if price >= dma_200:
        score += 2
        reasons.append(
            f"Price is above the 200 DMA (${dma_200:.2f}) — long-term trend intact."
        )
    else:
        score -= 2
        reasons.append(
            f"Price is below the 200 DMA (${dma_200:.2f}) — long-term trend weak."
        )

    # Short-term momentum (50 DMA)
    if price >= dma_50:
        score += 1
        reasons.append(f"Price is above the 50 DMA (${dma_50:.2f}).")
    else:
        score -= 1
        reasons.append(f"Price is below the 50 DMA (${dma_50:.2f}).")

    # RSI (context-aware)
    if rsi <= 30:
        if position >= 0.75:
            # Oversold RSI near highs is NOT bullish
            reasons.append(
                f"RSI is low ({rsi:.1f}), but price is near the 52-week high — possible divergence."
            )
        else:
            score += 1
            reasons.append(f"RSI is low ({rsi:.1f}) — potential rebound.")
    elif rsi >= 70:
        score -= 1
        reasons.append(f"RSI is high ({rsi:.1f}) — potential pullback.")
    else:
        reasons.append(f"RSI is neutral ({rsi:.1f}).")

    # 52-week position scoring
    if position <= 0.25:
        score += 1
        reasons.append("Price is near the 52-week low.")
    elif position >= 0.75:
        score -= 1
        reasons.append("Price is near the 52-week high.")

    # -----------------------------
    # Final decision
    # -----------------------------
    if score >= 3:
        action = "BUY"
        confidence = 90
    elif score >= 1:
        action = "HOLD"
        confidence = 65
    else:
        action = "SELL"
        confidence = 55

    return {
        "action": action,
        "confidence": confidence,
        "reasons": reasons,
    }


def explain_trade_recommendation(data: dict) -> list[str]:
    """
    Human-readable explanation. Never drops critical signals.
    """

    result = get_trade_recommendation(data)

    explanations = []

    if result["action"] == "BUY":
        explanations.append(f"✅ Strong buy setup ({result['confidence']}/100).")
    elif result["action"] == "HOLD":
        explanations.append(
            f"⚖️ Partial setup ({result['confidence']}/100) — lacks full conviction."
        )
    else:
        explanations.append(f"❌ Weak setup ({result['confidence']}/100).")

    explanations.extend(result["reasons"])
    return explanations
