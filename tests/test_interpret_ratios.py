"""Tests for interpret_ratios module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from interpret_ratios import RatioInterpreter, perform_comprehensive_analysis


class TestRatioInterpreter:
    def setup_method(self):
        self.interpreter = RatioInterpreter("technology")

    def test_init_with_known_industry(self):
        interp = RatioInterpreter("technology")
        assert "current_ratio" in interp.benchmarks

    def test_init_with_unknown_industry(self):
        interp = RatioInterpreter("unknown_industry")
        assert "current_ratio" in interp.benchmarks  # Falls back to general

    def test_interpret_current_ratio_excellent(self):
        result = self.interpreter.interpret_ratio("current_ratio", 3.0)
        assert result["rating"] == "Excellent"

    def test_interpret_current_ratio_poor(self):
        result = self.interpreter.interpret_ratio("current_ratio", 0.5)
        assert result["rating"] == "Poor"

    def test_interpret_debt_to_equity_excellent(self):
        result = self.interpreter.interpret_ratio("debt_to_equity", 0.2)
        assert result["rating"] == "Excellent"

    def test_interpret_debt_to_equity_poor(self):
        result = self.interpreter.interpret_ratio("debt_to_equity", 3.0)
        assert result["rating"] == "Poor"

    def test_interpret_roe(self):
        result = self.interpreter.interpret_ratio("roe", 0.3)
        assert result["rating"] == "Excellent"

    def test_interpret_pe_undervalued(self):
        result = self.interpreter.interpret_ratio("pe_ratio", 10)
        assert result["rating"] == "Potentially Undervalued"

    def test_interpret_pe_expensive(self):
        result = self.interpreter.interpret_ratio("pe_ratio", 60)
        assert result["rating"] == "Expensive"

    def test_interpret_unknown_ratio(self):
        result = self.interpreter.interpret_ratio("custom_ratio", 1.0)
        assert result["rating"] == "N/A"

    def test_interpret_negative_pe(self):
        result = self.interpreter.interpret_ratio("pe_ratio", -5)
        assert result["rating"] == "N/A"  # interpret_ratios uses generic N/A for non-positive PE

    def test_recommendations_generated(self):
        result = self.interpreter.interpret_ratio("current_ratio", 0.5)
        assert len(result["recommendation"]) > 0

    def test_benchmark_comparison(self):
        result = self.interpreter.interpret_ratio("current_ratio", 2.0)
        assert "benchmark_comparison" in result
        assert "excellent" in result["benchmark_comparison"]


class TestTrendAnalysis:
    def setup_method(self):
        self.interpreter = RatioInterpreter("technology")

    def test_improving_trend(self):
        result = self.interpreter.analyze_trend(
            "roe", [0.10, 0.12, 0.15], ["2022", "2023", "2024"]
        )
        assert result["trend"] == "Improving"
        assert result["pct_change"] > 0

    def test_deteriorating_trend(self):
        result = self.interpreter.analyze_trend(
            "roe", [0.20, 0.15, 0.10], ["2022", "2023", "2024"]
        )
        assert result["trend"] == "Deteriorating"

    def test_debt_improving(self):
        """Lower debt_to_equity is improving."""
        result = self.interpreter.analyze_trend(
            "debt_to_equity", [2.0, 1.5, 1.0], ["2022", "2023", "2024"]
        )
        assert result["trend"] == "Improving"

    def test_stable_trend(self):
        result = self.interpreter.analyze_trend(
            "roe", [0.100, 0.101, 0.102], ["2022", "2023", "2024"]
        )
        assert result["trend"] == "Stable"

    def test_insufficient_data(self):
        result = self.interpreter.analyze_trend("roe", [0.1], ["2024"])
        assert result["trend"] == "Insufficient data"


class TestGenerateReport:
    def test_report_generation(self):
        ratios = {
            "profitability": {"roe": 0.20, "net_margin": 0.15},
            "liquidity": {"current_ratio": 2.0},
        }
        report = RatioInterpreter("technology").generate_report(ratios)
        assert "Financial Analysis Report" in report
        assert "Technology" in report


class TestComprehensiveAnalysis:
    def test_basic_analysis(self):
        ratios = {
            "profitability": {"roe": 0.20, "net_margin": 0.15},
            "liquidity": {"current_ratio": 2.0},
        }
        result = perform_comprehensive_analysis(ratios, "technology")
        assert "current_analysis" in result
        assert "overall_health" in result
        assert "recommendations" in result
        assert "report" in result

    def test_with_historical_data(self):
        ratios = {
            "profitability": {"roe": 0.20},
        }
        historical = {
            "roe": {
                "values": [0.10, 0.15, 0.20],
                "periods": ["2022", "2023", "2024"],
            }
        }
        result = perform_comprehensive_analysis(ratios, "technology", historical)
        assert "roe" in result["trend_analysis"]
