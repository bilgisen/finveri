"""
Integration test for new TA modules.
Verifies that indicators_ext, patterns, market_breadth, advanced_ta extensions work.
"""
import sys
sys.path.insert(0, "src")

import json
import math


def test_indicators_ext():
    """Test extended indicators with synthetic data."""
    from app.services.indicators_ext import (
        detect_golden_death_cross,
        detect_trend_age,
        calculate_mtf_alignment,
        calculate_volume_metrics,
        calculate_atr_pct,
        calculate_efficiency_ratio,
    )

    # Uptrend data
    closes = [100 + i * 0.5 + math.sin(i * 0.1) * 2 for i in range(300)]
    highs = [c + 2 for c in closes]
    lows = [c - 2 for c in closes]
    volumes = [1000000 + i * 1000 + int(math.sin(i * 0.05) * 200000) for i in range(300)]

    gc = detect_golden_death_cross(closes, 20, 50)
    assert isinstance(gc, dict)
    assert "has_golden_cross" in gc
    print(f"  Golden/Death Cross: {gc}")

    ta = detect_trend_age(closes)
    assert isinstance(ta, dict)
    assert "daily_direction" in ta
    print(f"  Trend Age: {ta}")

    mtf = calculate_mtf_alignment(closes)
    assert isinstance(mtf, dict)
    assert "alignment_score" in mtf
    print(f"  MTF Alignment: {mtf['alignment_label']} ({mtf['alignment_score']})")

    vm = calculate_volume_metrics(closes, volumes)
    assert isinstance(vm, dict)
    assert "obv_trend" in vm
    print(f"  Volume Metrics: RV={vm['relative_volume']}, Conf={vm['volume_confirmation']}")

    atr_val = 1.5
    atr_p = calculate_atr_pct(closes, [None] * 290 + [atr_val])
    assert atr_p is not None
    print(f"  ATR%: {atr_p}")

    er = calculate_efficiency_ratio(closes)
    assert isinstance(er, float)
    print(f"  Efficiency Ratio: {er}")

    rs_data = {
        "ticker": [100 + i * 0.5 for i in range(200)],
        "index": [5000 + i * 2 for i in range(200)],
    }
    from app.services.indicators_ext import calculate_relative_strength
    rs = calculate_relative_strength(closes, [5000 + i * 2 for i in range(300)])
    assert isinstance(rs, dict)
    print(f"  Relative Strength: {rs.get('label')}")


def test_patterns():
    """Test pattern detection with synthetic data."""
    from app.services.patterns import (
        detect_candlestick_patterns,
        detect_chart_patterns,
        calculate_pattern_score,
    )

    # Generate candle data with a doji + engulfing at the end
    data = []
    for i in range(100):
        base = 100 + i * 0.3
        data.append({
            "date": f"2024-01-{i+1:02d}",
            "open": base,
            "high": base + 2,
            "low": base - 2,
            "close": base + (1 if i % 3 != 0 else -1),
            "volume": 1000000,
        })

    # Add a bullish engulfing at the end
    data[-3] = {"date": "2024-04-08", "open": 115, "high": 116, "low": 113, "close": 114, "volume": 1000000}
    data[-2] = {"date": "2024-04-09", "open": 116, "high": 116.5, "low": 114.5, "close": 115.5, "volume": 1000000}
    data[-1] = {"date": "2024-04-10", "open": 113, "high": 118, "low": 113, "close": 117, "volume": 2000000}

    candles = detect_candlestick_patterns(data)
    print(f"  Candle Patterns ({len(candles)}):")
    for p in candles:
        print(f"    - {p['name']}: {p['direction']} (rel={p['reliability']})")

    charts = detect_chart_patterns(data)
    print(f"  Chart Patterns ({len(charts)}):")
    for p in charts:
        print(f"    - {p['name']}: {p['direction']} (conf={p['confidence']})")

    score = calculate_pattern_score(data)
    assert isinstance(score, dict)
    assert "score" in score
    print(f"  Pattern Score: {score['score']} ({score['direction']}), active={score['active_count']}")


def test_market_breadth():
    """Test market breadth functions."""
    from app.services.market_breadth import (
        calculate_advance_decline,
        calculate_pct_above_ma,
        calculate_sector_performance,
    )

    tickers = [
        {"code": "THYAO", "change_pct": 2.5, "score": 75, "above_sma_50": True},
        {"code": "ASELS", "change_pct": -1.2, "score": 45, "above_sma_50": False},
        {"code": "EREGL", "change_pct": 0.8, "score": 60, "above_sma_50": True},
        {"code": "GARAN", "change_pct": -0.5, "score": 55, "above_sma_50": True},
        {"code": "SASA", "change_pct": 3.1, "score": 80, "above_sma_50": True},
    ]

    ad = calculate_advance_decline(tickers)
    print(f"  Advance/Decline: A={ad['advancing']} D={ad['declining']} Ratio={ad['ad_ratio']}")

    sectors = calculate_sector_performance({"BANKACILIK": tickers[:2], "SINAI": tickers[2:]})
    for s in sectors:
        print(f"  Sector {s['sector']}: median={s['median_score']}, return={s['mean_return']}%")


def test_advanced_ta_extensions():
    """Test new advanced_ta functions (scenarios, risk, divergence confidence)."""
    from app.services.advanced_ta import (
        generate_scenarios,
        calculate_risk_metrics,
        calculate_divergence_confidence,
        calculate_composite_score,
    )

    data = []
    for i in range(200):
        base = 100 + i * 0.3 + math.sin(i * 0.1) * 3
        data.append({
            "date": f"2024-01-{i+1:02d}",
            "open": base - 0.5,
            "high": base + 2,
            "low": base - 2,
            "close": base,
            "volume": 1000000,
        })

    sr = {
        "current_price": 150,
        "resistance_zones": [{"price": 155, "type": "Swing High", "strength": 85}],
        "support_zones": [{"price": 145, "type": "Swing Low", "strength": 85}],
        "nearest_resistance": {"price": 155, "type": "Swing High", "strength": 85},
        "nearest_support": {"price": 145, "type": "Swing Low", "strength": 85},
    }
    regime = {
        "regime": "Strong Trend",
        "trend_direction": "Bullish",
        "volatility_regime": "Normal",
        "adx": 32,
        "recommended_strategy": "Trend Following",
    }
    score = {
        "score": 70,
        "signals": [
            "✓ Above SMA 200 (Long-term Bullish)",
            "✓ Golden Cross alignment (SMA 20 > SMA 50)",
            "✓ Supertrend Bullish",
            "⊙ RSI Neutral",
            "✓ MACD Bullish",
        ],
        "confidence": "High",
        "trend_component": 35,
        "momentum_component": 20,
        "volume_component": 15,
    }

    scenarios = generate_scenarios(data, sr, regime, score)
    print(f"  Scenarios ({len(scenarios)}):")
    for s in scenarios:
        print(f"    - {s['name']}: trigger={s['trigger_price']}, target={s['target_price']}, signals={s['supporting_signal_count']}")

    risk = calculate_risk_metrics(data, regime)
    print(f"  Risk Metrics: SL={risk.get('atr_based_stop_loss')}, Vol={risk.get('volatility_classification')}")

    div_conf = calculate_divergence_confidence(data)
    print(f"  Divergence Confidence: count={div_conf['divergence_count']}, conf={div_conf['overall_confidence']}")

    comp = calculate_composite_score(data, regime)
    print(f"  Composite Score: {comp['total']} ({comp['confidence']})")
    print(f"  Components: {comp['components']}")


def test_cache_validation():
    """Test cache_validation module."""
    from app.core.cache_validation import get_ttl, get_ttl_for_cache_type, is_market_open

    ttl = get_ttl("public")
    assert isinstance(ttl, int) and ttl > 0
    print(f"  Cache TTL (public): {ttl}s")

    ttl2 = get_ttl("pool")
    assert isinstance(ttl2, int)
    print(f"  Cache TTL (pool): {ttl2}s")

    market_hours = is_market_open()
    print(f"  Market open: {market_hours}")


if __name__ == "__main__":
    print("=== Testing Indicators Ext ===")
    test_indicators_ext()

    print("\n=== Testing Patterns ===")
    test_patterns()

    print("\n=== Testing Market Breadth ===")
    test_market_breadth()

    print("\n=== Testing Advanced TA Extensions ===")
    test_advanced_ta_extensions()

    print("\n=== Testing Cache Validation ===")
    test_cache_validation()

    print("\n✅ All module tests PASSED!")
