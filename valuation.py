"""
估值分析模块
DCF + 蒙特卡洛 + 反向DCF + 格雷厄姆 + DDM
纯numpy实现，不引入QuantLib/OpenBB
"""

import numpy as np
from typing import Any


class ValuationAnalyzer:
    """估值分析器"""

    def dcf_2_stage(self, base_fcf: float, growth_rate: float, years: int = 5,
                    terminal_growth: float = 0.03, wacc: float = 0.10,
                    net_debt: float = 0, shares: float = 1) -> dict:
        """
        两阶段DCF（FCFF）

        Args:
            base_fcf: 基期自由现金流
            growth_rate: 第一阶段增长率
            years: 第一阶段年数
            terminal_growth: 永续增长率
            wacc: 加权平均资本成本
            net_debt: 净债务（总负债-现金）
            shares: 总股本
        """
        if terminal_growth >= wacc:
            terminal_growth = wacc - 0.01

        # 第一阶段现值
        pv_stage1 = 0
        fcf = base_fcf
        fcf_projections = []
        for i in range(1, years + 1):
            fcf = fcf * (1 + growth_rate)
            pv = fcf / (1 + wacc) ** i
            pv_stage1 += pv
            fcf_projections.append({"year": i, "fcf": round(fcf, 2), "pv": round(pv, 2)})

        # 第二阶段（永续）
        terminal_fcf = fcf * (1 + terminal_growth)
        terminal_value = terminal_fcf / (wacc - terminal_growth)
        pv_terminal = terminal_value / (1 + wacc) ** years

        # 企业价值
        enterprise_value = pv_stage1 + pv_terminal
        equity_value = enterprise_value - net_debt
        per_share = equity_value / shares if shares > 0 else 0

        return {
            "enterprise_value": round(enterprise_value, 2),
            "equity_value": round(equity_value, 2),
            "per_share_value": round(per_share, 2),
            "pv_stage1": round(pv_stage1, 2),
            "pv_terminal": round(pv_terminal, 2),
            "terminal_value": round(terminal_value, 2),
            "fcf_projections": fcf_projections,
            "assumptions": {
                "base_fcf": base_fcf, "growth_rate": growth_rate,
                "terminal_growth": terminal_growth, "wacc": wacc,
            },
        }

    def reverse_dcf(self, market_cap: float, base_fcf: float, years: int = 5,
                    terminal_growth: float = 0.03, wacc: float = 0.10,
                    net_debt: float = 0) -> dict:
        """
        反向DCF：给定当前市价，反推隐含增长率

        Returns:
            {"implied_growth_rate": float, "interpretation": str}
        """
        target_equity = market_cap
        target_ev = target_equity + net_debt

        # 二分法求解
        low, high = -0.5, 1.0
        for _ in range(100):
            mid = (low + high) / 2
            result = self.dcf_2_stage(base_fcf, mid, years, terminal_growth, wacc, net_debt, 1)
            ev = result["enterprise_value"]
            if ev < target_ev:
                low = mid
            else:
                high = mid
            if abs(ev - target_ev) < 1:
                break

        implied_growth = (low + high) / 2

        # 解读
        if implied_growth > 0.3:
            interpretation = "市场预期极高增长（>30%），风险较大"
        elif implied_growth > 0.15:
            interpretation = "市场预期高增长（15-30%），需验证可持续性"
        elif implied_growth > 0.05:
            interpretation = "市场预期温和增长（5-15%），相对合理"
        elif implied_growth > 0:
            interpretation = "市场预期低增长（0-5%），可能被低估"
        else:
            interpretation = "市场预期负增长，可能被严重低估或有隐含风险"

        return {
            "implied_growth_rate": round(implied_growth * 100, 2),
            "interpretation": interpretation,
        }

    def gordon_growth_model(self, dividend: float, required_return: float,
                            growth_rate: float) -> dict:
        """
        DDM股息折现模型
        适用于稳定分红的公司
        """
        if required_return <= growth_rate:
            return {"error": "要求回报率必须大于增长率"}

        fair_value = dividend * (1 + growth_rate) / (required_return - growth_rate)

        return {
            "fair_value": round(fair_value, 2),
            "dividend_yield": round(dividend / fair_value * 100, 2) if fair_value > 0 else 0,
            "assumptions": {
                "dividend": dividend, "required_return": required_return,
                "growth_rate": growth_rate,
            },
        }

    def graham_number(self, eps: float, bvps: float) -> dict:
        """
        格雷厄姆数值
        Graham Number = sqrt(22.5 × EPS × BVPS)
        """
        if eps <= 0 or bvps <= 0:
            return {"graham_number": 0, "error": "EPS和BVPS必须为正数"}

        graham = np.sqrt(22.5 * eps * bvps)

        return {
            "graham_number": round(graham, 2),
            "eps": eps,
            "bvps": bvps,
        }

    def monte_carlo_dcf(self, base_fcf: float, growth_mean: float, growth_std: float,
                        wacc_mean: float, wacc_std: float, years: int = 5,
                        terminal_growth_mean: float = 0.03, net_debt: float = 0,
                        shares: float = 1, simulations: int = 10000) -> dict:
        """
        蒙特卡洛DCF模拟

        Args:
            base_fcf: 基期FCF
            growth_mean/std: 增长率正态分布参数
            wacc_mean/std: WACC正态分布参数
            terminal_growth_mean: 永续增长率均值
            net_debt: 净债务
            shares: 总股本
            simulations: 模拟次数
        """
        np.random.seed(42)

        results = []
        for _ in range(simulations):
            # 随机参数
            g = np.random.normal(growth_mean, growth_std)
            w = np.random.normal(wacc_mean, wacc_std)
            tg = np.random.uniform(0.02, 0.04)

            # 安全约束
            if w <= tg + 0.01:
                w = tg + 0.02
            if w < 0.05:
                w = 0.05

            # DCF计算
            fcf = base_fcf
            pv_total = 0
            for i in range(1, years + 1):
                fcf = fcf * (1 + g)
                pv_total += fcf / (1 + w) ** i

            terminal_fcf = fcf * (1 + tg)
            terminal_value = terminal_fcf / (w - tg)
            pv_terminal = terminal_value / (1 + w) ** years

            ev = pv_total + pv_terminal
            equity = ev - net_debt
            per_share = equity / shares if shares > 0 else 0
            results.append(per_share)

        results = np.array(results)
        results = results[results > 0]  # 过滤负值

        if len(results) == 0:
            return {"error": "模拟结果无效"}

        percentiles = np.percentile(results, [5, 10, 25, 50, 75, 90, 95])

        return {
            "fair_value_distribution": {
                "p5": round(float(percentiles[0]), 2),
                "p10": round(float(percentiles[1]), 2),
                "p25": round(float(percentiles[2]), 2),
                "p50": round(float(percentiles[3]), 2),
                "p75": round(float(percentiles[4]), 2),
                "p90": round(float(percentiles[5]), 2),
                "p95": round(float(percentiles[6]), 2),
            },
            "mean": round(float(np.mean(results)), 2),
            "std": round(float(np.std(results)), 2),
            "simulations": len(results),
        }

    def safety_margin(self, fair_value: float, current_price: float) -> dict:
        """计算安全边际"""
        if fair_value <= 0:
            return {"safety_margin": 0, "signal": "unknown"}

        margin = (fair_value - current_price) / fair_value * 100

        if margin > 30:
            signal = "deep_value"
        elif margin > 15:
            signal = "undervalued"
        elif margin > 0:
            signal = "slightly_undervalued"
        elif margin > -15:
            signal = "slightly_overvalued"
        else:
            signal = "overvalued"

        return {
            "safety_margin": round(margin, 2),
            "signal": signal,
            "fair_value": round(fair_value, 2),
            "current_price": round(current_price, 2),
        }

    def scenario_analysis(self, base_fcf: float, shares: float, net_debt: float,
                           growth_rate: float = 0.08, wacc: float = 0.10,
                           _net_debt: float = None, years: int = 5) -> dict:
        """三情景DCF模拟（概率加权）"""
        nd = _net_debt if _net_debt is not None else net_debt
        scenarios = {
            "bull": {"growth": growth_rate * 1.5, "prob": 0.20},
            "base": {"growth": growth_rate, "prob": 0.50},
            "bear": {"growth": growth_rate * 0.5, "prob": 0.30},
        }

        results = {}
        for name, cfg in scenarios.items():
            dcf = self.dcf_2_stage(
                base_fcf=base_fcf, growth_rate=cfg["growth"],
                years=years, terminal_growth=0.03, wacc=wacc,
                net_debt=nd, shares=shares
            )
            results[name] = {
                "value": round(dcf["per_share_value"], 2),
                "probability": cfg["prob"],
            }

        expected_value = round(sum(r["value"] * r["probability"] for r in results.values()), 2)

        return {
            "scenarios": results,
            "expected_value": expected_value,
            "upside": results["bull"]["value"],
            "downside": results["bear"]["value"],
        }

    def relative_valuation(self, pe: float, pb: float, ps: float = 0,
                           industry_pe: float = 0, industry_pb: float = 0) -> dict:
        """
        相对估值（PE/PB/PS vs 行业均值）
        """
        result = {}

        if industry_pe > 0 and pe > 0:
            pe_premium = (pe - industry_pe) / industry_pe * 100
            result["pe"] = {
                "value": round(pe, 2),
                "industry_avg": round(industry_pe, 2),
                "premium": round(pe_premium, 2),
                "status": "高估" if pe_premium > 20 else "低估" if pe_premium < -20 else "合理",
            }

        if industry_pb > 0 and pb > 0:
            pb_premium = (pb - industry_pb) / industry_pb * 100
            result["pb"] = {
                "value": round(pb, 2),
                "industry_avg": round(industry_pb, 2),
                "premium": round(pb_premium, 2),
                "status": "高估" if pb_premium > 20 else "低估" if pb_premium < -20 else "合理",
            }

        if ps > 0:
            result["ps"] = {"value": round(ps, 2)}

        return result

    def pe_pb_percentile(self, pe_history: list, pb_history: list,
                         current_pe: float, current_pb: float,
                         years: int = 10) -> dict:
        """当前 PE/PB 在历史序列的百分位(0=最便宜,100=最贵)+ 估值档位。

        pe_history/pb_history:历史 PE/PB 数值序列(日频或年频,取正有效值);
        百分位 = 序列中小于当前值的占比,口径同韭圈儿/蛋卷(<30% 低估、>70% 高估)。
        """
        def _pct(series, cur):
            s = [x for x in (series or []) if x and x > 0]
            if not s or not cur or cur <= 0:
                return None
            return round(sum(1 for x in s if x < cur) / len(s) * 100, 1)

        def _status(pct):
            if pct is None:
                return "未知"
            if pct < 30:
                return "低估"
            if pct > 70:
                return "高估"
            return "适中"

        pe_pct = _pct(pe_history, current_pe)
        pb_pct = _pct(pb_history, current_pb)
        return {
            "pe_percentile": pe_pct,
            "pb_percentile": pb_pct,
            "pe_status": _status(pe_pct),
            "pb_status": _status(pb_pct),
            "current_pe": round(current_pe, 2) if current_pe else 0,
            "current_pb": round(current_pb, 2) if current_pb else 0,
            "sample_years": years,
        }

    def comprehensive_valuation(self, financial_data: dict, market_data: dict,
                                multi_period: list = None, industry_peers: dict = None,
                                pe_history: dict = None) -> dict:
        """
        综合估值分析

        Args:
            financial_data: 最新一期三表数据
            market_data: 市场数据（价格、股本等）
            multi_period: 多期财务数据
            industry_peers: 同行业数据
        """
        inc = financial_data.get("income_statement", {})
        bal = financial_data.get("balance_sheet", {})
        cf = financial_data.get("cash_flow", {})

        # 计算FCFF — 优先使用API提供的freeCashFlow
        ebit = inc.get("operating_profit", 0) or inc.get("ebit", 0) or inc.get("operating_income", 0)
        net_income = inc.get("net_income", 0)
        ocf = cf.get("net_cash_flow_from_operations", 0) or cf.get("operating_cash_flow", 0)
        api_fcf = cf.get("free_cash_flow", 0)
        capex = cf.get("capital_expenditure", 0)
        if capex == 0:
            capex = abs(cf.get("total_cash_outflow_from_investing", 0))
        if capex == 0:
            capex = abs(cf.get("investing_cash_flow", 0))

        # 折旧摊销：优先用API实际值，降级用OCF-NI近似
        da = cf.get("depreciation_amortization", 0)
        if da == 0:
            da = ocf - net_income if ocf > net_income else 0

        # 营运资本变动（简化：用单期近似）
        current_assets = bal.get("current_assets", 0)
        current_liabilities = bal.get("current_liabilities", 0)

        # FCFF = EBIT×(1-税率) + D&A - CapEx - ΔWC
        income_tax = inc.get("income_tax_expense", 0)
        income_before_tax = inc.get("income_before_tax", 0) or inc.get("total_profit", 0) or ebit
        tax_rate = income_tax / income_before_tax if income_before_tax > 0 else 0.25
        tax_rate = min(max(tax_rate, 0.1), 0.35)

        # 优先用API提供的FCF，其次自行计算
        # CapEx正常化：当CapEx/D&A > 2.5x时，说明处于高投资周期
        # 用多年平均CapEx/营收比正常化，避免peak CapEx压低FCF
        capex_da_ratio = capex / da if da > 0 else 1.0
        valuation_method = "DCF"

        if capex_da_ratio > 2.5 and multi_period and len(multi_period) >= 3:
            capex_ratios = []
            for p in multi_period:
                p_capex = abs(p.get("cash_flow", {}).get("capital_expenditure", 0))
                p_rev = p.get("income_statement", {}).get("revenue", 0)
                if p_rev > 0 and p_capex > 0:
                    capex_ratios.append(p_capex / p_rev)
            if len(capex_ratios) >= 3:
                avg_capex_ratio = sum(capex_ratios) / len(capex_ratios)
                normalized_capex = avg_capex_ratio * inc.get("revenue", 0)
                normalized_fcf = ocf - normalized_capex
                if normalized_fcf > 0:
                    fcff = normalized_fcf
                    valuation_method = "DCF (正常化CapEx)"
                else:
                    fcff = api_fcf if api_fcf > 0 else ebit * (1 - tax_rate) + da - capex
            else:
                fcff = api_fcf if api_fcf > 0 else ebit * (1 - tax_rate) + da - capex
        elif api_fcf > 0:
            fcff = api_fcf
        else:
            fcff = ebit * (1 - tax_rate) + da - capex

        # DCF柔性降级：FCF<0时尝试用正常年数据或降级到相对估值
        valuation_method = "DCF"
        dcf_valid = True
        if fcff <= 0 and multi_period and len(multi_period) >= 2:
            for p in multi_period[1:]:
                p_ocf = p.get("cash_flow", {}).get("net_cash_flow_from_operations", 0) or p.get("cash_flow", {}).get("operating_cash_flow", 0)
                p_ni = p.get("income_statement", {}).get("net_income", 0)
                p_capex = abs(p.get("cash_flow", {}).get("capital_expenditure", 0))
                if p_capex == 0:
                    p_capex = abs(p.get("cash_flow", {}).get("total_cash_outflow_from_investing", 0))
                p_da = p_ocf - p_ni if p_ocf > p_ni else 0
                p_ebit = p.get("income_statement", {}).get("operating_profit", 0) or p.get("income_statement", {}).get("ebit", 0)
                p_fcf = p_ebit * (1 - tax_rate) + p_da - p_capex
                if p_fcf > 0:
                    fcff = p_fcf
                    valuation_method = "DCF (正常年基线)"
                    break
        if fcff <= 0:
            dcf_valid = False
            valuation_method = "Relative_Valuation (PS/PB)"

        # 市场数据
        share_price = market_data.get("share_price", 0)
        shares = market_data.get("shares_outstanding", 0)
        market_cap = share_price * shares if shares > 0 else market_data.get("market_cap", 0)

        # 如果股本为0，尝试从资产负债表获取
        if shares <= 0:
            shares = bal.get("outstanding_shares", 0)

        # 如果股本为0但有市值和股价，反推股本
        if shares <= 0 and market_cap > 0 and share_price > 0:
            shares = market_cap / share_price

        # 净债务（DCF用净金融债务 = total_debt - cash，不是 total_liabilities - cash）
        cash = bal.get("cash_and_equivalents", 0)
        net_debt = bal.get("total_debt", 0) - cash

        # 历史增长率（排除异常年的多年CAGR）
        growth_rate = 0.08  # 默认8%
        growth_std = 0.05  # 默认波动率
        if multi_period and len(multi_period) >= 3:
            normal_rev = []
            normal_growth_list = []
            for i in range(len(multi_period) - 1):
                ni_cur = multi_period[i].get("income_statement", {}).get("net_income", 0)
                ni_prev = multi_period[i + 1].get("income_statement", {}).get("net_income", 0)
                rev_cur = multi_period[i].get("income_statement", {}).get("revenue", 0)
                if ni_prev > 0 and abs(ni_cur / ni_prev - 1) < 0.5:
                    normal_rev.append(rev_cur)
                    normal_growth_list.append(ni_cur / ni_prev - 1)
            if len(normal_rev) >= 2:
                n = len(normal_rev) - 1
                if normal_rev[-1] > 0:
                    growth_rate = (normal_rev[0] / normal_rev[-1]) ** (1 / n) - 1
                    growth_rate = max(min(growth_rate, 0.25), -0.05)
            if len(normal_growth_list) >= 2:
                growth_std = max(float(np.std(normal_growth_list)), 0.03)
                # growth_std上限：防止异常年导致蒙特卡洛区间发散
                growth_std = min(growth_std, growth_rate * 0.8 + 0.05)
        elif multi_period and len(multi_period) >= 2:
            rev_latest = multi_period[0].get("income_statement", {}).get("revenue", 0)
            rev_prev = multi_period[1].get("income_statement", {}).get("revenue", 0)
            if rev_prev > 0 and rev_latest > 0:
                growth_rate = (rev_latest / rev_prev) ** (1 / 1) - 1
                growth_rate = max(min(growth_rate, 0.3), -0.1)

        # DCF参数：高增长公司用更长预测期和更低WACC
        # 预测期：增长>10%用10年（捕捉更长增长跑道），否则5年
        dcf_years = 10 if growth_rate > 0.10 else 5
        # WACC：低杠杆(资产负债率<30%)且高盈利(ROE>15%)的大型公司用9%
        debt_ratio = bal.get("total_debt", 0) / bal.get("total_assets", 1) if bal.get("total_assets", 0) > 0 else 1
        roe = net_income / bal.get("shareholders_equity", 1) if bal.get("shareholders_equity", 0) > 0 else 0
        wacc = 0.09 if (debt_ratio < 0.30 and roe > 0.15 and market_cap > 50e9) else 0.10

        # DCF（柔性降级：FCF<0时跳过）
        if dcf_valid:
            dcf_result = self.dcf_2_stage(
                base_fcf=fcff, growth_rate=growth_rate, years=dcf_years,
                terminal_growth=0.03, wacc=wacc, net_debt=net_debt,
                shares=shares if shares > 0 else 1
            )
        else:
            dcf_result = {"per_share_value": 0, "enterprise_value": 0, "equity_value": 0}

        # 反向DCF
        if dcf_valid:
            reverse_result = self.reverse_dcf(
                market_cap=market_cap, base_fcf=fcff, years=dcf_years,
                terminal_growth=0.03, wacc=wacc, net_debt=net_debt
            )
        else:
            reverse_result = {"implied_growth_rate": 0, "interpretation": "FCF为负，DCF不适用"}

        # 格雷厄姆（EPS优先用TTM）
        eps = market_data.get("ttm_eps", 0)
        if eps <= 0:
            eps = inc.get("net_income_attributable", 0) / shares if shares > 0 else 0
        bvps = bal.get("shareholders_equity", 0) / shares if shares > 0 else 0
        graham = self.graham_number(eps, bvps)

        # 安全边际
        safety = self.safety_margin(dcf_result["per_share_value"], share_price)

        # 蒙特卡洛（用历史波动率替代固定σ）
        mc_result = self.monte_carlo_dcf(
            base_fcf=fcff, growth_mean=growth_rate, growth_std=growth_std,
            wacc_mean=wacc, wacc_std=0.015, years=dcf_years,
            net_debt=net_debt, shares=shares if shares > 0 else 1,
            simulations=10000
        ) if dcf_valid else {}

        # 情景分析（概率加权）
        scenario_result = {}
        if dcf_valid and shares > 0:
            scenario_result = self.scenario_analysis(fcff, shares, net_debt, growth_rate, wacc, net_debt, dcf_years)

        # 相对估值
        pe = market_data.get("pe_ratio", 0)
        pb = market_data.get("pb_ratio", 0)
        industry_pe = 0
        industry_pb = 0
        if industry_peers and industry_peers.get("peers"):
            peers = industry_peers["peers"]
            pe_vals = [p["pe"] for p in peers if p["pe"] > 0]
            pb_vals = [p["pb"] for p in peers if p["pb"] > 0]
            industry_pe = np.mean(pe_vals) if pe_vals else 0
            industry_pb = np.mean(pb_vals) if pb_vals else 0
        relative = self.relative_valuation(pe, pb, industry_pe=industry_pe, industry_pb=industry_pb)

        # 估值信号
        dividend_yield = market_data.get("dividend_yield", 0)
        pe_static = market_data.get("pe_static", 0)
        pe_ttm = market_data.get("pe_ttm", 0)
        valuation_signals = {
            "anomalous_year": market_data.get("is_anomalous_year", False),
            "dividend_support": "strong" if dividend_yield >= 4 else "moderate" if dividend_yield >= 2 else "none",
            "dcf_method": valuation_method,
            "pe_spread": round(pe_static - pe_ttm, 2) if pe_static > 0 and pe_ttm > 0 else 0,
            "dividend_warning": market_data.get("dividend_warning"),
        }

        # PE/PB 历史百分位(pe_history 由 fetcher.get_pe_pb_history 提供;None → 跳过)
        pe_pb_pct = {"pe_percentile": None}
        if pe_history:
            pe_pb_pct = self.pe_pb_percentile(
                pe_history.get("pe", []), pe_history.get("pb", []),
                pe_ttm or pe, pb,
            )

        return {
            "fcf": round(fcff, 2),
            "growth_rate": round(growth_rate * 100, 2),
            "tax_rate": round(tax_rate * 100, 2),
            "dcf": dcf_result,
            "reverse_dcf": reverse_result,
            "graham_number": graham,
            "safety_margin": safety,
            "monte_carlo": mc_result,
            "relative": relative,
            "scenario_analysis": scenario_result,
            "valuation_signals": valuation_signals,
            "pe_pb_percentile": pe_pb_pct,
            "dividend_yield": dividend_yield,
        }
