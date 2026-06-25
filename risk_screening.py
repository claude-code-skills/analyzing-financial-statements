"""
极端风险排查模块
Beneish M-Score + Altman Z-Score + Piotroski F-Score + A股特色检查
"""

from typing import Any


class RiskScreener:
    """风险筛查器"""

    def beneish_m(self, current: dict, prior: dict) -> dict:
        """
        Beneish M-Score 财务操纵检测

        M > -1.78 → 疑似财报操纵

        Args:
            current/prior: {
                "accounts_receivable", "revenue", "gross_margin",
                "intangible_assets", "total_assets",
                "net_income", "depreciation", "sga_expense",
                "current_liabilities", "long_term_debt", "cash",
                "operating_cash_flow"
            }
        """
        try:
            # DSRI = (AR_t/Rev_t) / (AR_t-1/Rev_t-1)
            ar_t = current.get("accounts_receivable", 0)
            rev_t = current.get("revenue", 0)
            ar_p = prior.get("accounts_receivable", 0)
            rev_p = prior.get("revenue", 0)
            dsri = (ar_t / rev_t) / (ar_p / rev_p) if rev_t > 0 and rev_p > 0 and ar_p > 0 else 1

            # GMI = GM_t-1 / GM_t
            gm_t = current.get("gross_margin", 0)
            gm_p = prior.get("gross_margin", 0)
            gmi = gm_p / gm_t if gm_t > 0 else 1

            # AQI = 无形资产占比变化
            ia_t = current.get("intangible_assets", 0)
            ta_t = current.get("total_assets", 0)
            ia_p = prior.get("intangible_assets", 0)
            ta_p = prior.get("total_assets", 0)
            aqi_t = ia_t / ta_t if ta_t > 0 else 0
            aqi_p = ia_p / ta_p if ta_p > 0 else 0
            aqi = aqi_t / aqi_p if aqi_p > 0 else 1

            # SGI = Rev_t / Rev_t-1
            sgi = rev_t / rev_p if rev_p > 0 else 1

            # DEPI = 折旧率变化
            dep_t = current.get("depreciation", 0)
            dep_p = prior.get("depreciation", 0)
            depr_t = dep_t / (dep_t + ta_t) if (dep_t + ta_t) > 0 else 0
            depr_p = dep_p / (dep_p + ta_p) if (dep_p + ta_p) > 0 else 0
            depi = depr_p / depr_t if depr_t > 0 else 1

            # SGAI = 管理费用率变化
            sga_t = current.get("sga_expense", 0)
            sga_p = prior.get("sga_expense", 0)
            sgai_t = sga_t / rev_t if rev_t > 0 else 0
            sgai_p = sga_p / rev_p if rev_p > 0 else 0
            sgai = sgai_t / sgai_p if sgai_p > 0 else 1

            # TATA = (NetIncome - OCF) / TotalAssets
            ni_t = current.get("net_income", 0)
            ocf_t = current.get("operating_cash_flow", 0)
            tata = (ni_t - ocf_t) / ta_t if ta_t > 0 else 0

            # LVGI = 杠杆率变化
            lev_t = (current.get("current_liabilities", 0) + current.get("long_term_debt", 0)) / ta_t if ta_t > 0 else 0
            lev_p = (prior.get("current_liabilities", 0) + prior.get("long_term_debt", 0)) / ta_p if ta_p > 0 else 0
            lvgi = lev_t / lev_p if lev_p > 0 else 1

            # M-Score
            m = (-4.84 + 0.92 * dsri + 0.528 * gmi + 0.404 * aqi + 0.892 * sgi
                 + 0.115 * depi - 0.172 * sgai + 4.679 * tata - 0.327 * lvgi)

            if m > -1.78:
                risk = "高风险"
                interpretation = "M-Score > -1.78，疑似财报操纵"
            else:
                risk = "低风险"
                interpretation = "M-Score 正常，未检测到操纵迹象"

            return {
                "m_score": round(m, 3),
                "risk": risk,
                "interpretation": interpretation,
                "components": {
                    "DSRI": round(dsri, 4), "GMI": round(gmi, 4),
                    "AQI": round(aqi, 4), "SGI": round(sgi, 4),
                    "DEPI": round(depi, 4), "SGAI": round(sgai, 4),
                    "TATA": round(tata, 4), "LVGI": round(lvgi, 4),
                },
            }

        except Exception as e:
            return {"error": f"Beneish M-Score 计算失败: {str(e)}", "m_score": None}

    def altman_z(self, working_capital: float, retained_earnings: float,
                 ebit: float, market_cap: float, total_liabilities: float,
                 total_assets: float, revenue: float) -> dict:
        """
        Altman Z-Score 破产预警

        Z > 2.99 = 安全区
        1.81 < Z < 2.99 = 灰色区
        Z < 1.81 = 困境区
        """
        if total_assets <= 0:
            return {"error": "总资产为0，无法计算", "z_score": None}

        x1 = working_capital / total_assets
        x2 = retained_earnings / total_assets
        x3 = ebit / total_assets
        x4 = market_cap / total_liabilities if total_liabilities > 0 else 0
        x5 = revenue / total_assets

        z = 1.2 * x1 + 1.4 * x2 + 3.3 * x3 + 0.6 * x4 + 1.0 * x5

        if z > 2.99:
            zone = "安全区"
            risk = "低"
        elif z > 1.81:
            zone = "灰色区"
            risk = "中"
        else:
            zone = "困境区"
            risk = "高"

        return {
            "z_score": round(z, 3),
            "zone": zone,
            "risk": risk,
            "components": {
                "X1_流动性": round(x1, 4),
                "X2_累积盈利": round(x2, 4),
                "X3_资产回报": round(x3, 4),
                "X4_杠杆容忍": round(x4, 4),
                "X5_周转效率": round(x5, 4),
            },
        }

    def piotroski_f(self, current: dict, prior: dict) -> dict:
        """
        Piotroski F-Score 财务健康9分制

        Args:
            current/prior: {
                "net_income", "total_assets", "operating_cash_flow",
                "long_term_debt", "current_assets", "current_liabilities",
                "shares_outstanding", "gross_margin", "revenue"
            }
        """
        score = 0
        details = {}

        # 1. ROA > 0
        roa_t = current.get("net_income", 0) / (current.get("total_assets") or 1)
        if roa_t > 0:
            score += 1
            details["ROA正"] = 1
        else:
            details["ROA正"] = 0

        # 2. OCF > 0
        ocf_t = current.get("operating_cash_flow", 0)
        if ocf_t > 0:
            score += 1
            details["OCF正"] = 1
        else:
            details["OCF正"] = 0

        # 3. ROA变化
        roa_p = prior.get("net_income", 0) / (prior.get("total_assets") or 1)
        if roa_t > roa_p:
            score += 1
            details["ROA上升"] = 1
        else:
            details["ROA上升"] = 0

        # 4. 盈利质量 (OCF > Net Income)
        if ocf_t > current.get("net_income", 0):
            score += 1
            details["盈利质量好"] = 1
        else:
            details["盈利质量好"] = 0

        # 5. 杠杆变化
        lev_t = current.get("long_term_debt", 0) / (current.get("total_assets") or 1)
        lev_p = prior.get("long_term_debt", 0) / (prior.get("total_assets") or 1)
        if lev_t < lev_p:
            score += 1
            details["杠杆下降"] = 1
        else:
            details["杠杆下降"] = 0

        # 6. 流动性变化
        cr_t = current.get("current_assets", 0) / (current.get("current_liabilities") or 1)
        cr_p = prior.get("current_assets", 0) / (prior.get("current_liabilities") or 1)
        if cr_t > cr_p:
            score += 1
            details["流动性改善"] = 1
        else:
            details["流动性改善"] = 0

        # 7. 未增发新股
        shares_t = current.get("shares_outstanding", 0)
        shares_p = prior.get("shares_outstanding", 0)
        if shares_t <= shares_p:
            score += 1
            details["未稀释"] = 1
        else:
            details["未稀释"] = 0

        # 8. 毛利率变化
        gm_t = current.get("gross_margin", 0)
        gm_p = prior.get("gross_margin", 0)
        if gm_t > gm_p:
            score += 1
            details["毛利率上升"] = 1
        else:
            details["毛利率上升"] = 0

        # 9. 资产周转率变化
        at_t = current.get("revenue", 0) / (current.get("total_assets") or 1)
        at_p = prior.get("revenue", 0) / (prior.get("total_assets") or 1)
        if at_t > at_p:
            score += 1
            details["周转率上升"] = 1
        else:
            details["周转率上升"] = 0

        if score >= 8:
            signal = "强买入"
        elif score >= 6:
            signal = "偏多"
        elif score >= 4:
            signal = "中性"
        elif score >= 2:
            signal = "偏空"
        else:
            signal = "强卖出"

        return {
            "f_score": score,
            "signal": signal,
            "details": details,
        }

    def a_share_checks(self, current: dict, prior: dict = None) -> dict:
        """
        A股特色8项检查

        Args:
            current: 当期财务数据
            prior: 上期财务数据（用于连续性检查）
        """
        checks = []
        red_count = 0
        yellow_count = 0

        rev = current.get("revenue", 0)
        ar = current.get("accounts_receivable", 0)
        ni = current.get("net_income", 0)
        ocf = current.get("operating_cash_flow", 0)
        goodwill = current.get("goodwill", 0)
        equity = current.get("shareholders_equity", 0)
        ta = current.get("total_assets", 0)
        tl = current.get("total_liabilities", 0)
        ca = current.get("current_assets", 0)
        cl = current.get("current_liabilities", 0)
        cash = current.get("cash_and_equivalents", 0)
        debt = current.get("total_debt", 0) or (current.get("long_term_debt", 0) + current.get("short_term_debt", 0))

        # 1. 应收/营收比
        ar_ratio = ar / rev * 100 if rev > 0 else 0
        if ar_ratio > 30:
            checks.append({"name": "应收/营收比", "value": f"{ar_ratio:.1f}%", "light": "红灯", "desc": "应收账款过高，可能虚增收入"})
            red_count += 1
        elif ar_ratio > 20:
            checks.append({"name": "应收/营收比", "value": f"{ar_ratio:.1f}%", "light": "黄灯", "desc": "应收账款偏高"})
            yellow_count += 1
        else:
            checks.append({"name": "应收/营收比", "value": f"{ar_ratio:.1f}%", "light": "绿灯", "desc": "正常"})

        # 2. 现金流/净利润
        ocf_ni_ratio = ocf / ni if ni > 0 else 999
        if ni > 0 and ocf_ni_ratio < 0.7:
            # 检查是否连续2年
            prior_ocf_ni = 1.0
            if prior:
                prior_ni = prior.get("net_income", 0)
                prior_ocf = prior.get("operating_cash_flow", 0)
                prior_ocf_ni = prior_ocf / prior_ni if prior_ni > 0 else 999
            if prior_ocf_ni < 0.7:
                checks.append({"name": "现金流/净利润", "value": f"{ocf_ni_ratio:.2f}", "light": "红灯", "desc": "连续2年现金流低于净利润，盈利质量差"})
                red_count += 1
            else:
                checks.append({"name": "现金流/净利润", "value": f"{ocf_ni_ratio:.2f}", "light": "黄灯", "desc": "现金流低于净利润"})
                yellow_count += 1
        else:
            checks.append({"name": "现金流/净利润", "value": f"{ocf_ni_ratio:.2f}", "light": "绿灯", "desc": "正常"})

        # 3. 商誉/净资产
        gw_ratio = goodwill / equity * 100 if equity > 0 else 0
        if gw_ratio > 30:
            checks.append({"name": "商誉/净资产", "value": f"{gw_ratio:.1f}%", "light": "红灯", "desc": "商誉减值风险大"})
            red_count += 1
        elif gw_ratio > 15:
            checks.append({"name": "商誉/净资产", "value": f"{gw_ratio:.1f}%", "light": "黄灯", "desc": "商誉占比偏高"})
            yellow_count += 1
        else:
            checks.append({"name": "商誉/净资产", "value": f"{gw_ratio:.1f}%", "light": "绿灯", "desc": "正常"})

        # 4. 资产负债率
        da_ratio = tl / ta * 100 if ta > 0 else 0
        if da_ratio > 70:
            checks.append({"name": "资产负债率", "value": f"{da_ratio:.1f}%", "light": "红灯", "desc": "负债过高"})
            red_count += 1
        elif da_ratio > 60:
            checks.append({"name": "资产负债率", "value": f"{da_ratio:.1f}%", "light": "黄灯", "desc": "负债偏高"})
            yellow_count += 1
        else:
            checks.append({"name": "资产负债率", "value": f"{da_ratio:.1f}%", "light": "绿灯", "desc": "正常"})

        # 5. 流动比率
        cr = ca / cl if cl > 0 else 0
        if cr < 1:
            checks.append({"name": "流动比率", "value": f"{cr:.2f}", "light": "红灯", "desc": "短期偿债能力不足"})
            red_count += 1
        elif cr < 1.5:
            checks.append({"name": "流动比率", "value": f"{cr:.2f}", "light": "黄灯", "desc": "短期偿债能力偏弱"})
            yellow_count += 1
        else:
            checks.append({"name": "流动比率", "value": f"{cr:.2f}", "light": "绿灯", "desc": "正常"})

        # 6. 存贷双高
        if cash > 0 and debt > 0:
            cash_ratio = cash / ta if ta > 0 else 0
            debt_ratio = debt / ta if ta > 0 else 0
            if cash_ratio > 0.15 and debt_ratio > 0.15:
                checks.append({"name": "存贷双高", "value": f"现金{cash_ratio*100:.0f}%/负债{debt_ratio*100:.0f}%", "light": "黄灯", "desc": "大存大贷，可能资金被占用"})
                yellow_count += 1
            else:
                checks.append({"name": "存贷双高", "value": "否", "light": "绿灯", "desc": "正常"})
        else:
            checks.append({"name": "存贷双高", "value": "否", "light": "绿灯", "desc": "正常"})

        # 7. 累计FCF（3年为负）
        fcf = ocf - current.get("capital_expenditure", 0)
        if fcf < 0:
            checks.append({"name": "自由现金流", "value": f"{fcf/1e8:.2f}亿", "light": "黄灯", "desc": "当期FCF为负"})
            yellow_count += 1
        else:
            checks.append({"name": "自由现金流", "value": f"{fcf/1e8:.2f}亿", "light": "绿灯", "desc": "正常"})

        # 8. 质押比例（从外部数据传入）
        pledge = current.get("pledge_ratio", 0)
        if pledge > 80:
            checks.append({"name": "质押比例", "value": f"{pledge:.1f}%", "light": "红灯", "desc": "质押极度危险"})
            red_count += 1
        elif pledge > 50:
            checks.append({"name": "质押比例", "value": f"{pledge:.1f}%", "light": "黄灯", "desc": "质押风险较高"})
            yellow_count += 1
        else:
            checks.append({"name": "质押比例", "value": f"{pledge:.1f}%", "light": "绿灯", "desc": "正常"})

        # 雷区评分
        risk_score = red_count * 20 + yellow_count * 8
        risk_score = min(risk_score, 100)

        return {
            "checks": checks,
            "red_count": red_count,
            "yellow_count": yellow_count,
            "green_count": len(checks) - red_count - yellow_count,
            "risk_score": risk_score,
            "risk_level": "极高" if risk_score > 60 else "高" if risk_score > 40 else "中" if risk_score > 20 else "低",
        }

    def comprehensive_risk_check(self, multi_period_data: list, market_data: dict,
                                  pledge_data: dict = None, market: str = "cn") -> dict:
        """
        综合风险排查

        Args:
            multi_period_data: 多期财务数据
            market_data: 市场数据
            pledge_data: 质押数据
        """
        if not multi_period_data or len(multi_period_data) < 2:
            return {"error": "需要至少2期财务数据"}

        current = {}
        prior = {}

        # 当期各表引用（Altman等需要）
        inc = multi_period_data[0].get("income_statement", {})
        bal = multi_period_data[0].get("balance_sheet", {})

        # 合并当期数据
        current.update(inc)
        current.update(bal)
        current.update(multi_period_data[0].get("cash_flow", {}))
        if pledge_data:
            current["pledge_ratio"] = pledge_data.get("pledge_ratio", 0)

        # 合并上期数据
        prior.update(multi_period_data[1].get("income_statement", {}))
        prior.update(multi_period_data[1].get("balance_sheet", {}))
        prior.update(multi_period_data[1].get("cash_flow", {}))

        # 计算派生字段（akshare原始数据不含这些，需从已有字段推算）
        for d in [current, prior]:
            rev = d.get("revenue", 0)
            cost = d.get("operating_cost", 0)
            if rev > 0 and "gross_margin" not in d:
                d["gross_margin"] = 1 - cost / rev
            if "operating_cash_flow" not in d:
                d["operating_cash_flow"] = d.get("net_cash_flow_from_operations", 0)
            if "sga_expense" not in d:
                d["sga_expense"] = d.get("selling_expense", 0) + d.get("admin_expense", 0)
            if "depreciation" not in d:
                ocf = d.get("net_cash_flow_from_operations", 0)
                ni = d.get("net_income", 0)
                d["depreciation"] = max(0, ocf - ni)
            if "shares_outstanding" not in d:
                d["shares_outstanding"] = d.get("outstanding_shares", 0)

        # Beneish M-Score
        try:
            beneish = self.beneish_m(current, prior)
        except Exception as e:
            beneish = {"error": str(e), "m_score": None}

        # Altman Z-Score
        try:
            market_cap = market_data.get("market_cap", 0)
            if market_cap == 0:
                market_cap = market_data.get("share_price", 0) * market_data.get("shares_outstanding", 0)
            altman = self.altman_z(
                working_capital=bal.get("working_capital", 0),
                retained_earnings=bal.get("shareholders_equity", 0) * 0.6,
                ebit=inc.get("operating_profit", 0) or inc.get("ebit", 0) or inc.get("operating_income", 0),
                market_cap=market_cap,
                total_liabilities=bal.get("total_liabilities", 0) or (bal.get("total_assets", 0) - bal.get("shareholders_equity", 0)),
                total_assets=bal.get("total_assets", 0),
                revenue=inc.get("revenue", 0),
            )
        except Exception as e:
            altman = {"error": str(e), "z_score": None}

        # Piotroski F-Score
        try:
            piotroski = self.piotroski_f(current, prior)
        except Exception as e:
            piotroski = {"error": str(e), "f_score": None}

        # A股特色检查（仅 A股;美股/港股跳过 —— 质押/北向/涨跌停等 A股专属指标不适用）
        if market == "cn":
            try:
                a_share = self.a_share_checks(current, prior)
            except Exception as e:
                a_share = {"error": str(e), "checks": [], "risk_score": 0}
        else:
            a_share = {"checks": [], "risk_score": 0, "skipped": f"{market} 不适用 A股特色检查"}

        # 综合风险评级
        total_risk = 0
        if beneish.get("m_score") and beneish["m_score"] > -1.78:
            total_risk += 25
        if altman.get("z_score") and altman["z_score"] < 1.81:
            total_risk += 25
        elif altman.get("z_score") and altman["z_score"] < 2.99:
            total_risk += 10
        total_risk += a_share["risk_score"] * 0.5

        return {
            "beneish_m": beneish,
            "altman_z": altman,
            "piotroski_f": piotroski,
            "a_share_checks": a_share,
            "total_risk_score": round(min(total_risk, 100), 1),
            "total_risk_level": "极高" if total_risk > 60 else "高" if total_risk > 40 else "中" if total_risk > 20 else "低",
        }
