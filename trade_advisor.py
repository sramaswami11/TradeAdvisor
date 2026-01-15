import json
import logging
from pathlib import Path

from market_data.service import get_market_snapshot

# =========================
# Logging
# =========================

logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# =========================
# Confidence Scoring (Enhanced)
# =========================

def calculate_confidence(action: str, data: dict) -> int:
    price = data.get("current_price")
    low = data.get("52w_low")
    high = data.get("52w_high")
    dma_200 = data.get("dma_200")
    dma_50 = data.get("dma_50")
    rsi = data.get("rsi_14")

    # Missing critical data → zero confidence
    if None in (price, low, high, dma_200, dma_50, rsi):
        return 0

    confidence = 0

    if action == "BUY":
        if price <= low * 1.10:
            confidence += 25
        if price > dma_200:
            confidence += 20
        if price >= dma_50:
            confidence += 15
        if 30 <= rsi <= 35:
            confidence += 25
        # Bonus for strong trend
        if price > dma_200 and price > dma_50:
            confidence += 10

    elif action == "SELL":
        if price >= high * 0.90:
            confidence += 40
        if price < dma_200:
            confidence += 40
        if rsi > 70:
            confidence += 20
        # Bonus for weak trend
        if price < dma_200 and price < dma_50:
            confidence += 10

    else:  # HOLD
        confidence = 50
        # Strong position but not extreme
        if price > dma_200 and 40 < rsi < 60:
            confidence += 15
        # Consolidating near support
        if abs(price - dma_50) / dma_50 < 0.02:  # Within 2% of 50 DMA
            confidence += 10
        # Uncertain conditions
        if rsi < 30 or rsi > 70:
            confidence -= 15
        # Weak technicals
        if price < dma_200:
            confidence -= 10

    return min(max(confidence, 0), 100)

# =========================
# Data Collection
# =========================

def get_trade_advisor_data(ticker: str) -> dict:
    """Fetch market data for a ticker"""
    snapshot = get_market_snapshot(ticker)

    if not isinstance(snapshot, dict):
        logger.error(f"{ticker}: market snapshot is invalid ({snapshot})")
        return {
            "ticker": ticker,
            "current_price": None,
            "52w_high": None,
            "52w_low": None,
            "dma_50": None,
            "dma_200": None,
            "rsi_14": None,
            "volume": None,
        }

    return snapshot


# =========================
# Trade Recommendation Logic (IMPROVED)
# =========================

def get_trade_recommendation(data: dict) -> dict:
    """Generate BUY/SELL/HOLD recommendation with reasoning"""
    reasons = []

    price = data.get("current_price")
    low = data.get("52w_low")
    high = data.get("52w_high")
    dma_200 = data.get("dma_200")
    dma_50 = data.get("dma_50")
    rsi = data.get("rsi_14")

    # Insufficient data guard
    if None in (price, low, high, dma_200, dma_50, rsi):
        return {
            "action": "HOLD",
            "confidence": 0,
            "reasons": ["Insufficient data to form a reliable signal"]
        }

    near_low = price <= low * 1.10
    near_high = price >= high * 0.90
    above_200 = price > dma_200
    above_50 = price >= dma_50
    below_200 = price < dma_200
    below_50 = price < dma_50

    # =========================
    # STRONG BUY CONDITIONS
    # =========================
    buy_score = 0
    buy_reasons = []

    if near_low:
        buy_reasons.append(f"✓ Price near 52-week low (${price:.2f} vs ${low:.2f})")
        buy_score += 25
    
    if above_200:
        buy_reasons.append(f"✓ Above 200-day MA (${dma_200:.2f})")
        buy_score += 25

    if above_50:
        buy_reasons.append(f"✓ At/Above 50-day MA (${dma_50:.2f})")
        buy_score += 20

    if 30 <= rsi <= 35:
        buy_reasons.append(f"✓ RSI in accumulation zone ({rsi:.1f})")
        buy_score += 30

    # =========================
    # STRONG SELL CONDITIONS
    # =========================
    sell_score = 0
    sell_reasons = []

    if near_high:
        sell_reasons.append(f"⚠ Price near 52-week high (${price:.2f} vs ${high:.2f})")
        sell_score += 40

    if below_200:
        sell_reasons.append(f"⚠ Below 200-day MA (${dma_200:.2f}) - bearish")
        sell_score += 40

    if rsi > 70:
        sell_reasons.append(f"⚠ RSI overbought ({rsi:.1f})")
        sell_score += 20

    if below_50:
        sell_reasons.append(f"⚠ Below 50-day MA (${dma_50:.2f})")
        sell_score += 10

    # =========================
    # DECISION LOGIC (Score-Based)
    # =========================

    # Strong BUY: All 4 conditions met
    if buy_score >= 90:  # All major buy conditions
        confidence = calculate_confidence("BUY", data)
        return {
            "action": "BUY",
            "confidence": confidence,
            "reasons": buy_reasons
        }

    # Strong SELL: High near-term risk
    if sell_score >= 80 and near_high and below_200:
        confidence = calculate_confidence("SELL", data)
        return {
            "action": "SELL",
            "confidence": confidence,
            "reasons": sell_reasons
        }

    # Weak SELL: Multiple bearish signals (NEW!)
    if sell_score >= 50 and below_200 and below_50:
        confidence = calculate_confidence("SELL", data)
        if confidence >= 40:  # Only recommend SELL if reasonably confident
            return {
                "action": "SELL",
                "confidence": confidence,
                "reasons": sell_reasons + [
                    "Multiple bearish technical signals suggest weakness"
                ]
            }
    
    # FALLING KNIFE SELL: Severely oversold in downtrend (NEW!)
    if rsi < 30 and below_200 and below_50:
        confidence = calculate_confidence("SELL", data)
        return {
            "action": "SELL", 
            "confidence": max(confidence, 60),  # At least 60% confidence
            "reasons": [
                f"🔻 Falling knife pattern detected",
                f"Price below both 50-day MA (${dma_50:.2f}) and 200-day MA (${dma_200:.2f})",
                f"RSI severely oversold ({rsi:.1f}) - suggesting panic selling",
                f"Recommendation: Avoid catching falling knives - wait for stabilization"
            ]
        }

    # =========================
    # HOLD WITH CONTEXT
    # =========================

    hold_reasons = []
    
    # Determine the dominant narrative
    if buy_score > sell_score:
        # Leaning bullish but not enough
        hold_reasons.append(f"⚖️ Partial buy setup ({buy_score}/100) - lacks full conviction")
        
        # Explain what's missing for BUY
        if not near_low:
            hold_reasons.append(f"⚠ Not at attractive entry - price ${price:.2f} vs 52W low ${low:.2f}")
        if not (30 <= rsi <= 35):
            hold_reasons.append(f"⚠ RSI not in buy zone - currently {rsi:.1f} (target: 30-35)")
        if above_200:
            hold_reasons.append(f"✓ Long-term trend intact (above 200 DMA ${dma_200:.2f})")
            
    elif sell_score > buy_score:
        # Leaning bearish but not critical
        hold_reasons.append(f"⚖️ Caution signals present ({sell_score}/100) - monitoring for deterioration")
        
        # Explain the concerns
        if near_high:
            hold_reasons.append(f"⚠ Near resistance - price ${price:.2f} approaching 52W high ${high:.2f}")
        if below_50:
            hold_reasons.append(f"⚠ Short-term weakness - below 50 DMA ${dma_50:.2f}")
        if below_200:
            hold_reasons.append(f"⚠ Long-term downtrend - below 200 DMA ${dma_200:.2f}")
        if rsi > 65:
            hold_reasons.append(f"⚠ Momentum extended - RSI {rsi:.1f}")
            
    else:
        # Truly neutral
        hold_reasons.append("⚖️ Neutral technical setup - no strong signals")
        
        if above_200:
            hold_reasons.append(f"✓ Above 200-day MA (${dma_200:.2f}) - long-term trend positive")
        if 40 <= rsi <= 60:
            hold_reasons.append(f"⚖️ RSI neutral ({rsi:.1f}) - balanced momentum")

    if not hold_reasons:
        hold_reasons.append("No strong signals in either direction - wait for clearer setup")

    confidence = calculate_confidence("HOLD", data)
    
    return {
        "action": "HOLD",
        "confidence": confidence,
        "reasons": hold_reasons
    }


# =========================
# Explainability wrapper
# =========================

def explain_trade_recommendation(data: dict) -> list:
    """Return human-readable explanations for the trade decision"""
    result = get_trade_recommendation(data)
    return result.get("reasons", ["Insufficient data to generate recommendation"])


# =========================
# Batch JSON processing
# =========================

def analyze_tickers_from_json(json_path: str) -> list[dict]:
    """Batch analyze tickers from JSON file"""
    path = Path(json_path)

    with open(path, "r") as f:
        payload = json.load(f)

    results = []

    for ticker in payload.get("tickers", []):
        try:
            data = get_trade_advisor_data(ticker)
            result = get_trade_recommendation(data)

            results.append({
                "ticker": ticker,
                "price": data.get("current_price"),
                "action": result["action"],
                "confidence": result["confidence"],
                "rsi": data.get("rsi_14"),
                "dma_50": data.get("dma_50"),
                "dma_200": data.get("dma_200"),
                "52w_low": data.get("52w_low"),
                "52w_high": data.get("52w_high"),
                "volume": data.get("volume"),
            })
        except Exception as e:
            logger.error(f"Error analyzing {ticker}: {e}")
            results.append({
                "ticker": ticker,
                "price": None,
                "action": "ERROR",
                "confidence": 0,
                "rsi": None,
                "dma_50": None,
                "dma_200": None,
                "52w_low": None,
                "52w_high": None,
                "volume": None,
            })

    return results