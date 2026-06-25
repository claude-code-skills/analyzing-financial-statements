"""Tests for comprehensive_score module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from comprehensive_score import ComprehensiveScorer


class TestCalculateOverallScore:
    def setup_method(self):
        self.scorer = ComprehensiveScorer()

    def _good_data(self):
        return {
            "fundamental": {"quality": {"score": 7}},
            "valuation": {"safety_margin": {"safety_margin": 25}, "dividend_yield": 3},
            "technical": {"timing_signal": "buy", "confidence": 70},
            "sentiment": {"composite_score": 65},
            "risk": {"total_risk_score": 15},
            "market_temp": {"composite_score": 60},
        }

    def _bad_data(self):
        return {
            "fundamental": {"quality": {"score": 2}},
            "valuation": {"safety_margin": {"safety_margin": -20}, "dividend_yield": 0},
            "technical": {"timing_signal": "sell", "confidence": 30},
            "sentiment": {"composite_score": 25},
            "risk": {"total_risk_score": 70},
            "market_temp": {"composite_score": 20},
        }

    def test_good_stock(self):
        result = self.scorer.calculate_overall_score(self._good_data())
        assert "overall_score" in result
        assert "rating" in result
        assert "scores" in result
        assert "recommendation" in result
        assert result["overall_score"] >= 60
        assert result["rating"] in ("优秀", "良好")

    def test_none_sentiment_excluded(self):
        """sentiment 无效(美股降级 composite_score=None)→ 排除并重新归一化,overall 基于剩余维度。"""
        data = self._good_data()
        data["sentiment"] = {"composite_score": None}
        r = self.scorer.calculate_overall_score(data)
        assert "sentiment" not in r["scores"]   # None 维度排除
        assert r["overall_score"] > 0            # 剩余维度归一化仍出分

    def test_bad_stock(self):
        result = self.scorer.calculate_overall_score(self._bad_data())
        assert result["overall_score"] < 50

    def test_empty_data(self):
        result = self.scorer.calculate_overall_score({})
        assert result["overall_score"] == 50  # All defaults

    def test_weights_sum_to_one(self):
        total = sum(self.scorer.WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_recommendation_action(self):
        result = self.scorer.calculate_overall_score(self._good_data())
        assert "action" in result["recommendation"]
        assert "confidence" in result["recommendation"]


class TestScoreFundamental:
    def setup_method(self):
        self.scorer = ComprehensiveScorer()

    def test_high_quality(self):
        score = self.scorer._score_fundamental({"quality": {"score": 8}})
        assert score == 100  # 8*10+20=100

    def test_low_quality(self):
        score = self.scorer._score_fundamental({"quality": {"score": 0}})
        assert score == 20  # 0*10+20=20

    def test_empty(self):
        score = self.scorer._score_fundamental({})
        assert score == 50


class TestScoreValuation:
    def setup_method(self):
        self.scorer = ComprehensiveScorer()

    def test_deep_value(self):
        score = self.scorer._score_valuation({"safety_margin": {"safety_margin": 40}})
        assert score == 90

    def test_overvalued(self):
        score = self.scorer._score_valuation({"safety_margin": {"safety_margin": -20}})
        assert score == 20

    def test_dividend_bonus(self):
        score = self.scorer._score_valuation({
            "safety_margin": {"safety_margin": 0}, "dividend_yield": 5
        })
        assert score == 55  # base 40 (margin=0 falls in >-15 branch) + 15 bonus for >=5% dividend

    def test_empty(self):
        score = self.scorer._score_valuation({})
        assert score == 50


class TestScoreTechnical:
    def setup_method(self):
        self.scorer = ComprehensiveScorer()

    def test_strong_buy(self):
        score = self.scorer._score_technical({"timing_signal": "strong_buy", "confidence": 80})
        assert score > 80

    def test_strong_sell(self):
        score = self.scorer._score_technical({"timing_signal": "strong_sell", "confidence": 20})
        assert score < 20

    def test_hold(self):
        score = self.scorer._score_technical({"timing_signal": "hold", "confidence": 50})
        assert abs(score - 50.0) < 0.1


class TestETFScoring:
    def setup_method(self):
        self.scorer = ComprehensiveScorer()

    def test_etf_score(self):
        data = {
            "technical": {"timing_signal": "buy", "confidence": 65},
            "sentiment": {"composite_score": 60},
            "premium": {"premium_rate": 1.5, "price": 2.5, "iopv": 2.46},
        }
        result = self.scorer.calculate_etf_score(data)
        assert "overall_score" in result
        assert "rating" in result
        assert "recommendation" in result

    def test_etf_weights(self):
        total = sum(self.scorer.ETF_WEIGHTS.values())
        assert abs(total - 1.0) < 0.001

    def test_premium_scoring(self):
        assert self.scorer._score_etf_premium({"premium_rate": -1}) == 90
        assert self.scorer._score_etf_premium({"premium_rate": 1}) == 75
        assert self.scorer._score_etf_premium({"premium_rate": 4}) == 50
        assert self.scorer._score_etf_premium({"premium_rate": 7}) == 30
        assert self.scorer._score_etf_premium({"premium_rate": 15}) == 10


class TestRecommendation:
    def setup_method(self):
        self.scorer = ComprehensiveScorer()

    def test_left_side_attention(self):
        """High dividend + anomalous year + overvalued → 左侧关注."""
        data = {
            "fundamental": {"quality": {"score": 5}},
            "valuation": {
                "safety_margin": {"safety_margin": -5, "fair_value": 100, "current_price": 105},
                "dividend_yield": 5,
                "valuation_signals": {"anomalous_year": True},
                "scenario_analysis": {},
            },
            "technical": {"timing_signal": "hold", "confidence": 50},
            "sentiment": {"composite_score": 40},
            "risk": {"total_risk_score": 30},
            "market_temp": {"composite_score": 40},
        }
        result = self.scorer.calculate_overall_score(data)
        assert result["recommendation"]["action"] == "左侧关注"

    def test_build_position(self):
        """Large safety margin + buy signal → 建仓."""
        data = {
            "fundamental": {"quality": {"score": 7}},
            "valuation": {
                "safety_margin": {"safety_margin": 35, "fair_value": 150, "current_price": 100},
                "dividend_yield": 1,
                "valuation_signals": {"anomalous_year": False},
                "scenario_analysis": {},
            },
            "technical": {"timing_signal": "buy", "confidence": 70},
            "sentiment": {"composite_score": 60},
            "risk": {"total_risk_score": 10},
            "market_temp": {"composite_score": 55},
        }
        result = self.scorer.calculate_overall_score(data)
        assert result["recommendation"]["action"] == "建仓"
