import sys
sys.path.insert(0, "src")

import pytest
import math
from app.services.pivot_points import (
    classic_pivot, fibonacci_pivot, camarilla_pivot,
    fibonacci_retracement, compute_all_pivots,
)


class TestClassicPivot:
    def test_known_values(self):
        r = classic_pivot(110, 90, 100)
        assert r["pivot"] == pytest.approx(100.0, rel=1e-2)
        assert r["r1"] == pytest.approx(110.0, rel=1e-2)
        assert r["s1"] == pytest.approx(90.0, rel=1e-2)

    def test_all_positive(self):
        r = classic_pivot(150, 100, 120)
        pivot = (150 + 100 + 120) / 3.0
        assert r["pivot"] == pytest.approx(pivot, abs=0.01)
        assert r["r1"] == pytest.approx(2 * pivot - 100, abs=0.01)
        assert r["s1"] == pytest.approx(2 * pivot - 150, abs=0.01)
        assert r["r2"] == pytest.approx(pivot + 50, abs=0.01)
        assert r["s2"] == pytest.approx(pivot - 50, abs=0.01)
        assert r["r3"] == pytest.approx(150 + 2 * (pivot - 100), abs=0.01)
        assert r["s3"] == pytest.approx(100 - 2 * (150 - pivot), abs=0.01)
    def test_structure(self):
        r = fibonacci_pivot(110, 90, 100)
        assert "pivot" in r
        assert "r1" in r and "r2" in r and "r3" in r
        assert "s1" in r and "s2" in r and "s3" in r

    def test_symmetry(self):
        r = fibonacci_pivot(110, 90, 100)
        assert r["r1"] > r["pivot"] > r["s1"]
        assert r["r3"] > r["r2"] > r["r1"]
        assert r["s1"] > r["s2"] > r["s3"]


class TestCamarillaPivot:
    def test_structure(self):
        r = camarilla_pivot(110, 90, 100)
        for k in ["r1", "r2", "r3", "r4", "s1", "s2", "s3", "s4"]:
            assert k in r

    def test_ordering(self):
        r = camarilla_pivot(110, 90, 100)
        assert r["r4"] > r["r3"] > r["r2"] > r["r1"]
        assert r["s1"] > r["s2"] > r["s3"] > r["s4"]

    def test_symmetric(self):
        r = camarilla_pivot(110, 90, 100)
        assert r["r1"] == pytest.approx(100 + 20 * 1.1 / 12, abs=0.01)
        assert r["s1"] == pytest.approx(100 - 20 * 1.1 / 12, abs=0.01)


class TestFibonacciRetracement:
    def test_uptrend(self):
        highs = [100, 105, 110, 108, 115, 112, 118]
        lows = [95, 98, 102, 100, 108, 105, 110]
        closes = [98, 103, 108, 105, 112, 110, 115]
        r = fibonacci_retracement(highs, lows, closes, lookback=7)
        assert r["swing_high"] == 118
        assert r["swing_low"] == 95
        diff = 118 - 95
        assert r["direction"] == "uptrend"
        assert r["levels"]["0.0"] == pytest.approx(118, abs=0.01)
        assert r["levels"]["0.618"] == pytest.approx(118 - 0.618 * diff, abs=0.01)
        assert r["levels"]["1.0"] == pytest.approx(95, abs=0.01)

    def test_downtrend(self):
        highs = [118, 115, 112, 108, 105, 100, 98]
        lows = [110, 108, 105, 100, 98, 95, 92]
        closes = [115, 110, 108, 102, 100, 97, 95]
        r = fibonacci_retracement(highs, lows, closes, lookback=7)
        diff = 118 - 92
        assert r["direction"] == "downtrend"
        assert r["levels"]["0.0"] == pytest.approx(92, abs=0.01)
        assert r["levels"]["0.618"] == pytest.approx(92 + 0.618 * diff, abs=0.01)
        assert r["levels"]["1.0"] == pytest.approx(118, abs=0.01)

    def test_short_data(self):
        r = fibonacci_retracement([100], [90], [95])
        assert "swing_high" in r

    def test_flat(self):
        highs = [100] * 10
        lows = [100] * 10
        closes = [100] * 10
        r = fibonacci_retracement(highs, lows, closes)
        assert r["direction"] == "flat"
        assert r["levels"] == {}


class TestComputeAllPivots:
    def test_all_types(self):
        highs = [100 + i * 0.5 + math.sin(i * 0.1) * 2 for i in range(100)]
        lows = [v - 3 for v in highs]
        closes = [v - 1 for v in highs]
        r = compute_all_pivots(highs, lows, closes)
        assert "classic" in r
        assert "fibonacci" in r
        assert "camarilla" in r
        assert "fib_retracement" in r

    def test_empty(self):
        r = compute_all_pivots([], [], [])
        assert "error" in r
