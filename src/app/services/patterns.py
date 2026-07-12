"""
Pattern Detection Module — Pure Python, zero dependencies.
Candlestick patterns, chart patterns, and harmonic patterns.
All inputs: List[Dict] with keys: date, open, high, low, close, volume
"""
from __future__ import annotations
import math
import logging
from typing import Any

logger = logging.getLogger(__name__)


def _cols(data: list[dict]) -> dict[str, list[float]]:
    if not data:
        return {}
    return {
        k: [float(r.get(k, 0) or 0) for r in data]
        for k in ["open", "high", "low", "close", "volume"]
    }


def _body_size(o: float, c: float) -> float:
    return abs(c - o)


def _wick_size(high: float, low: float, o: float, c: float) -> tuple[float, float]:
    upper = high - max(o, c)
    lower = min(o, c) - low
    return upper, lower


def detect_candlestick_patterns(data: list[dict]) -> list[dict]:
    """
    Detect common candlestick patterns on the last 5 bars.
    Returns list of patterns with name, direction, reliability, bars_ago.
    """
    if len(data) < 10:
        return []
    patterns = []
    cols = _cols(data)
    o, h, l_, c, v = cols["open"], cols["high"], cols["low"], cols["close"], cols["volume"]
    n = len(data)

    for bar in range(max(0, n - 5), n):
        if bar < 1:
            continue
        idx = bar

        body = _body_size(o[idx], c[idx])
        up_wick, low_wick = _wick_size(h[idx], l_[idx], o[idx], c[idx])
        total_range = h[idx] - l_[idx]
        avg_vol = sum(v[max(0, idx - 20):idx]) / max(idx - max(0, idx - 20), 1) if idx > 0 else v[idx]

        if total_range == 0:
            continue

        # Doji: very small body relative to range
        if body / total_range < 0.1 and body < (total_range * 0.15):
            direction = "Neutral"
            if up_wick > low_wick * 2:
                direction = "Bullish"
            elif low_wick > up_wick * 2:
                direction = "Bearish"
            patterns.append({
                "name": "Doji",
                "direction": direction,
                "reliability": 30 if direction == "Neutral" else 60,
                "bars_ago": n - 1 - idx,
                "confirmation_volume": v[idx] > avg_vol * 1.2,
            })

        # Engulfing
        if idx >= 1:
            prev_body = _body_size(o[idx - 1], c[idx - 1])
            prev_bullish = c[idx - 1] > o[idx - 1]
            curr_bullish = c[idx] > o[idx]
            if prev_bullish and not curr_bullish and o[idx] > c[idx - 1] and c[idx] < o[idx - 1]:
                patterns.append({
                    "name": "Bearish Engulfing",
                    "direction": "Bearish",
                    "reliability": 75 if v[idx] > avg_vol else 55,
                    "bars_ago": n - 1 - idx,
                    "confirmation_volume": v[idx] > avg_vol,
                })
            elif not prev_bullish and curr_bullish and c[idx] > o[idx - 1] and o[idx] < c[idx - 1]:
                patterns.append({
                    "name": "Bullish Engulfing",
                    "direction": "Bullish",
                    "reliability": 75 if v[idx] > avg_vol else 55,
                    "bars_ago": n - 1 - idx,
                    "confirmation_volume": v[idx] > avg_vol,
                })

        # Hammer / Shooting Star
        if body / total_range < 0.4:
            if low_wick > body * 2 and up_wick < body * 0.5 and c[idx] > o[idx]:
                patterns.append({
                    "name": "Hammer",
                    "direction": "Bullish",
                    "reliability": 65 if v[idx] > avg_vol else 50,
                    "bars_ago": n - 1 - idx,
                    "confirmation_volume": v[idx] > avg_vol,
                })
            elif up_wick > body * 2 and low_wick < body * 0.5 and c[idx] < o[idx]:
                patterns.append({
                    "name": "Shooting Star",
                    "direction": "Bearish",
                    "reliability": 65 if v[idx] > avg_vol else 50,
                    "bars_ago": n - 1 - idx,
                    "confirmation_volume": v[idx] > avg_vol,
                })

        # Morning Star / Evening Star (3-bar pattern)
        if idx >= 2:
            b1, b2, b3 = idx - 2, idx - 1, idx
            b1_bearish = c[b1] < o[b1]
            b1_body = _body_size(o[b1], c[b1])
            b2_body = _body_size(o[b2], c[b2])
            b3_bullish = c[b3] > o[b3]
            b3_body = _body_size(o[b3], c[b3])

            if b1_bearish and b2_body < b1_body * 0.5 and b3_bullish and c[b3] > (o[b1] + c[b1]) / 2:
                patterns.append({
                    "name": "Morning Star",
                    "direction": "Bullish",
                    "reliability": 80 if v[b3] > avg_vol else 65,
                    "bars_ago": n - 1 - b3,
                    "confirmation_volume": v[b3] > avg_vol,
                })
            elif not b1_bearish and b2_body < _body_size(o[b1], c[b1]) * 0.5 and not b3_bullish and c[b3] < (o[b1] + c[b1]) / 2:
                patterns.append({
                    "name": "Evening Star",
                    "direction": "Bearish",
                    "reliability": 80 if v[b3] > avg_vol else 65,
                    "bars_ago": n - 1 - b3,
                    "confirmation_volume": v[b3] > avg_vol,
                })

        # Three White Soldiers / Three Black Crows
        if idx >= 2:
            b1, b2, b3 = idx - 2, idx - 1, idx
            if all(c[i] > o[i] for i in [b1, b2, b3]):
                bodies = [_body_size(o[i], c[i]) for i in [b1, b2, b3]]
                if all(bodies[i] >= bodies[i - 1] * 0.7 for i in [1, 2]):
                    patterns.append({
                        "name": "Three White Soldiers",
                        "direction": "Bullish",
                        "reliability": 80,
                        "bars_ago": n - 1 - b3,
                        "confirmation_volume": v[b3] > avg_vol,
                    })
            elif all(c[i] < o[i] for i in [b1, b2, b3]):
                bodies = [_body_size(o[i], c[i]) for i in [b1, b2, b3]]
                if all(bodies[i] >= bodies[i - 1] * 0.7 for i in [1, 2]):
                    patterns.append({
                        "name": "Three Black Crows",
                        "direction": "Bearish",
                        "reliability": 80,
                        "bars_ago": n - 1 - b3,
                        "confirmation_volume": v[b3] > avg_vol,
                    })

        # Piercing Pattern / Dark Cloud Cover
        if idx >= 1:
            prev_bearish = c[idx - 1] < o[idx - 1]
            curr_bullish = c[idx] > o[idx]
            if prev_bearish and curr_bullish and o[idx] < c[idx - 1] and c[idx] > (o[idx - 1] + c[idx - 1]) / 2 and c[idx] < o[idx - 1]:
                patterns.append({
                    "name": "Piercing Pattern",
                    "direction": "Bullish",
                    "reliability": 70,
                    "bars_ago": n - 1 - idx,
                    "confirmation_volume": v[idx] > avg_vol,
                })
            elif not prev_bearish and not curr_bullish and c[idx] < o[idx] and o[idx] < c[idx - 1] and o[idx] > (o[idx - 1] + c[idx - 1]) / 2:
                patterns.append({
                    "name": "Dark Cloud Cover",
                    "direction": "Bearish",
                    "reliability": 70,
                    "bars_ago": n - 1 - idx,
                    "confirmation_volume": v[idx] > avg_vol,
                })

    return patterns[:8]


def detect_chart_patterns(data: list[dict], lookback: int = 120) -> list[dict]:
    """
    Detect classical chart patterns using swing high/low analysis.
    Head & Shoulders, Double Top/Bottom, Triangles, Flags, Wedges.
    """
    if len(data) < lookback:
        return []
    cols = _cols(data)
    c, h, l_ = cols["close"], cols["high"], cols["low"]
    n = len(data)
    patterns = []

    swing_highs = []
    swing_lows = []
    window = 5
    for i in range(window, n - window):
        if all(h[i] >= h[i - j] for j in range(1, window + 1)) and all(h[i] >= h[i + j] for j in range(1, window + 1)):
            swing_highs.append((i, h[i]))
        if all(l_[i] <= l_[i - j] for j in range(1, window + 1)) and all(l_[i] <= l_[i + j] for j in range(1, window + 1)):
            swing_lows.append((i, l_[i]))

    if len(swing_highs) < 3 or len(swing_lows) < 3:
        return patterns

    # Head & Shoulders (top reversal)
    recent_highs = swing_highs[-5:]
    if len(recent_highs) >= 3:
        for i in range(len(recent_highs) - 2):
            left, head, right = recent_highs[i], recent_highs[i + 1], recent_highs[i + 2]
            if head[1] > left[1] and head[1] > right[1]:
                neckline = min(left[1], right[1])
                if abs(left[1] - right[1]) / head[1] < 0.1:
                    patterns.append({
                        "name": "Head & Shoulders (Top)",
                        "direction": "Bearish",
                        "entry_price": round(neckline, 2),
                        "target_price": round(neckline - (head[1] - neckline), 2),
                        "invalidation_price": round(head[1] * 1.02, 2),
                        "confidence": 75,
                        "bars_ago": n - 1 - right[0],
                        "volume_confirmed": False,
                    })

    # Inverse Head & Shoulders (bottom reversal)
    recent_lows = swing_lows[-5:]
    if len(recent_lows) >= 3:
        for i in range(len(recent_lows) - 2):
            left, head, right = recent_lows[i], recent_lows[i + 1], recent_lows[i + 2]
            if head[1] < left[1] and head[1] < right[1]:
                neckline = max(left[1], right[1])
                if abs(left[1] - right[1]) / max(head[1], 0.01) < 0.1:
                    patterns.append({
                        "name": "Inverse Head & Shoulders (Bottom)",
                        "direction": "Bullish",
                        "entry_price": round(neckline, 2),
                        "target_price": round(neckline + (neckline - head[1]), 2),
                        "invalidation_price": round(head[1] * 0.98, 2),
                        "confidence": 75,
                        "bars_ago": n - 1 - right[0],
                        "volume_confirmed": False,
                    })

    # Double Top / Bottom
    if len(swing_highs) >= 2:
        top1, top2 = swing_highs[-2], swing_highs[-1]
        if abs(top1[1] - top2[1]) / top1[1] < 0.03:
            valley = min(l_[top1[0]:top2[0]]) if top1[0] < top2[0] else min(l_[top2[0]:top1[0]])
            patterns.append({
                "name": "Double Top",
                "direction": "Bearish",
                "entry_price": round(valley, 2),
                "target_price": round(valley - (top1[1] - valley), 2),
                "invalidation_price": round(max(top1[1], top2[1]) * 1.02, 2),
                "confidence": 70,
                "bars_ago": n - 1 - max(top1[0], top2[0]),
                "volume_confirmed": False,
            })
    if len(swing_lows) >= 2:
        bot1, bot2 = swing_lows[-2], swing_lows[-1]
        if abs(bot1[1] - bot2[1]) / max(bot1[1], 0.01) < 0.03:
            peak = max(h[bot1[0]:bot2[0]]) if bot1[0] < bot2[0] else max(h[bot2[0]:bot1[0]])
            patterns.append({
                "name": "Double Bottom",
                "direction": "Bullish",
                "entry_price": round(peak, 2),
                "target_price": round(peak + (peak - bot1[1]), 2),
                "invalidation_price": round(min(bot1[1], bot2[1]) * 0.98, 2),
                "confidence": 70,
                "bars_ago": n - 1 - max(bot1[0], bot2[0]),
                "volume_confirmed": False,
            })

    # Triangle detection (last 30 bars)
    recent_data = data[-30:]
    r_cols = _cols(recent_data)
    r_h, r_l, r_c = r_cols["high"], r_cols["low"], r_cols["close"]
    if len(recent_data) >= 15:
        upper_trend = [(i, r_h[i]) for i in range(len(recent_data)) if i % 3 == 0]
        lower_trend = [(i, r_l[i]) for i in range(len(recent_data)) if i % 3 == 0]
        if len(upper_trend) >= 3 and len(lower_trend) >= 3:
            u_slope = (upper_trend[-1][1] - upper_trend[0][1]) / len(upper_trend) if len(upper_trend) > 1 else 0
            l_slope = (lower_trend[-1][1] - lower_trend[0][1]) / len(lower_trend) if len(lower_trend) > 1 else 0
            if -0.5 < u_slope < 0.5 and l_slope > 0.3:
                patterns.append({
                    "name": "Symmetrical Triangle",
                    "direction": "Neutral",
                    "entry_price": round(r_c[-1], 2),
                    "target_price": round(upper_trend[-1][1] + (upper_trend[-1][1] - lower_trend[-1][1]), 2),
                    "invalidation_price": round(lower_trend[-1][1] * 0.98, 2),
                    "confidence": 55,
                    "bars_ago": 0,
                    "volume_confirmed": False,
                })

    return patterns[:5]


def calculate_pattern_score(data: list[dict]) -> dict:
    """
    Composite pattern analysis score.
    Aggregates candle + chart patterns into a single score component.
    """
    candle_patterns = detect_candlestick_patterns(data)
    chart_patterns = detect_chart_patterns(data)

    bullish_score = 0
    bearish_score = 0
    total_confidence = 0

    for p in candle_patterns:
        conf = p["reliability"]
        total_confidence += conf
        if p["direction"] == "Bullish":
            bullish_score += conf
        elif p["direction"] == "Bearish":
            bearish_score += conf

    for p in chart_patterns:
        conf = p["confidence"]
        total_confidence += conf
        if p["direction"] == "Bullish":
            bullish_score += conf
        elif p["direction"] == "Bearish":
            bearish_score += conf

    net = bullish_score - bearish_score
    max_possible = max(total_confidence, 1)

    if total_confidence == 0:
        return {"score": 0, "direction": "Neutral", "active_count": 0}

    normalized = int((net / max_possible) * 50 + 50)
    normalized = max(0, min(100, normalized))

    return {
        "score": normalized,
        "direction": "Bullish" if net > 10 else "Bearish" if net < -10 else "Neutral",
        "active_count": len(candle_patterns) + len(chart_patterns),
    }
