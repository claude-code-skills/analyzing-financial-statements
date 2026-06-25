"""Tests for risk_screening module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from risk_screening import RiskScreener


class TestBeneishM:
    def setup_method(self):
        self.screener = RiskScreener()

    def test_normal_company(self):
        current = {
            "accounts_receivable": 100, "revenue": 1000, "gross_margin": 0.4,
            "intangible_assets": 50, "total_assets": 2000,
            "net_income": 150, "depreciation": 80, "sga_expense": 100,
            "current_liabilities": 300, "long_term_debt": 200, "cash": 200,
            "operating_cash_flow": 180,
        }
        prior = {
            "accounts_receivable": 90, "revenue": 950, "gross_margin": 0.38,
            "intangible_assets": 45, "total_assets": 1800,
            "net_income": 130, "depreciation": 75, "sga_expense": 95,
            "current_liabilities": 280, "long_term_debt": 210, "cash": 180,
            "operating_cash_flow": 160,
        }
        result = self.screener.beneish_m(current, prior)
        assert "m_score" in result
        assert "risk" in result
        assert "components" in result
        assert result["m_score"] is not None

    def test_suspicious_company(self):
        """Company with rapidly growing receivables and declining cash flow."""
        current = {
            "accounts_receivable": 500, "revenue": 1000, "gross_margin": 0.3,
            "intangible_assets": 200, "total_assets": 2000,
            "net_income": 200, "depreciation": 50, "sga_expense": 300,
            "current_liabilities": 600, "long_term_debt": 500, "cash": 50,
            "operating_cash_flow": 20,
        }
        prior = {
            "accounts_receivable": 100, "revenue": 800, "gross_margin": 0.45,
            "intangible_assets": 50, "total_assets": 1500,
            "net_income": 100, "depreciation": 40, "sga_expense": 100,
            "current_liabilities": 300, "long_term_debt": 200, "cash": 200,
            "operating_cash_flow": 150,
        }
        result = self.screener.beneish_m(current, prior)
        # Suspicious company should have high M-Score
        assert result["risk"] == "高风险"


class TestAltmanZ:
    def setup_method(self):
        self.screener = RiskScreener()

    def test_safe_company(self):
        result = self.screener.altman_z(
            working_capital=500, retained_earnings=800,
            ebit=300, market_cap=5000, total_liabilities=500,
            total_assets=2000, revenue=3000
        )
        assert "z_score" in result
        assert "zone" in result
        assert "risk" in result
        # This should be a safe company
        assert result["zone"] == "安全区"
        assert result["z_score"] > 2.99

    def test_distressed_company(self):
        result = self.screener.altman_z(
            working_capital=100, retained_earnings=50,
            ebit=20, market_cap=200, total_liabilities=1500,
            total_assets=2000, revenue=500
        )
        assert result["zone"] == "困境区"
        assert result["z_score"] < 1.81

    def test_zero_assets(self):
        result = self.screener.altman_z(
            working_capital=0, retained_earnings=0,
            ebit=0, market_cap=0, total_liabilities=0,
            total_assets=0, revenue=0
        )
        assert "error" in result


class TestPiotroskiF:
    def setup_method(self):
        self.screener = RiskScreener()

    def test_strong_company(self):
        current = {
            "net_income": 200, "total_assets": 2000, "operating_cash_flow": 300,
            "long_term_debt": 200, "current_assets": 800, "current_liabilities": 400,
            "shares_outstanding": 100, "gross_margin": 0.4, "revenue": 2000,
        }
        prior = {
            "net_income": 150, "total_assets": 1800, "operating_cash_flow": 200,
            "long_term_debt": 300, "current_assets": 600, "current_liabilities": 500,
            "shares_outstanding": 100, "gross_margin": 0.35, "revenue": 1800,
        }
        result = self.screener.piotroski_f(current, prior)
        assert "f_score" in result
        assert "signal" in result
        assert "details" in result
        assert result["f_score"] >= 6

    def test_weak_company(self):
        current = {
            "net_income": -50, "total_assets": 2000, "operating_cash_flow": -100,
            "long_term_debt": 800, "current_assets": 300, "current_liabilities": 500,
            "shares_outstanding": 150, "gross_margin": 0.15, "revenue": 500,
        }
        prior = {
            "net_income": 50, "total_assets": 1800, "operating_cash_flow": 100,
            "long_term_debt": 500, "current_assets": 500, "current_liabilities": 400,
            "shares_outstanding": 100, "gross_margin": 0.3, "revenue": 800,
        }
        result = self.screener.piotroski_f(current, prior)
        assert result["f_score"] <= 4

    def test_score_range(self):
        current = {
            "net_income": 100, "total_assets": 1000, "operating_cash_flow": 150,
            "long_term_debt": 200, "current_assets": 500, "current_liabilities": 300,
            "shares_outstanding": 100, "gross_margin": 0.3, "revenue": 1000,
        }
        prior = {
            "net_income": 80, "total_assets": 900, "operating_cash_flow": 120,
            "long_term_debt": 250, "current_assets": 450, "current_liabilities": 350,
            "shares_outstanding": 100, "gross_margin": 0.28, "revenue": 900,
        }
        result = self.screener.piotroski_f(current, prior)
        assert 0 <= result["f_score"] <= 9


class TestAShareChecks:
    def setup_method(self):
        self.screener = RiskScreener()

    def test_healthy_company(self):
        current = {
            "revenue": 10000, "accounts_receivable": 1000,
            "net_income": 2000, "operating_cash_flow": 2500,
            "goodwill": 100, "shareholders_equity": 5000,
            "total_assets": 10000, "total_liabilities": 4000,
            "current_assets": 3000, "current_liabilities": 1500,
            "cash_and_equivalents": 1000, "total_debt": 1000,
            "capital_expenditure": 500, "pledge_ratio": 10,
        }
        result = self.screener.a_share_checks(current)
        assert "checks" in result
        assert "red_count" in result
        assert "yellow_count" in result
        assert "green_count" in result
        assert "risk_score" in result
        assert result["red_count"] == 0
        assert result["risk_score"] < 30

    def test_risky_company(self):
        current = {
            "revenue": 10000, "accounts_receivable": 5000,
            "net_income": 500, "operating_cash_flow": 200,
            "goodwill": 3000, "shareholders_equity": 4000,
            "total_assets": 10000, "total_liabilities": 8000,
            "current_assets": 2000, "current_liabilities": 2500,
            "cash_and_equivalents": 2000, "total_debt": 3000,
            "capital_expenditure": 1000, "pledge_ratio": 90,
        }
        prior = {
            "net_income": 600, "operating_cash_flow": 100,
        }
        result = self.screener.a_share_checks(current, prior)
        assert result["red_count"] >= 2
        assert result["risk_score"] > 40


class TestComprehensiveRiskCheck:
    def setup_method(self):
        self.screener = RiskScreener()

    def test_basic_check(self):
        multi_period = [
            {
                "income_statement": {
                    "revenue": 10000, "net_income": 2000,
                    "operating_profit": 2500, "operating_cost": 6000,
                    "selling_expense": 500, "admin_expense": 300,
                    "income_tax_expense": 500, "total_profit": 2500,
                },
                "balance_sheet": {
                    "total_assets": 20000, "shareholders_equity": 12000,
                    "total_liabilities": 8000, "working_capital": 3000,
                    "accounts_receivable": 1000, "current_assets": 5000,
                    "current_liabilities": 2000, "cash_and_equivalents": 2000,
                    "total_debt": 3000, "goodwill": 500,
                    "long_term_debt": 2000, "intangible_assets": 200,
                },
                "cash_flow": {
                    "net_cash_flow_from_operations": 3000,
                    "capital_expenditure": 1000,
                },
            },
            {
                "income_statement": {
                    "revenue": 9000, "net_income": 1800,
                    "operating_profit": 2200, "operating_cost": 5500,
                    "selling_expense": 450, "admin_expense": 280,
                    "income_tax_expense": 450, "total_profit": 2200,
                },
                "balance_sheet": {
                    "total_assets": 18000, "shareholders_equity": 11000,
                    "total_liabilities": 7000, "working_capital": 2500,
                    "accounts_receivable": 900, "current_assets": 4500,
                    "current_liabilities": 2000, "cash_and_equivalents": 1800,
                    "total_debt": 2500, "goodwill": 400,
                    "long_term_debt": 1800, "intangible_assets": 180,
                },
                "cash_flow": {
                    "net_cash_flow_from_operations": 2500,
                    "capital_expenditure": 800,
                },
            },
        ]
        market_data = {
            "market_cap": 50000, "share_price": 50, "shares_outstanding": 1000,
        }
        pledge_data = {"pledge_ratio": 10}

        result = self.screener.comprehensive_risk_check(
            multi_period, market_data, pledge_data
        )
        assert "beneish_m" in result
        assert "altman_z" in result
        assert "piotroski_f" in result
        assert "a_share_checks" in result
        assert "total_risk_score" in result
        assert "total_risk_level" in result

    def test_insufficient_data(self):
        result = self.screener.comprehensive_risk_check([], {})
        assert "error" in result
