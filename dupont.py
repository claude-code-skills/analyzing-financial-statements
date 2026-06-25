"""
杜邦分析模块
三因素 + 五因素分解，多期趋势，ROE质量评级
"""

from typing import Any


class DuPontAnalyzer:
    """杜邦分析器"""

    def dupont_3(self, net_income: float, revenue: float,
                 total_assets: float, equity: float) -> dict:
        """
        三因素杜邦分解
        ROE = 净利率 × 资产周转率 × 权益乘数
        """
        npm = net_income / revenue if revenue > 0 else 0
        at = revenue / total_assets if total_assets > 0 else 0
        em = total_assets / equity if equity > 0 else 0

        npm_pct = round(npm * 100, 2)
        at_r = round(at, 4)
        em_r = round(em, 2)
        # 从已 round 分量反算 ROE，保证乘积一致性
        roe = round(npm_pct / 100 * at_r * em_r * 100, 2)

        return {
            "roe": roe,
            "net_profit_margin": npm_pct,
            "asset_turnover": at_r,
            "equity_multiplier": em_r,
        }

    def dupont_5(self, net_income: float, ebt: float, ebit: float,
                 revenue: float, total_assets: float, equity: float) -> dict:
        """
        五因素杜邦分解
        ROE = 税负系数 × 利息负担 × 营业利润率 × 资产周转率 × 权益乘数
        """
        tax_burden = net_income / ebt if ebt > 0 else 0
        interest_burden = ebt / ebit if ebit > 0 else 0
        operating_margin = ebit / revenue if revenue > 0 else 0
        asset_turnover = revenue / total_assets if total_assets > 0 else 0
        equity_multiplier = total_assets / equity if equity > 0 else 0

        tb_r = round(tax_burden, 4)
        ib_r = round(interest_burden, 4)
        om_pct = round(operating_margin * 100, 2)
        at_r = round(asset_turnover, 4)
        em_r = round(equity_multiplier, 2)
        # 从已 round 分量反算 ROE，保证乘积一致性
        roe = round(tb_r * ib_r * om_pct / 100 * at_r * em_r * 100, 2)

        return {
            "roe": roe,
            "tax_burden": tb_r,
            "interest_burden": ib_r,
            "operating_margin": om_pct,
            "asset_turnover": at_r,
            "equity_multiplier": em_r,
        }

    def analyze_trend(self, multi_period_data: list[dict]) -> dict:
        """
        多期杜邦趋势分析

        Args:
            multi_period_data: [{income_statement: {...}, balance_sheet: {...}}, ...]
        """
        results = []

        for period in multi_period_data:
            inc = period.get("income_statement", {})
            bal = period.get("balance_sheet", {})

            net_income = inc.get("net_income_attributable", 0) or inc.get("net_income", 0)
            revenue = inc.get("revenue", 0)
            ebt = inc.get("total_profit", 0)
            ebit = inc.get("operating_profit", 0)
            total_assets = bal.get("total_assets", 0)
            equity = bal.get("parent_equity", 0) or bal.get("shareholders_equity", 0) or bal.get("total_equity", 0)
            date = inc.get("date", bal.get("date", ""))

            if total_assets > 0 and equity > 0 and revenue > 0:
                dp3 = self.dupont_3(net_income, revenue, total_assets, equity)
                dp5 = self.dupont_5(net_income, ebt, ebit, revenue, total_assets, equity)
                results.append({"date": date, "dupont_3": dp3, "dupont_5": dp5})

        if not results:
            return {"error": "数据不足，无法进行杜邦分析"}

        # 趋势分析
        latest = results[0]
        roe_trend = [r["dupont_3"]["roe"] for r in results]

        # 判断驱动因素
        driver = self._identify_driver(latest["dupont_5"])

        # ROE质量评级
        quality = self._assess_quality(results)

        return {
            "latest": latest,
            "periods": results,
            "roe_trend": roe_trend,
            "driver": driver,
            "quality": quality,
        }

    def _identify_driver(self, dp5: dict) -> dict:
        """识别ROE主要驱动因素"""
        factors = {
            "净利率驱动": abs(dp5["operating_margin"]),
            "周转率驱动": abs(dp5["asset_turnover"]) * 100,
            "杠杆驱动": abs(dp5["equity_multiplier"] - 1) * 50,
        }
        main_driver = max(factors, key=factors.get)

        explanation = {
            "净利率驱动": "赚钱靠高利润率（品牌/垄断/差异化）",
            "周转率驱动": "赚钱靠高周转（薄利多销/零售模式）",
            "杠杆驱动": "赚钱靠借钱放大收益（风险较高）",
        }

        return {
            "main_driver": main_driver,
            "explanation": explanation[main_driver],
            "factors": factors,
        }

    def _assess_quality(self, results: list[dict]) -> dict:
        """ROE质量评级"""
        if not results:
            return {"rating": "unknown", "score": 0}

        latest = results[0]["dupont_3"]

        score = 0
        reasons = []

        # ROE水平
        roe = latest["roe"]
        if roe > 20:
            score += 3
            reasons.append(f"ROE优秀({roe}%)")
        elif roe > 15:
            score += 2
            reasons.append(f"ROE良好({roe}%)")
        elif roe > 10:
            score += 1
            reasons.append(f"ROE一般({roe}%)")
        else:
            reasons.append(f"ROE偏低({roe}%)")

        # 净利率
        npm = latest["net_profit_margin"]
        if npm > 20:
            score += 2
            reasons.append(f"净利率高({npm}%)，有定价权")
        elif npm > 10:
            score += 1
            reasons.append(f"净利率尚可({npm}%)")

        # 杠杆
        em = latest["equity_multiplier"]
        if em < 1.5:
            score += 2
            reasons.append(f"低杠杆({em}倍)，财务稳健")
        elif em < 2.5:
            score += 1
            reasons.append(f"适中杠杆({em}倍)")
        else:
            reasons.append(f"高杠杆({em}倍)，风险较高")

        # 趋势
        if len(results) >= 2:
            roe_prev = results[1]["dupont_3"]["roe"]
            if roe > roe_prev:
                score += 1
                reasons.append("ROE上升趋势")
            elif roe < roe_prev * 0.9:
                reasons.append("ROE下滑趋势")

        if score >= 6:
            rating = "优质"
        elif score >= 4:
            rating = "良好"
        elif score >= 2:
            rating = "一般"
        else:
            rating = "较差"

        return {"rating": rating, "score": score, "reasons": reasons}
