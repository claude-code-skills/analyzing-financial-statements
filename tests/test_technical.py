"""Tests for technical module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pandas as pd
import numpy as np
from technical import TechnicalAnalyzer


def _make_hist_data(n=100, trend="up"):
    """Generate mock historical data."""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    np.random.seed(42)
    base = 50
    if trend == "up":
        close = base + np.cumsum(np.random.randn(n) * 0.5 + 0.1)
    elif trend == "down":
        close = base + np.cumsum(np.random.randn(n) * 0.5 - 0.1)
    else:
        close = base + np.random.randn(n) * 1.0

    high = close + np.abs(np.random.randn(n) * 0.5)
    low = close - np.abs(np.random.randn(n) * 0.5)
    open_ = close + np.random.randn(n) * 0.3
    volume = np.random.randint(100000, 500000, n).astype(float)

    return pd.DataFrame({
        "Date": dates,
        "Open": open_,
        "High": high,
        "Low": low,
        "Close": close,
        "Volume": volume,
    })


def _make_cn_hist_data(n=100):
    """Generate mock Chinese column name data."""
    dates = pd.date_range("2024-01-01", periods=n, freq="D")
    np.random.seed(42)
    close = 50 + np.cumsum(np.random.randn(n) * 0.5 + 0.05)

    return pd.DataFrame({
        "日期": dates,
        "开盘": close + np.random.randn(n) * 0.3,
        "收盘": close,
        "最高": close + np.abs(np.random.randn(n) * 0.5),
        "最低": close - np.abs(np.random.randn(n) * 0.5),
        "成交量": np.random.randint(100000, 500000, n).astype(float),
    })


class TestTechnicalAnalyzer:
    def test_column_normalization(self):
        df = _make_cn_hist_data()
        ta = TechnicalAnalyzer(df)
        assert "Close" in ta.df.columns
        assert "Open" in ta.df.columns
        assert "High" in ta.df.columns
        assert "Low" in ta.df.columns
        assert "Volume" in ta.df.columns

    def test_macd(self):
        df = _make_hist_data(100, "up")
        ta = TechnicalAnalyzer(df)
        result = ta.calculate_macd()
        assert "dif" in result
        assert "dea" in result
        assert "macd_hist" in result
        assert "signal" in result
        assert result["signal"] in ("golden_cross", "death_cross", "bullish", "bearish")

    def test_rsi(self):
        df = _make_hist_data(100, "up")
        ta = TechnicalAnalyzer(df)
        result = ta.calculate_rsi()
        assert "rsi" in result
        assert "status" in result
        assert 0 <= result["rsi"] <= 100

    def test_kdj(self):
        df = _make_hist_data(100, "up")
        ta = TechnicalAnalyzer(df)
        result = ta.calculate_kdj()
        assert "k" in result
        assert "d" in result
        assert "j" in result
        assert "signal" in result

    def test_bollinger(self):
        df = _make_hist_data(100, "up")
        ta = TechnicalAnalyzer(df)
        result = ta.calculate_bollinger()
        assert "upper" in result
        assert "middle" in result
        assert "lower" in result
        assert result["upper"] > result["lower"]
        assert "position" in result
        assert "squeeze" in result

    def test_obv(self):
        df = _make_hist_data(100, "up")
        ta = TechnicalAnalyzer(df)
        result = ta.calculate_obv()
        assert "obv" in result
        assert "obv_ma5" in result
        assert "trend" in result
        assert result["trend"] in ("rising", "falling")

    def test_atr(self):
        df = _make_hist_data(100, "up")
        ta = TechnicalAnalyzer(df)
        result = ta.calculate_atr()
        assert "atr" in result
        assert "atr_pct" in result
        assert result["atr"] > 0

    def test_adx(self):
        df = _make_hist_data(100, "up")
        ta = TechnicalAnalyzer(df)
        result = ta.calculate_adx()
        assert "adx" in result
        assert "plus_di" in result
        assert "minus_di" in result
        assert "strength" in result
        assert "direction" in result

    def test_ma_system(self):
        df = _make_hist_data(100, "up")
        ta = TechnicalAnalyzer(df)
        result = ta.get_ma_system()
        assert "ma5" in result
        assert "ma10" in result
        assert "ma20" in result
        assert "ma60" in result
        assert "trend" in result
        assert result["trend"] in ("bullish", "bearish", "mixed")

    def test_volume_price_analysis(self):
        df = _make_hist_data(100, "up")
        ta = TechnicalAnalyzer(df)
        result = ta.volume_price_analysis()
        assert "signal" in result
        assert "price_change_5d" in result
        assert "vol_change_5d" in result

    def test_insufficient_data_volume_price(self):
        df = _make_hist_data(5)
        ta = TechnicalAnalyzer(df)
        result = ta.volume_price_analysis()
        assert result["signal"] == "insufficient_data"

    def test_analyze_comprehensive(self):
        df = _make_hist_data(100, "up")
        ta = TechnicalAnalyzer(df)
        result = ta.analyze()
        assert "macd" in result
        assert "rsi" in result
        assert "kdj" in result
        assert "bollinger" in result
        assert "obv" in result
        assert "atr" in result
        assert "adx" in result
        assert "cci" in result
        assert "mfi" in result
        assert "ma_system" in result
        assert "volume_price" in result
        assert "timing_signal" in result
        assert "confidence" in result
        assert result["timing_signal"] in (
            "strong_buy", "buy", "hold", "sell", "strong_sell"
        )
        assert 0 <= result["confidence"] <= 100
