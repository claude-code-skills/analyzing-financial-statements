"""Tests for valuation module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

import pytest
import numpy as np
from valuation import ValuationAnalyzer


class TestDCF2Stage:
    def setup_method(self):
        self.analyzer = ValuationAnalyzer()

    def test_basic_dcf(self):
        result = self.analyzer.dcf_2_stage(
            base_fcf=1000, growth_rate=0.08, years=5,
            terminal_growth=0.03, wacc=0.10, net_debt=500, shares=100
        )
        assert "enterprise_value" in result
        assert "equity_value" in result
        assert "per_share_value" in result
        assert "fcf_projections" in result
        assert len(result["fcf_projections"]) == 5
        assert result["per_share_value"] > 0

    def test_terminal_growth_capped(self):
        result = self.analyzer.dcf_2_stage(
            base_fcf=1000, growth_rate=0.08,
            terminal_growth=0.15, wacc=0.10,  # terminal >= wacc
        )
        # terminal_growth should be capped to wacc - 0.01
        assert result["assumptions"]["terminal_growth"] == pytest.approx(0.09)

    def test_zero_shares(self):
        result = self.analyzer.dcf_2_stage(
            base_fcf=1000, growth_rate=0.08, shares=0
        )
        assert result["per_share_value"] == 0


class TestReverseDCF:
    def setup_method(self):
        self.analyzer = ValuationAnalyzer()

    def test_basic_reverse(self):
        # First get a DCF value, then reverse it
        dcf = self.analyzer.dcf_2_stage(
            base_fcf=1000, growth_rate=0.10, years=5,
            terminal_growth=0.03, wacc=0.10, net_debt=0, shares=1
        )
        result = self.analyzer.reverse_dcf(
            market_cap=dcf["enterprise_value"], base_fcf=1000, years=5,
            terminal_growth=0.03, wacc=0.10, net_debt=0
        )
        assert "implied_growth_rate" in result
        assert "interpretation" in result
        # Should recover approximately 10%
        assert abs(result["implied_growth_rate"] - 10) < 2

    def test_negative_implied(self):
        result = self.analyzer.reverse_dcf(
            market_cap=10, base_fcf=1000, years=5,
            terminal_growth=0.03, wacc=0.10
        )
        # Very low market cap should imply negative growth
        assert result["implied_growth_rate"] < 0


class TestGordonGrowth:
    def setup_method(self):
        self.analyzer = ValuationAnalyzer()

    def test_basic_ddm(self):
        result = self.analyzer.gordon_growth_model(
            dividend=5, required_return=0.10, growth_rate=0.05
        )
        assert "fair_value" in result
        assert "dividend_yield" in result
        assert abs(result["fair_value"] - 105) < 0.01

    def test_invalid_params(self):
        result = self.analyzer.gordon_growth_model(
            dividend=5, required_return=0.05, growth_rate=0.10
        )
        assert "error" in result


class TestGrahamNumber:
    def setup_method(self):
        self.analyzer = ValuationAnalyzer()

    def test_basic_graham(self):
        result = self.analyzer.graham_number(eps=5, bvps=30)
        expected = np.sqrt(22.5 * 5 * 30)
        assert abs(result["graham_number"] - round(expected, 2)) < 0.01

    def test_negative_eps(self):
        result = self.analyzer.graham_number(eps=-5, bvps=30)
        assert result["graham_number"] == 0
        assert "error" in result


class TestMonteCarloDCF:
    def setup_method(self):
        self.analyzer = ValuationAnalyzer()

    def test_basic_simulation(self):
        result = self.analyzer.monte_carlo_dcf(
            base_fcf=1000, growth_mean=0.08, growth_std=0.05,
            wacc_mean=0.10, wacc_std=0.015, simulations=100
        )
        assert "fair_value_distribution" in result
        dist = result["fair_value_distribution"]
        assert "p5" in dist
        assert "p50" in dist
        assert "p95" in dist
        assert dist["p5"] < dist["p50"] < dist["p95"]
        assert result["simulations"] > 0

    def test_deterministic_seed(self):
        r1 = self.analyzer.monte_carlo_dcf(
            base_fcf=1000, growth_mean=0.08, growth_std=0.05,
            wacc_mean=0.10, wacc_std=0.015, simulations=100
        )
        r2 = self.analyzer.monte_carlo_dcf(
            base_fcf=1000, growth_mean=0.08, growth_std=0.05,
            wacc_mean=0.10, wacc_std=0.015, simulations=100
        )
        assert r1["fair_value_distribution"]["p50"] == r2["fair_value_distribution"]["p50"]


class TestSafetyMargin:
    def setup_method(self):
        self.analyzer = ValuationAnalyzer()

    def test_deep_value(self):
        result = self.analyzer.safety_margin(fair_value=100, current_price=50)
        assert result["safety_margin"] == 50.0
        assert result["signal"] == "deep_value"

    def test_undervalued(self):
        result = self.analyzer.safety_margin(fair_value=100, current_price=80)
        assert result["signal"] == "undervalued"

    def test_overvalued(self):
        result = self.analyzer.safety_margin(fair_value=100, current_price=130)
        assert result["safety_margin"] < 0
        assert result["signal"] == "overvalued"

    def test_zero_fair_value(self):
        result = self.analyzer.safety_margin(fair_value=0, current_price=50)
        assert result["safety_margin"] == 0
        assert result["signal"] == "unknown"


class TestScenarioAnalysis:
    def setup_method(self):
        self.analyzer = ValuationAnalyzer()

    def test_three_scenarios(self):
        result = self.analyzer.scenario_analysis(
            base_fcf=1000, shares=100, net_debt=500, growth_rate=0.08
        )
        assert "scenarios" in result
        assert "bull" in result["scenarios"]
        assert "base" in result["scenarios"]
        assert "bear" in result["scenarios"]
        assert "expected_value" in result
        assert result["scenarios"]["bull"]["value"] > result["scenarios"]["bear"]["value"]

    def test_probability_weights(self):
        result = self.analyzer.scenario_analysis(
            base_fcf=1000, shares=100, net_debt=500
        )
        probs = [s["probability"] for s in result["scenarios"].values()]
        assert abs(sum(probs) - 1.0) < 0.01


class TestRelativeValuation:
    def setup_method(self):
        self.analyzer = ValuationAnalyzer()

    def test_pe_comparison(self):
        result = self.analyzer.relative_valuation(
            pe=15, pb=4, industry_pe=25, industry_pb=2.5
        )
        assert "pe" in result
        # (15-25)/25 = -40% < -20 → 低估
        assert result["pe"]["status"] == "低估"
        assert "pb" in result
        # (4-2.5)/2.5 = 60% > 20 → 高估
        assert result["pb"]["status"] == "高估"

    def test_no_industry(self):
        result = self.analyzer.relative_valuation(pe=20, pb=3)
        assert "pe" not in result

    def test_ps_alone(self):
        result = self.analyzer.relative_valuation(pe=0, pb=0, ps=5)
        assert "ps" in result
