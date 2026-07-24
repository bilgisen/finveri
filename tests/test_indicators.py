import sys
import math
sys.path.insert(0, "src")

import pytest
from app.services.indicators import (
    sma, ema, rsi, macd, bollinger_bands, atr,
    stochastic, adx, obv, mfi, supertrend, psar,
    cci, williams_r, roc, historical_volatility,
    compute_all, compute_selected,
)


def _trend_data(n=300) -> list[float]:
    return [100.0 + i * 0.5 + math.sin(i * 0.1) * 2 for i in range(n)]


def _cols_from_close(closes: list[float]) -> dict:
    return {
        "close": closes,
        "high": [c + 2.0 for c in closes],
        "low": [c - 2.0 for c in closes],
        "volume": [1_000_000.0 + i * 1000.0 for i in range(len(closes))],
    }


class TestSMA:
    def test_basic(self):
        c = _trend_data(50)
        result = sma(c, 20)
        assert len(result) == 50
        assert result[0] is None
        assert result[19] is not None
        assert result[19] > 0

    def test_short_data(self):
        result = sma([10, 20], 5)
        assert result == [None, None]

    def test_known_values(self):
        c = [1, 2, 3, 4, 5]
        result = sma(c, 3)
        assert result[2] == pytest.approx(2.0, rel=1e-4)
        assert result[3] == pytest.approx(3.0, rel=1e-4)
        assert result[4] == pytest.approx(4.0, rel=1e-4)


class TestEMA:
    def test_basic(self):
        c = _trend_data(50)
        result = ema(c, 20)
        assert len(result) == 50
        assert result[19] is not None
        assert result[18] is None

    def test_ema_vs_sma_convergence(self):
        c = [100.0] * 30
        s = sma(c, 10)
        e = ema(c, 10)
        assert e[-1] == pytest.approx(s[-1], rel=1e-2)

    def test_short_data(self):
        result = ema([10], 5)
        assert result == [10.0]


class TestRSI:
    def test_basic(self):
        c = _trend_data(100)
        result = rsi(c, 14)
        assert len(result) == 100
        assert all(r is None or 0 <= r <= 100 for r in result)

    def test_all_up(self):
        c = list(range(50, 100))
        result = rsi(c, 14)
        assert result[-1] is not None
        assert result[-1] > 80

    def test_all_down(self):
        c = list(range(100, 50, -1))
        result = rsi(c, 14)
        assert result[-1] is not None
        assert result[-1] < 20


class TestMACD:
    def test_basic(self):
        c = _trend_data(100)
        result = macd(c)
        assert "macd" in result
        assert "signal" in result
        assert "histogram" in result
        m = result["macd"]
        s = result["signal"]
        h = result["histogram"]
        assert len(m) == len(c)
        assert len(s) == len(c)
        assert len(h) == len(c)
        for i in range(len(c)):
            if m[i] is not None and s[i] is not None:
                assert h[i] == pytest.approx(m[i] - s[i], rel=1e-4)


class TestBollingerBands:
    def test_basic(self):
        c = _trend_data(50)
        result = bollinger_bands(c, 20)
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result
        for i in range(20, len(c)):
            assert result["upper"][i] >= result["middle"][i] >= result["lower"][i]

    def test_constant_values(self):
        c = [100.0] * 50
        result = bollinger_bands(c, 20)
        for i in range(20, len(c)):
            assert result["upper"][i] == pytest.approx(100.0, rel=1e-2)
            assert result["lower"][i] == pytest.approx(100.0, rel=1e-2)


class TestATR:
    def test_basic(self):
        h = [110, 112, 111, 115, 113]
        l_ = [90, 92, 91, 95, 93]
        c = [105, 108, 106, 110, 109]
        result = atr(h, l_, c, 14)
        assert len(result) == 5
        # Data too short for period=14
        assert result[-1] is None

    def with_enough_data(self):
        c = _trend_data(100)
        h = [v + 3 for v in c]
        l_ = [v - 3 for v in c]
        result = atr(h, l_, c, 14)
        assert len(result) == 100
        assert result[14] is not None
        assert result[-1] is not None
        assert result[-1] > 0


class TestStochastic:
    def test_basic(self):
        c = _trend_data(100)
        h = [v + 3 for v in c]
        l_ = [v - 3 for v in c]
        result = stochastic(h, l_, c)
        assert "k" in result
        assert "d" in result
        assert len(result["k"]) == 100
        assert len(result["d"]) == 100
        for i in range(17, 100):
            assert result["k"][i] is not None
            assert 0 <= result["k"][i] <= 100

    def test_short_data(self):
        result = stochastic([1, 2, 3], [1, 2, 3], [1, 2, 3])
        assert all(v is None for v in result["k"])

    def test_slow_stochastic_smoothing(self):
        c = [100 + i * 0.3 for i in range(50)]
        h = [v + 2 for v in c]
        l_ = [v - 2 for v in c]
        result = stochastic(h, l_, c)
        k = [v for v in result["k"] if v is not None]
        d = [v for v in result["d"] if v is not None]
        assert len(k) >= 30
        assert len(d) >= 28

    def test_k_d(self):
        high = [10, 12, 11, 14, 13, 15, 16, 14, 15, 17, 16, 18, 19, 17, 20, 18, 21, 19]
        low  = [8,  9,  9, 10, 11, 12, 13, 11, 12, 14, 13, 15, 16, 14, 17, 15, 18, 16]
        close = [9, 11, 10, 13, 12, 14, 15, 13, 14, 16, 15, 17, 18, 16, 19, 17, 20, 18]
        result = stochastic(high, low, close, k_period=14, d_period=3)
        assert result["k"][16] is not None
        assert result["d"][17] is not None


class TestADX:
    def test_basic(self):
        h = _trend_data(100)
        l_ = [v - 3 for v in h]
        c = [v - 1 for v in h]
        result = adx(h, l_, c, 14)
        assert "adx" in result
        assert "plus_di" in result
        assert "minus_di" in result
        assert result["adx"][27] is not None, "ADX needs 2*period bars (index 27 for period=14)"
        assert 0 <= result["adx"][27] <= 100

    def test_short_data(self):
        result = adx([1, 2, 3], [1, 2, 3], [1, 2, 3])
        assert all(v is None for v in result["adx"])

    def test_adx_range(self):
        h = _trend_data(100)
        l_ = [v - 3 for v in h]
        c = [v - 1 for v in h]
        result = adx(h, l_, c, 14)
        for i in range(14, 100):
            if result["adx"][i] is not None:
                assert 0 <= result["adx"][i] <= 100


class TestOBV:
    def test_uptrend(self):
        c = list(range(1, 101))
        v = [1000.0] * 100
        result = obv(c, v)
        assert result[-1] > result[0]

    def test_downtrend(self):
        c = list(range(100, 0, -1))
        v = [1000.0] * 100
        result = obv(c, v)
        assert result[-1] < result[0]

    def test_length(self):
        result = obv([1, 2, 3], [100, 200, 300])
        assert len(result) == 3


class TestMFI:
    def test_basic(self):
        c = _trend_data(100)
        h = [v + 2 for v in c]
        l_ = [v - 2 for v in c]
        v = [1_000_000.0] * 100
        result = mfi(h, l_, c, v)
        assert len(result) == 100
        assert result[14] is not None
        assert 0 <= result[14] <= 100

    def test_short_data(self):
        result = mfi([1, 2, 3], [1, 2, 3], [1, 2, 3], [100, 200, 300])
        assert all(v is None for v in result)


class TestSupertrend:
    def test_basic(self):
        c = _trend_data(100)
        h = [v + 2 for v in c]
        l_ = [v - 2 for v in c]
        result = supertrend(h, l_, c)
        assert "supertrend" in result
        assert "trend" in result
        assert len(result["supertrend"]) == 100
        assert len(result["trend"]) == 100
        for i in range(7, 100):
            assert result["trend"][i] in (1, -1)

    def test_trend_non_none(self):
        c = [100.0] * 50
        h = [105.0] * 50
        l_ = [95.0] * 50
        result = supertrend(h, l_, c, period=7, multiplier=2.0)
        for i in range(7, 50):
            assert result["trend"][i] is not None
            assert result["supertrend"][i] is not None
        assert result["trend"][7] == 1, "Supertrend should start up"


class TestPSAR:
    def test_basic(self):
        c = _trend_data(100)
        h = [v + 2 for v in c]
        l_ = [v - 2 for v in c]
        result = psar(h, l_, c)
        assert len(result) == 100
        assert result[0] is not None
        for v in result[1:]:
            assert v is not None


class TestCCI:
    def test_basic(self):
        c = _trend_data(100)
        h = [v + 2 for v in c]
        l_ = [v - 2 for v in c]
        result = cci(h, l_, c, 20)
        assert len(result) == 100
        assert result[19] is not None
        assert result[19] != 0

    def test_short_data(self):
        result = cci([1, 2, 3], [1, 2, 3], [1, 2, 3], 20)
        assert all(v is None for v in result)

    def test_constant(self):
        c = [100.0] * 50
        h = [102.0] * 50
        l_ = [98.0] * 50
        result = cci(h, l_, c, 20)
        assert result[-1] == pytest.approx(0.0, abs=1)


class TestWilliamsR:
    def test_basic(self):
        c = _trend_data(100)
        h = [v + 2 for v in c]
        l_ = [v - 2 for v in c]
        result = williams_r(h, l_, c, 14)
        assert len(result) == 100
        assert result[13] is not None
        assert result[13] <= 0

    def test_range(self):
        c = _trend_data(100)
        h = [v + 2 for v in c]
        l_ = [v - 2 for v in c]
        result = williams_r(h, l_, c, 14)
        for i in range(14, 100):
            assert -100 <= result[i] <= 0

    def test_short_data(self):
        result = williams_r([1, 2, 3], [1, 2, 3], [1, 2, 3])
        assert all(v is None for v in result)


class TestROC:
    def test_basic(self):
        c = _trend_data(100)
        result = roc(c, 12)
        assert len(result) == 100
        assert result[12] is not None

    def test_uptrend(self):
        c = list(range(50, 150))
        result = roc(c, 12)
        assert result[-1] > 0

    def test_short_data(self):
        result = roc([1, 2, 3], 10)
        assert all(v is None for v in result)


class TestHistoricalVolatility:
    def test_basic(self):
        c = _trend_data(100)
        result = historical_volatility(c, 20)
        assert len(result) == 100
        assert result[20] is not None

    def test_short_data(self):
        result = historical_volatility([1, 2, 3], 20)
        assert all(v is None for v in result)


class TestComputeAll:
    def test_empty_data(self):
        result = compute_all([])
        assert "error" in result

    def test_full(self):
        data = []
        for i in range(300):
            base = 100 + i * 0.5 + math.sin(i * 0.1) * 2
            data.append({
                "date": f"2025-01-{i%30+1:02d}",
                "open": base - 0.5,
                "high": base + 2,
                "low": base - 2,
                "close": base,
                "volume": 1_000_000 + i * 1000,
            })
        result = compute_all(data)
        assert "error" not in result
        assert result.get("rsi") is not None
        assert result.get("atr") is not None
        m = result.get("macd", {})
        assert m.get("value") is not None
        assert result.get("cci") is not None
        assert result.get("williams_r") is not None
        assert result.get("roc") is not None
        assert result.get("historical_volatility") is not None


class TestComputeSelected:
    def test_selected(self):
        data = []
        for i in range(300):
            base = 100 + i * 0.5 + math.sin(i * 0.1) * 2
            data.append({
                "date": f"2025-01-{i%30+1:02d}",
                "open": base - 0.5,
                "high": base + 2,
                "low": base - 2,
                "close": base,
                "volume": 1_000_000 + i * 1000,
            })
        result = compute_selected(data, ["rsi", "macd", "stoch", "bbands", "cci", "williams_r", "roc"])
        assert result.get("rsi") is not None
        assert result.get("macd") is not None
        assert result.get("cci") is not None
        assert result.get("williams_r") is not None
        assert result.get("roc") is not None
