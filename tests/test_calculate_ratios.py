"""Tests for calculate_ratios module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from calculate_ratios import FinancialRatioCalculator, calculate_ratios_from_data, generate_summary


def _sample_data():
    return {
        "income_statement": {
            "revenue": 1000000,
            "cost_of_goods_sold": 600000,
            "operating_income": 200000,
            "ebit": 180000,
            "ebitda": 250000,
            "interest_expense": 20000,
            "net_income": 150000,
        },
        "balance_sheet": {
            "total_assets": 2000000,
            "current_assets": 800000,
            "cash_and_equivalents": 200000,
            "accounts_receivable": 150000,
            "inventory": 250000,
            "current_liabilities": 400000,
            "total_debt": 500000,
            "current_portion_long_term_debt": 50000,
            "shareholders_equity": 1500000,
        },
        "cash_flow": {
            "operating_cash_flow": 180000,
            "investing_cash_flow": -100000,
            "financing_cash_flow": -50000,
        },
        "market_data": {
            "share_price": 50,
            "shares_outstanding": 100000,
            "earnings_growth_rate": 0.10,
        },
    }


class TestFinancialRatioCalculator:
    def setup_method(self):
        self.calc = FinancialRatioCalculator(_sample_data())

    def test_safe_divide_normal(self):
        assert self.calc.safe_divide(10, 2) == 5.0

    def test_safe_divide_zero(self):
        assert self.calc.safe_divide(10, 0) == 0.0

    def test_safe_divide_custom_default(self):
        assert self.calc.safe_divide(10, 0, default=-1) == -1

    def test_profitability_ratios(self):
        ratios = self.calc.calculate_profitability_ratios()
        assert "roe" in ratios
        assert "roa" in ratios
        assert "gross_margin" in ratios
        assert "operating_margin" in ratios
        assert "net_margin" in ratios
        # ROE = 150000/1500000 = 0.1
        assert abs(ratios["roe"] - 0.1) < 0.001
        # ROA = 150000/2000000 = 0.075
        assert abs(ratios["roa"] - 0.075) < 0.001
        # gross_margin = (1000000-600000)/1000000 = 0.4
        assert abs(ratios["gross_margin"] - 0.4) < 0.001

    def test_profitability_no_cogs(self):
        data = _sample_data()
        del data["income_statement"]["cost_of_goods_sold"]
        calc = FinancialRatioCalculator(data)
        ratios = calc.calculate_profitability_ratios()
        assert ratios["gross_margin"] == 0

    def test_liquidity_ratios(self):
        ratios = self.calc.calculate_liquidity_ratios()
        assert "current_ratio" in ratios
        assert "quick_ratio" in ratios
        assert "cash_ratio" in ratios
        # current_ratio = 800000/400000 = 2.0
        assert abs(ratios["current_ratio"] - 2.0) < 0.001

    def test_leverage_ratios(self):
        ratios = self.calc.calculate_leverage_ratios()
        assert "debt_to_equity" in ratios
        assert "interest_coverage" in ratios
        # debt_to_equity = 500000/1500000 = 0.333
        assert abs(ratios["debt_to_equity"] - 0.333) < 0.01

    def test_efficiency_ratios(self):
        ratios = self.calc.calculate_efficiency_ratios()
        assert "asset_turnover" in ratios
        assert "inventory_turnover" in ratios
        assert "receivables_turnover" in ratios
        assert "days_sales_outstanding" in ratios

    def test_valuation_ratios(self):
        ratios = self.calc.calculate_valuation_ratios()
        assert "pe_ratio" in ratios
        assert "pb_ratio" in ratios
        assert "ps_ratio" in ratios
        assert "eps" in ratios
        assert "peg_ratio" in ratios
        # EPS = 150000/100000 = 1.5
        assert abs(ratios["eps"] - 1.5) < 0.001
        # PE = 50/1.5 = 33.33
        assert abs(ratios["pe_ratio"] - 33.33) < 0.1

    def test_calculate_all_ratios(self):
        all_ratios = self.calc.calculate_all_ratios()
        assert "profitability" in all_ratios
        assert "liquidity" in all_ratios
        assert "leverage" in all_ratios
        assert "efficiency" in all_ratios
        assert "valuation" in all_ratios

    def test_interpret_ratio_roe(self):
        assert self.calc.interpret_ratio("roe", 0.25) == "Excellent returns"
        assert self.calc.interpret_ratio("roe", 0.17) == "Good returns"
        assert self.calc.interpret_ratio("roe", 0.12) == "Average returns"
        assert self.calc.interpret_ratio("roe", 0.05) == "Below average returns"
        assert self.calc.interpret_ratio("roe", -0.1) == "Negative returns"

    def test_interpret_ratio_current_ratio(self):
        assert self.calc.interpret_ratio("current_ratio", 2.5) == "Strong liquidity"
        assert self.calc.interpret_ratio("current_ratio", 1.0) == "Liquidity issues"

    def test_interpret_ratio_debt_to_equity(self):
        assert self.calc.interpret_ratio("debt_to_equity", 0.3) == "Low leverage"
        assert self.calc.interpret_ratio("debt_to_equity", 3.0) == "Very high leverage"

    def test_interpret_ratio_pe(self):
        assert self.calc.interpret_ratio("pe_ratio", 10) == "Potentially undervalued"
        assert self.calc.interpret_ratio("pe_ratio", 20) == "Fair value"
        assert self.calc.interpret_ratio("pe_ratio", 30) == "Growth premium"
        assert self.calc.interpret_ratio("pe_ratio", 50) == "High valuation"
        assert self.calc.interpret_ratio("pe_ratio", -5) == "N/A (negative earnings)"

    def test_interpret_ratio_unknown(self):
        assert self.calc.interpret_ratio("unknown_ratio", 1.0) == "No interpretation available"

    def test_format_ratio_percentage(self):
        assert self.calc.format_ratio("roe", 0.15) == "15.00%"

    def test_format_ratio_times(self):
        assert self.calc.format_ratio("current_ratio", 2.5) == "2.50x"

    def test_format_ratio_days(self):
        assert self.calc.format_ratio("days_sales_outstanding", 30) == "30.0天"

    def test_format_ratio_currency(self):
        assert self.calc.format_ratio("eps", 1.5) == "1.50"


class TestCalculateRatiosFromData:
    def test_returns_structure(self):
        result = calculate_ratios_from_data(_sample_data())
        assert "ratios" in result
        assert "interpretations" in result
        assert "summary" in result

    def test_summary_content(self):
        result = calculate_ratios_from_data(_sample_data())
        assert "ROE" in result["summary"]


class TestGenerateSummary:
    def test_with_good_ratios(self):
        ratios = {
            "profitability": {"roe": 0.20},
            "liquidity": {"current_ratio": 2.5},
            "leverage": {"debt_to_equity": 0.3},
            "valuation": {"pe_ratio": 15},
        }
        summary = generate_summary(ratios)
        assert "ROE" in summary
        assert "Current ratio" in summary

    def test_insufficient_data(self):
        assert generate_summary({}) == "Insufficient data for summary."


class TestRatioFixes:
    """ROE 归母口径 + 速动减预付 回归测试。"""

    def test_roe_uses_attributable_income(self):
        """ROE/ROA 应优先用归母净利润(net_income_attributable,剔除少数股东)。"""
        from calculate_ratios import FinancialRatioCalculator
        data = {
            "income_statement": {"net_income": 200, "net_income_attributable": 150, "revenue": 1000},
            "balance_sheet": {"shareholders_equity": 1000, "total_assets": 2000},
        }
        prof = FinancialRatioCalculator(data).calculate_profitability_ratios()
        assert abs(prof["roe"] - 0.15) < 1e-9   # 150/1000,不是 200/1000
        assert abs(prof["roa"] - 0.075) < 1e-9  # 150/2000

    def test_quick_ratio_subtracts_prepayments(self):
        """速动比率应减去预付账款(标准速动 = 流动 − 存货 − 预付)。"""
        from calculate_ratios import FinancialRatioCalculator
        data = {"balance_sheet": {"current_assets": 500, "current_liabilities": 200,
                                  "inventory": 100, "prepayments": 50}}
        liq = FinancialRatioCalculator(data).calculate_liquidity_ratios()
        assert abs(liq["quick_ratio"] - 1.75) < 1e-9  # (500-100-50)/200

    def test_roe_uses_average_equity(self):
        """ROE/ROA 应优先用平均权益(本期+上期)/2 做分母(更准)。"""
        from calculate_ratios import FinancialRatioCalculator
        data = {
            "income_statement": {"net_income_attributable": 150, "revenue": 1000},
            "balance_sheet": {"shareholders_equity": 1000, "total_assets": 2000},
        }
        prev = {"shareholders_equity": 500, "total_assets": 1500}
        prof = FinancialRatioCalculator(data, prev_balance_sheet=prev).calculate_profitability_ratios()
        assert abs(prof["roe"] - 0.2) < 1e-9          # 150 / ((1000+500)/2)=750
        assert abs(prof["roa"] - 150 / 1750) < 1e-9   # 150 / ((2000+1500)/2)=1750

    def test_roe_prefers_parent_equity(self):
        """ROE 分母优先用归母权益(parent_equity,剔除少数股东),回退总权益。"""
        from calculate_ratios import FinancialRatioCalculator
        data = {
            "income_statement": {"net_income_attributable": 100},
            "balance_sheet": {"parent_equity": 500, "shareholders_equity": 600},  # 归母<总(含少数)
        }
        prof = FinancialRatioCalculator(data).calculate_profitability_ratios()
        assert abs(prof["roe"] - 0.2) < 1e-9  # 100/500(归母),不是 100/600
