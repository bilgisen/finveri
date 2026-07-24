import sys
sys.path.insert(0, "src")

import pytest
from app.services.signal_classifier import (
    classify_rsi, classify_macd, classify_stoch, classify_mfi,
    classify_cci, classify_williams_r, classify_obv, classify_adx,
    classify_roc, classify_supertrend, get_all_signals,
)


class TestRSISignal:
    def test_oversold(self):
        assert classify_rsi(25) == "Al"

    def test_overbought(self):
        assert classify_rsi(75) == "Sat"

    def test_neutral(self):
        assert classify_rsi(50) == "Nötr"
        assert classify_rsi(40) == "Nötr"
        assert classify_rsi(60) == "Nötr"

    def test_boundaries(self):
        assert classify_rsi(30) == "Nötr"
        assert classify_rsi(70) == "Nötr"
        assert classify_rsi(29.9) == "Al"
        assert classify_rsi(70.1) == "Sat"


class TestMACDSignal:
    def test_bullish(self):
        assert classify_macd(0.5) == "Al"

    def test_bearish(self):
        assert classify_macd(-0.5) == "Sat"

    def test_neutral(self):
        assert classify_macd(0) == "Nötr"


class TestStochSignal:
    def test_oversold(self):
        assert classify_stoch(15) == "Al"

    def test_overbought(self):
        assert classify_stoch(85) == "Sat"

    def test_neutral(self):
        assert classify_stoch(50) == "Nötr"


class TestMFISignal:
    def test_oversold(self):
        assert classify_mfi(15) == "Al"

    def test_overbought(self):
        assert classify_mfi(85) == "Sat"

    def test_neutral(self):
        assert classify_mfi(50) == "Nötr"


class TestCCISignal:
    def test_oversold(self):
        assert classify_cci(-150) == "Al"

    def test_overbought(self):
        assert classify_cci(150) == "Sat"

    def test_neutral(self):
        assert classify_cci(0) == "Nötr"
        assert classify_cci(50) == "Nötr"
        assert classify_cci(-50) == "Nötr"


class TestWilliamsRSignal:
    def test_oversold(self):
        assert classify_williams_r(-90) == "Al"

    def test_overbought(self):
        assert classify_williams_r(-10) == "Sat"

    def test_neutral(self):
        assert classify_williams_r(-50) == "Nötr"


class TestOBVSignal:
    def test_rising(self):
        assert classify_obv("Rising") == "Al"

    def test_falling(self):
        assert classify_obv("Falling") == "Sat"

    def test_neutral(self):
        assert classify_obv("Neutral") == "Nötr"


class TestADXSignal:
    def test_strong_trend_bullish(self):
        assert classify_adx(30, plus_di=25, minus_di=15) == "Al"

    def test_strong_trend_bearish(self):
        assert classify_adx(30, plus_di=15, minus_di=25) == "Sat"

    def test_weak_trend(self):
        assert classify_adx(20) == "Nötr"

    def test_no_di(self):
        assert classify_adx(30) == "Nötr"


class TestROCSignal:
    def test_strong_up(self):
        assert classify_roc(10) == "Al"

    def test_strong_down(self):
        assert classify_roc(-10) == "Sat"

    def test_neutral(self):
        assert classify_roc(0) == "Nötr"
        assert classify_roc(4) == "Nötr"
        assert classify_roc(-4) == "Nötr"


class TestSupertrendSignal:
    def test_up(self):
        assert classify_supertrend("up") == "Al"

    def test_down(self):
        assert classify_supertrend("down") == "Sat"

    def test_neutral(self):
        assert classify_supertrend("flat") == "Nötr"


class TestGetAllSignals:
    def test_full_set(self):
        signals = get_all_signals(
            rsi=25, macd_histogram=0.5, stoch_k=15, stoch_d=20,
            mfi=85, cci=150, williams_r=-10, obv_trend="Falling",
            adx=30, plus_di=25, minus_di=15, roc=10,
            supertrend_direction="up",
        )
        assert len(signals) == 10
        assert signals["rsi"]["signal"] == "Al"
        assert signals["macd"]["signal"] == "Al"
        assert signals["stoch"]["signal"] == "Al"
        assert signals["mfi"]["signal"] == "Sat"
        assert signals["cci"]["signal"] == "Sat"
        assert signals["williams_r"]["signal"] == "Sat"
        assert signals["obv"]["signal"] == "Sat"
        assert signals["adx"]["signal"] == "Al"
        assert signals["roc"]["signal"] == "Al"
        assert signals["supertrend"]["signal"] == "Al"

    def test_partial(self):
        signals = get_all_signals(rsi=50, macd_histogram=0.1)
        assert len(signals) == 2
        assert signals["rsi"]["signal"] == "Nötr"
        assert signals["macd"]["signal"] == "Al"

    def test_empty(self):
        signals = get_all_signals()
        assert signals == {}
