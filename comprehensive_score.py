"""
综合评分系统 v2 — 六维一体评分
基本面/估值/技术面/情绪面/风控/市场温度
"""

from typing import Any


class ComprehensiveScorer:
    """六维综合评分系统"""

    WEIGHTS = {
        "fundamental": 0.25,   # 基本面（杜邦ROE质量）
        "valuation": 0.20,     # 估值（DCF安全边际 + 相对估值）
        "technical": 0.15,     # 技术面（多指标共振）
        "sentiment": 0.20,     # 情绪面（资金流向 + 北向）
        "risk": 0.10,          # 风控（雷区评分反向）
        "market_temp": 0.10,   # 市场温度（恐贪指数）
    }

    def calculate_overall_score(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        计算综合评分 0-100

        Args:
            data: {
                "fundamental": 杜邦分析结果,
                "valuation": 估值分析结果,
                "technical": 技术面数据,
                "sentiment": 情绪面数据,
                "risk": 风控数据,
                "market_temp": 市场温度数据
            }
        """
        scores = {}

        scores["fundamental"] = self._score_fundamental(data.get("fundamental", {}))
        scores["valuation"] = self._score_valuation(data.get("valuation", {}))
        scores["technical"] = self._score_technical(data.get("technical", {}))
        scores["sentiment"] = self._score_sentiment(data.get("sentiment", {}))
        scores["risk"] = self._score_risk(data.get("risk", {}))
        scores["market_temp"] = self._score_market_temp(data.get("market_temp", {}))

        # 无效维度(None,如美股 sentiment 降级)排除并重新归一化权重
        valid = {k: v for k, v in scores.items() if v is not None}
        total_weight = sum(self.WEIGHTS[k] for k in valid)
        overall = sum(valid[k] * self.WEIGHTS[k] for k in valid) / total_weight if total_weight else 50

        if overall >= 80:
            rating = "优秀"
        elif overall >= 60:
            rating = "良好"
        elif overall >= 40:
            rating = "一般"
        else:
            rating = "较差"

        return {
            "overall_score": round(overall, 1),
            "rating": rating,
            "scores": {k: round(v, 1) for k, v in scores.items() if v is not None},
            "weights": self.WEIGHTS,
            "recommendation": self._generate_recommendation(overall, data, scores),
        }

    def _score_fundamental(self, fundamental: dict) -> float:
        """基本面评分（基于杜邦分析）"""
        if not fundamental:
            return 50

        quality = fundamental.get("quality", {})
        score = quality.get("score", 0) * 10  # 0-8 → 0-80
        return max(0, min(100, score + 20))  # 保底20分

    def _score_valuation(self, valuation: dict) -> float:
        """估值评分（安全边际 + 股息率加分）"""
        if not valuation:
            return 50

        safety = valuation.get("safety_margin", {})
        margin = safety.get("safety_margin", 0)
        dividend_yield = valuation.get("dividend_yield", 0)

        # 基础分
        if margin > 30:
            base = 90
        elif margin > 15:
            base = 75
        elif margin > 0:
            base = 60
        elif margin > -15:
            base = 40
        else:
            base = 20

        # 股息率加分
        if dividend_yield >= 5:
            base = min(100, base + 15)
        elif dividend_yield >= 3:
            base = min(100, base + 8)

        return base

    def _score_technical(self, technical: dict) -> float:
        """技术面评分（基于多指标共振）"""
        if not technical:
            return 50

        timing = technical.get("timing_signal", "hold")
        confidence = technical.get("confidence", 50)

        signal_score = {
            "strong_buy": 90, "buy": 75, "hold": 50,
            "sell": 25, "strong_sell": 10,
        }.get(timing, 50)

        return signal_score * 0.7 + confidence * 0.3

    def _score_sentiment(self, sentiment: dict) -> float | None:
        """情绪面评分。composite_score 为 None(美股/港股降级)→ 返回 None,综合评分排除该维度。"""
        if not sentiment:
            return 50

        # 如果是7维情绪综合指标（美股降级时 composite_score=None）
        if "composite_score" in sentiment:
            return sentiment["composite_score"]

        # 兼容旧格式
        return sentiment.get("sentiment_score", 50)

    def _score_risk(self, risk: dict) -> float:
        """风控评分（雷区评分反向：越危险分越低）"""
        if not risk:
            return 50

        risk_score = risk.get("total_risk_score", 0)
        return max(0, 100 - risk_score)

    def _score_market_temp(self, market_temp: dict) -> float:
        """市场温度评分"""
        if not market_temp:
            return 50

        if "composite_score" in market_temp:
            return market_temp["composite_score"]

        return 50

    def _generate_recommendation(self, overall: float, data: dict, scores: dict) -> dict:
        """生成操作建议（含赔率决策树）"""
        valuation = data.get("valuation", {})
        safety = valuation.get("safety_margin", {})
        margin = safety.get("safety_margin", 0)
        dividend_yield = valuation.get("dividend_yield", 0)
        is_anomalous = valuation.get("valuation_signals", {}).get("anomalous_year", False)
        scenario = valuation.get("scenario_analysis", {})

        technical = data.get("technical", {})
        timing = technical.get("timing_signal", "hold")

        # 价值分歧区：DCF说高估 + 高股息 + 异常年 → 可能错杀
        if margin < 0 and dividend_yield >= 4 and is_anomalous:
            action = "左侧关注"
            confidence = "中"
        elif margin < 0 and dividend_yield >= 5:
            action = "逢低关注"
            confidence = "中"
        elif margin > 30 and timing in ("buy", "strong_buy"):
            action = "建仓"
            confidence = "高"
        elif margin > 30 and timing == "hold":
            action = "等待买点"
            confidence = "中高"
        elif margin > 15 and timing in ("buy", "strong_buy"):
            action = "加仓"
            confidence = "中高"
        elif margin < 0 and timing in ("sell", "strong_sell"):
            action = "减仓"
            confidence = "高"
        elif margin < -15:
            action = "规避"
            confidence = "高"
        elif overall >= 60:
            action = "持有"
            confidence = "中"
        elif overall >= 40:
            action = "观望"
            confidence = "中"
        else:
            action = "减持"
            confidence = "中"

        # 目标价和止损价
        fair_value = safety.get("fair_value", 0)
        current_price = safety.get("current_price", 0)

        if action in ("建仓", "加仓", "持有", "等待买点", "观望", "左侧关注", "逢低关注"):
            target_price = fair_value
            stop_loss = current_price * 0.92 if current_price > 0 else 0
        else:
            target_price = None
            stop_loss = None

        # 周期建议
        if scores.get("technical", 50) > 70:
            horizon = "短线 (1-2周)"
        elif scores.get("fundamental", 50) > 70:
            horizon = "长线 (6-12月)"
        else:
            horizon = "中线 (1-3月)"

        result = {
            "action": action,
            "confidence": confidence,
            "target_price": round(target_price, 2) if target_price else None,
            "stop_loss": round(stop_loss, 2) if stop_loss else None,
            "time_horizon": horizon,
            "safety_margin": f"{margin:.1f}%",
            "timing_signal": timing,
        }

        # 情景分析赔率信息
        if scenario and scenario.get("scenarios"):
            expected = scenario.get("expected_value", 0)
            upside = scenario.get("upside", 0)
            downside = scenario.get("downside", 0)
            if current_price > 0:
                result["scenario_odds"] = {
                    "expected_value": expected,
                    "upside_target": upside,
                    "downside_floor": downside,
                    "upside_pct": round((upside - current_price) / current_price * 100, 1) if upside > 0 else 0,
                    "downside_pct": round((downside - current_price) / current_price * 100, 1) if downside > 0 else 0,
                }

        return result

    # ── ETF 专用评分 ──

    ETF_WEIGHTS = {
        "technical": 0.35,   # 技术面（ETF最核心，多指标共振）
        "sentiment": 0.30,   # 情绪面（恐贪指数+资金流向）
        "premium": 0.35,     # 溢价风险（高溢价=高风险，反向评分）
    }

    def calculate_etf_score(self, data: dict[str, Any]) -> dict[str, Any]:
        """
        ETF 专用评分：技术面 + 情绪面 + 溢价风险
        """
        scores = {}
        scores["technical"] = self._score_technical(data.get("technical", {}))
        scores["sentiment"] = self._score_sentiment(data.get("sentiment", {}))
        scores["premium"] = self._score_etf_premium(data.get("premium", {}))

        overall = sum(
            scores[k] * self.ETF_WEIGHTS[k] for k in self.ETF_WEIGHTS
        )

        if overall >= 75:
            rating = "优秀"
        elif overall >= 55:
            rating = "良好"
        elif overall >= 35:
            rating = "一般"
        else:
            rating = "较差"

        return {
            "overall_score": round(overall, 1),
            "rating": rating,
            "scores": {k: round(v, 1) for k, v in scores.items() if v is not None},
            "weights": self.ETF_WEIGHTS,
            "recommendation": self._generate_etf_recommendation(overall, data, scores),
        }

    def _score_etf_premium(self, premium_data: dict) -> float:
        """溢价风险评分（溢价越高分数越低）"""
        rate = premium_data.get("premium_rate", 0)
        if rate <= 0:
            return 90   # 折价，非常安全
        elif rate <= 2:
            return 75   # 正常
        elif rate <= 5:
            return 50   # 中等风险
        elif rate <= 8:
            return 30   # 较高风险
        else:
            return 10   # 高风险

    def _generate_etf_recommendation(self, overall: float, data: dict, scores: dict) -> dict:
        """ETF 操作建议"""
        premium = data.get("premium", {})
        premium_rate = premium.get("premium_rate", 0)
        technical = data.get("technical", {})
        timing = technical.get("timing_signal", "hold")

        if premium_rate > 5 and timing in ("sell", "strong_sell"):
            action = "减仓"
            confidence = "高"
        elif premium_rate > 5:
            action = "不追高"
            confidence = "高"
        elif premium_rate < 2 and timing in ("buy", "strong_buy"):
            action = "建仓"
            confidence = "高"
        elif premium_rate < 2 and timing == "hold":
            action = "等待买点"
            confidence = "中"
        elif overall >= 60:
            action = "持有"
            confidence = "中"
        elif overall >= 40:
            action = "观望"
            confidence = "中"
        else:
            action = "减持"
            confidence = "中高"

        price = premium.get("price", 0)
        iopv = premium.get("iopv", 0)

        return {
            "action": action,
            "confidence": confidence,
            "premium_rate": f"{premium_rate}%",
            "premium_risk": "高" if premium_rate > 5 else "中" if premium_rate > 2 else "低",
            "timing_signal": timing,
            "stop_loss": round(price * 0.95, 3) if price > 0 else None,
            "fair_value_ref": iopv if iopv > 0 else None,
        }
