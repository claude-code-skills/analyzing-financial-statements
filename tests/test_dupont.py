"""Tests for dupont module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from dupont import DuPontAnalyzer


class TestDuPont3:
    def setup_method(self):
        self.analyzer = DuPontAnalyzer()

    def test_basic_decomposition(self):
        result = self.analyzer.dupont_3(
            net_income=100, revenue=1000, total_assets=2000, equity=800
        )
        assert "roe" in result
        assert "net_profit_margin" in result
        assert "asset_turnover" in result
        assert "equity_multiplier" in result
        # npm = 100/1000*100 = 10%
        assert result["net_profit_margin"] == 10.0
        # at = 1000/2000 = 0.5
        assert result["asset_turnover"] == 0.5
        # em = 2000/800 = 2.5
        assert result["equity_multiplier"] == 2.5

    def test_roe_consistency(self):
        result = self.analyzer.dupont_3(
            net_income=100, revenue=1000, total_assets=2000, equity=800
        )
        expected_roe = result["net_profit_margin"] / 100 * result["asset_turnover"] * result["equity_multiplier"] * 100
        assert abs(result["roe"] - round(expected_roe, 2)) < 0.1

    def test_zero_revenue(self):
        result = self.analyzer.dupont_3(
            net_income=100, revenue=0, total_assets=2000, equity=800
        )
        assert result["net_profit_margin"] == 0

    def test_zero_equity(self):
        result = self.analyzer.dupont_3(
            net_income=100, revenue=1000, total_assets=2000, equity=0
        )
        assert result["equity_multiplier"] == 0


class TestDuPont5:
    def setup_method(self):
        self.analyzer = DuPontAnalyzer()

    def test_basic_decomposition(self):
        result = self.analyzer.dupont_5(
            net_income=80, ebt=100, ebit=130,
            revenue=1000, total_assets=2000, equity=800
        )
        assert "roe" in result
        assert "tax_burden" in result
        assert "interest_burden" in result
        assert "operating_margin" in result
        assert "asset_turnover" in result
        assert "equity_multiplier" in result
        # tax_burden = 80/100 = 0.8
        assert result["tax_burden"] == 0.8
        # interest_burden = 100/130 = 0.7692
        assert abs(result["interest_burden"] - 0.7692) < 0.001

    def test_zero_ebit(self):
        result = self.analyzer.dupont_5(
            net_income=80, ebt=100, ebit=0,
            revenue=1000, total_assets=2000, equity=800
        )
        assert result["interest_burden"] == 0


class TestAnalyzeTrend:
    def setup_method(self):
        self.analyzer = DuPontAnalyzer()

    def _make_period(self, date, ni, rev, ta, equity, ebt=0, ebit=0):
        return {
            "income_statement": {
                "date": date, "net_income": ni, "revenue": rev,
                "total_profit": ebt, "operating_profit": ebit,
            },
            "balance_sheet": {
                "date": date, "total_assets": ta, "shareholders_equity": equity,
            },
        }

    def test_multi_period(self):
        data = [
            self._make_period("2024", 100, 1000, 2000, 800, ebt=120, ebit=150),
            self._make_period("2023", 80, 900, 1800, 750, ebt=95, ebit=120),
            self._make_period("2022", 70, 800, 1700, 700, ebt=85, ebit=100),
        ]
        result = self.analyzer.analyze_trend(data)
        assert "latest" in result
        assert "periods" in result
        assert "roe_trend" in result
        assert "driver" in result
        assert "quality" in result
        assert len(result["periods"]) == 3
        assert len(result["roe_trend"]) == 3

    def test_insufficient_data(self):
        result = self.analyzer.analyze_trend([])
        assert "error" in result

    def test_quality_rating(self):
        # High ROE, high margin, low leverage
        data = [
            self._make_period("2024", 200, 1000, 1500, 1200, ebt=250, ebit=300),
            self._make_period("2023", 180, 900, 1400, 1100, ebt=220, ebit=270),
        ]
        result = self.analyzer.analyze_trend(data)
        quality = result["quality"]
        assert "rating" in quality
        assert "score" in quality
        assert "reasons" in quality
        # High ROE should give high quality
        assert quality["rating"] in ("优质", "良好")

    def test_driver_identification(self):
        data = [
            self._make_period("2024", 100, 1000, 2000, 800, ebt=120, ebit=150),
        ]
        result = self.analyzer.analyze_trend(data)
        assert "main_driver" in result["driver"]
        assert "explanation" in result["driver"]
        assert "factors" in result["driver"]
