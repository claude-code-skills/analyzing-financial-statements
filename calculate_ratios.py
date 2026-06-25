"""
Financial ratio calculation module.
Provides functions to calculate key financial metrics and ratios.
"""

import json
from typing import Any


class FinancialRatioCalculator:
    """Calculate financial ratios from financial statement data."""

    def __init__(self, financial_data: dict[str, Any], prev_balance_sheet: dict[str, Any] = None):
        """
        Initialize with financial statement data.

        Args:
            financial_data: Dictionary containing income_statement, balance_sheet,
                          cash_flow, and market_data
            prev_balance_sheet: 上期资产负债表(可选,ROE/ROA 用平均分母更准)
        """
        self.income_statement = financial_data.get("income_statement", {})
        self.balance_sheet = financial_data.get("balance_sheet", {})
        self.cash_flow = financial_data.get("cash_flow", {})
        self.market_data = financial_data.get("market_data", {})
        self.prev_balance_sheet = prev_balance_sheet or {}
        self.ratios = {}

    def safe_divide(self, numerator: float, denominator: float, default: float = 0.0) -> float:
        """Safely divide two numbers, returning default if denominator is zero."""
        if denominator == 0:
            return default
        return numerator / denominator

    def calculate_profitability_ratios(self) -> dict[str, float]:
        """Calculate profitability ratios."""
        ratios = {}

        # ROE/ROA — 优先归母净利润(剔除少数股东权益),回退总净利润
        net_income = (self.income_statement.get("net_income_attributable", 0)
                      or self.income_statement.get("net_income", 0))
        # ROE 分母:归母权益(剔除少数股东权益)优先,回退总权益;用平均(本期+上期)/2
        equity0 = self.balance_sheet.get("parent_equity") or self.balance_sheet.get("shareholders_equity", 0)
        equity1 = self.prev_balance_sheet.get("parent_equity") or self.prev_balance_sheet.get("shareholders_equity", 0)
        avg_equity = (equity0 + equity1) / 2 if equity1 > 0 else equity0
        # ROA 分母:总资产(ROA 本就用总资产),平均
        assets0 = self.balance_sheet.get("total_assets", 0)
        assets1 = self.prev_balance_sheet.get("total_assets", 0)
        avg_assets = (assets0 + assets1) / 2 if assets1 > 0 else assets0
        ratios["roe"] = self.safe_divide(net_income, avg_equity)
        ratios["roa"] = self.safe_divide(net_income, avg_assets)

        # Gross Margin
        revenue = self.income_statement.get("revenue", 0)
        # 只有当 COGS 实际存在时才计算毛利率，否则返回0
        if "cost_of_goods_sold" in self.income_statement:
            cogs = self.income_statement["cost_of_goods_sold"]
            gross_profit = revenue - cogs
            ratios["gross_margin"] = self.safe_divide(gross_profit, revenue)
        else:
            ratios["gross_margin"] = 0  # COGS 缺失，无法计算有效毛利率

        # Operating Margin
        operating_income = self.income_statement.get("operating_income", 0)
        ratios["operating_margin"] = self.safe_divide(operating_income, revenue)

        # Net Margin
        ratios["net_margin"] = self.safe_divide(net_income, revenue)

        return ratios

    def calculate_liquidity_ratios(self) -> dict[str, float]:
        """Calculate liquidity ratios."""
        ratios = {}

        current_assets = self.balance_sheet.get("current_assets", 0)
        current_liabilities = self.balance_sheet.get("current_liabilities", 0)

        # Current Ratio
        ratios["current_ratio"] = self.safe_divide(current_assets, current_liabilities)

        # Quick Ratio (Acid Test) — 速动资产 = 流动资产 − 存货 − 预付账款
        inventory = self.balance_sheet.get("inventory", 0)
        prepayments = self.balance_sheet.get("prepayments", 0) or 0
        quick_assets = current_assets - inventory - prepayments
        ratios["quick_ratio"] = self.safe_divide(quick_assets, current_liabilities)

        # Cash Ratio
        cash = self.balance_sheet.get("cash_and_equivalents", 0)
        ratios["cash_ratio"] = self.safe_divide(cash, current_liabilities)

        return ratios

    def calculate_leverage_ratios(self) -> dict[str, float]:
        """Calculate leverage/solvency ratios."""
        ratios = {}

        total_debt = self.balance_sheet.get("total_debt", 0)
        shareholders_equity = self.balance_sheet.get("shareholders_equity", 0)

        # Debt-to-Equity Ratio
        ratios["debt_to_equity"] = self.safe_divide(total_debt, shareholders_equity)

        # Interest Coverage Ratio
        ebit = self.income_statement.get("ebit", 0)
        interest_expense = self.income_statement.get("interest_expense", 0)
        ratios["interest_coverage"] = self.safe_divide(ebit, interest_expense)

        # Debt Service Coverage Ratio
        net_operating_income = self.income_statement.get("operating_income", 0)
        total_debt_service = interest_expense + self.balance_sheet.get(
            "current_portion_long_term_debt", 0
        )
        ratios["debt_service_coverage"] = self.safe_divide(net_operating_income, total_debt_service)

        return ratios

    def calculate_efficiency_ratios(self) -> dict[str, float]:
        """Calculate efficiency/activity ratios."""
        ratios = {}

        revenue = self.income_statement.get("revenue", 0)
        total_assets = self.balance_sheet.get("total_assets", 0)

        # Asset Turnover
        ratios["asset_turnover"] = self.safe_divide(revenue, total_assets)

        # Inventory Turnover
        cogs = self.income_statement.get("cost_of_goods_sold", 0)
        inventory = self.balance_sheet.get("inventory", 0)
        ratios["inventory_turnover"] = self.safe_divide(cogs, inventory)

        # Receivables Turnover
        accounts_receivable = self.balance_sheet.get("accounts_receivable", 0)
        ratios["receivables_turnover"] = self.safe_divide(revenue, accounts_receivable)

        # Days Sales Outstanding
        ratios["days_sales_outstanding"] = self.safe_divide(365, ratios["receivables_turnover"])

        return ratios

    def calculate_valuation_ratios(self) -> dict[str, float]:
        """Calculate valuation ratios.优先使用 FMP ratios-ttm 预计算值，回退到年报计算。"""
        ratios = {}

        share_price = self.market_data.get("share_price", 0)
        shares_outstanding = self.market_data.get("shares_outstanding", 0)
        market_cap = share_price * shares_outstanding

        # P/E Ratio — 优先 TTM，回退年报
        ttm_eps = self.market_data.get("ttm_eps", 0)
        pe_ttm = self.market_data.get("pe_ttm", 0)
        if pe_ttm > 0:
            ratios["pe_ratio"] = pe_ttm
            ratios["eps"] = ttm_eps
        else:
            net_income = self.income_statement.get("net_income", 0)
            eps = self.safe_divide(net_income, shares_outstanding)
            ratios["pe_ratio"] = self.safe_divide(share_price, eps)
            ratios["eps"] = eps

        # P/B Ratio — 优先 TTM（FMP ratios-ttm 有 bookValuePerShareTTM）
        bvps_ttm = self.market_data.get("book_value_per_share", 0)
        if bvps_ttm > 0:
            ratios["book_value_per_share"] = bvps_ttm
            ratios["pb_ratio"] = self.safe_divide(share_price, bvps_ttm)
        else:
            book_value = self.balance_sheet.get("shareholders_equity", 0)
            book_value_per_share = self.safe_divide(book_value, shares_outstanding)
            ratios["pb_ratio"] = self.safe_divide(share_price, book_value_per_share)
            ratios["book_value_per_share"] = book_value_per_share

        # P/S Ratio
        revenue = self.income_statement.get("revenue", 0)
        ratios["ps_ratio"] = self.safe_divide(market_cap, revenue)

        # EV/EBITDA
        ebitda = self.income_statement.get("ebitda", 0)
        total_debt = self.balance_sheet.get("total_debt", 0)
        cash = self.balance_sheet.get("cash_and_equivalents", 0)
        enterprise_value = market_cap + total_debt - cash
        ratios["ev_to_ebitda"] = self.safe_divide(enterprise_value, ebitda)

        # PEG Ratio — 优先 analyzer 自算的 CAGR-based PEG
        peg = self.market_data.get("peg_ratio", 0)
        if peg > 0:
            ratios["peg_ratio"] = peg
        else:
            earnings_growth = self.market_data.get("earnings_growth_rate", 0)
            if earnings_growth > 0:
                ratios["peg_ratio"] = self.safe_divide(ratios["pe_ratio"], earnings_growth * 100)

        return ratios

    def calculate_all_ratios(self) -> dict[str, Any]:
        """Calculate all financial ratios."""
        return {
            "profitability": self.calculate_profitability_ratios(),
            "liquidity": self.calculate_liquidity_ratios(),
            "leverage": self.calculate_leverage_ratios(),
            "efficiency": self.calculate_efficiency_ratios(),
            "valuation": self.calculate_valuation_ratios(),
        }

    def interpret_ratio(self, ratio_name: str, value: float) -> str:
        """Provide interpretation for a specific ratio."""
        interpretations = {
            "current_ratio": lambda v: (
                "Strong liquidity"
                if v > 2
                else "Adequate liquidity"
                if v > 1.5
                else "Potential liquidity concerns"
                if v > 1
                else "Liquidity issues"
            ),
            "debt_to_equity": lambda v: (
                "Low leverage"
                if v < 0.5
                else "Moderate leverage"
                if v < 1
                else "High leverage"
                if v < 2
                else "Very high leverage"
            ),
            "roe": lambda v: (
                "Excellent returns"
                if v > 0.20
                else "Good returns"
                if v > 0.15
                else "Average returns"
                if v > 0.10
                else "Below average returns"
                if v > 0
                else "Negative returns"
            ),
            "pe_ratio": lambda v: (
                "Potentially undervalued"
                if 0 < v < 15
                else "Fair value"
                if 15 <= v < 25
                else "Growth premium"
                if 25 <= v < 40
                else "High valuation"
                if v >= 40
                else "N/A (negative earnings)"
                if v <= 0
                else "N/A"
            ),
        }

        if ratio_name in interpretations:
            return interpretations[ratio_name](value)
        return "No interpretation available"

    # 指标显示类型映射
    RATIO_FORMATS = {
        "roe": "percentage", "roa": "percentage",
        "gross_margin": "percentage", "operating_margin": "percentage", "net_margin": "percentage",
        "current_ratio": "times", "quick_ratio": "times", "cash_ratio": "times",
        "debt_to_equity": "times", "interest_coverage": "times", "debt_service_coverage": "times",
        "asset_turnover": "times", "inventory_turnover": "times", "receivables_turnover": "times",
        "days_sales_outstanding": "days",
        "pe_ratio": "times", "pb_ratio": "times", "ps_ratio": "times", "ev_to_ebitda": "times",
        "eps": "currency", "book_value_per_share": "currency",
    }

    def format_ratio(self, name: str, value: float, format_type: str = "auto") -> str:
        """Format ratio value for display."""
        if format_type == "auto":
            format_type = self.RATIO_FORMATS.get(name, "ratio")

        if format_type == "percentage":
            return f"{value * 100:.2f}%"
        elif format_type == "times":
            return f"{value:.2f}x"
        elif format_type == "days":
            return f"{value:.1f}天"
        elif format_type == "currency":
            return f"{value:.2f}"
        else:
            return f"{value:.2f}"


def calculate_ratios_from_data(financial_data: dict[str, Any], prev_period: dict[str, Any] = None) -> dict[str, Any]:
    """
    Main function to calculate all ratios from financial data.

    Args:
        financial_data: Dictionary with financial statement data
        prev_period: 上期财报(可选,ROE/ROA 平均分母)

    Returns:
        Dictionary with calculated ratios and interpretations
    """
    prev_balance = (prev_period or {}).get("balance_sheet", {}) or {}
    calculator = FinancialRatioCalculator(financial_data, prev_balance_sheet=prev_balance)
    ratios = calculator.calculate_all_ratios()

    # Add interpretations
    interpretations = {}
    for category, category_ratios in ratios.items():
        interpretations[category] = {}
        for ratio_name, value in category_ratios.items():
            interpretations[category][ratio_name] = {
                "value": value,
                "formatted": calculator.format_ratio(ratio_name, value),
                "interpretation": calculator.interpret_ratio(ratio_name, value),
            }

    return {
        "ratios": ratios,
        "interpretations": interpretations,
        "summary": generate_summary(ratios),
    }


def generate_summary(ratios: dict[str, Any]) -> str:
    """Generate a text summary of the financial analysis."""
    summary_parts = []

    # Profitability summary
    prof = ratios.get("profitability", {})
    if prof.get("roe", 0) > 0:
        summary_parts.append(
            f"ROE of {prof['roe'] * 100:.1f}% indicates {'strong' if prof['roe'] > 0.15 else 'moderate'} shareholder returns."
        )

    # Liquidity summary
    liq = ratios.get("liquidity", {})
    if liq.get("current_ratio", 0) > 0:
        summary_parts.append(
            f"Current ratio of {liq['current_ratio']:.2f} suggests {'good' if liq['current_ratio'] > 1.5 else 'potential'} liquidity {'position' if liq['current_ratio'] > 1.5 else 'concerns'}."
        )

    # Leverage summary
    lev = ratios.get("leverage", {})
    if "debt_to_equity" in lev and lev["debt_to_equity"] >= 0:
        summary_parts.append(
            f"Debt-to-equity of {lev['debt_to_equity']:.2f} indicates {'conservative' if lev['debt_to_equity'] < 0.5 else 'moderate' if lev['debt_to_equity'] < 1 else 'high'} leverage."
        )

    # Valuation summary
    val = ratios.get("valuation", {})
    if val.get("pe_ratio", 0) > 0:
        summary_parts.append(
            f"P/E ratio of {val['pe_ratio']:.1f} suggests the stock is trading at {'a discount' if val['pe_ratio'] < 15 else 'fair value' if val['pe_ratio'] < 25 else 'a premium'}."
        )

    return " ".join(summary_parts) if summary_parts else "Insufficient data for summary."


# Example usage
if __name__ == "__main__":
    # Sample financial data
    sample_data = {
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

    results = calculate_ratios_from_data(sample_data)
    print(json.dumps(results, indent=2))