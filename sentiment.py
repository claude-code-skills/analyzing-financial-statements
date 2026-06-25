"""
市场情绪分析模块
分析主力资金流向(A股)和社交媒体情绪(美股)
"""

from typing import Any


class SentimentAnalyzer:
    """市场情绪分析器"""

    def __init__(self, fetcher):
        self.fetcher = fetcher

    def analyze_fund_flow(self, symbol: str) -> dict[str, Any]:
        """
        分析主力资金流向 (A股)

        Returns:
            {
                "date": "日期",
                "main_net_inflow": 主力净流入(元),
                "main_net_inflow_ratio": 主力净占比(%),
                "super_large_inflow": 超大单净流入(元),
                "large_inflow": 大单净流入(元),
                "medium_inflow": 中单净流入(元),
                "small_inflow": 小单净流入(元),
                "trend_5d": "趋势描述",
                "sentiment_rating": "强/中/弱",
                "sentiment_score": 0-100,
                "data_type": "fund_flow"
            }
        """
        # 通过 fetcher 获取数据
        fund_data = self.fetcher.get_fund_flow(symbol)

        if "error" in fund_data:
            return fund_data

        latest = fund_data["latest"]
        trend = fund_data.get("trend", [])

        # 计算情绪评分
        score = self._calculate_sentiment_score(latest, trend)

        # 情绪评级
        main_inflow = latest.get("主力净流入-净额", 0)
        ratio = latest.get("主力净流入-净占比", 0)

        if main_inflow > 0 and ratio > 10:
            rating = "强"
        elif main_inflow > 0:
            rating = "偏强"
        elif main_inflow < 0 and ratio < -10:
            rating = "弱"
        else:
            rating = "中性"

        return {
            "date": str(latest.get("日期", "")),
            "main_net_inflow": main_inflow,
            "main_net_inflow_ratio": ratio,
            "super_large_inflow": latest.get("超大单净流入-净额", 0),
            "large_inflow": latest.get("大单净流入-净额", 0),
            "medium_inflow": latest.get("中单净流入-净额", 0),
            "small_inflow": latest.get("小单净流入-净额", 0),
            "trend_5d": self._get_trend_description(trend),
            "sentiment_rating": rating,
            "sentiment_score": score,
            "data_type": "fund_flow"
        }

    def analyze_social_sentiment(self, symbol: str, market: str = "cn") -> dict[str, Any]:
        """
        分析市场情绪 (支持 A股和美股)

        Args:
            symbol: 股票代码
            market: cn=A股, us=美股

        Returns:
            A股: 返回资金流向分析
            美股: 返回社交媒体情绪分析
        """
        if market == "cn":
            return self.analyze_fund_flow(symbol)

        # 美股社交媒体情绪分析
        social_data = self.fetcher.get_social_sentiment(symbol)

        if "error" in social_data:
            return social_data

        latest = social_data["latest"]
        trend = social_data.get("trend", [])
        mentions_trend = social_data.get("mentions_trend", [])

        # 计算情绪评分
        score = self._calculate_social_score(latest, trend, mentions_trend)

        # 情绪评级
        sentiment = latest.get("sentiment", 0)
        positive_ratio = latest.get("positiveRatio", 0.5)

        if sentiment > 0.2 and positive_ratio > 0.6:
            rating = "强"
        elif sentiment > 0:
            rating = "偏强"
        elif sentiment < -0.2 and positive_ratio < 0.4:
            rating = "弱"
        else:
            rating = "中性"

        return {
            "date": str(latest.get("date", "")),
            "sentiment": sentiment,           # -1到1
            "social_score": latest.get("socialScore", 50),  # 0-100
            "mentions": latest.get("mentions", 0),
            "positive_ratio": positive_ratio,
            "negative_ratio": latest.get("negativeRatio", 0.5),
            "trend_5d": self._get_social_trend_description(trend),
            "sentiment_rating": rating,
            "sentiment_score": score,
            "data_type": "social"
        }

    def _calculate_sentiment_score(self, latest: dict, trend: list) -> float:
        """
        A股情绪面评分 0-100

        算法:
        - 基础分 50
        - 主力净流入 > 0 → +10分
        - 每增加1亿 → +2分 (最多+30)
        - 连续3日净流入 → +20分
        - 连续3日净流出 → -20分
        """
        score = 50

        main_inflow = latest.get("主力净流入-净额", 0)
        ratio = latest.get("主力净流入-净占比", 0)

        if main_inflow > 0:
            score += 10
            # 每亿+2分，最多+30
            score += min(abs(main_inflow) / 1e8 * 2, 30)
        else:
            score -= 10
            score -= min(abs(main_inflow) / 1e8 * 2, 30)

        # 趋势加分
        if len(trend) >= 3:
            positive_days = sum(1 for t in trend[:3] if t > 0)
            negative_days = sum(1 for t in trend[:3] if t < 0)
            if positive_days == 3:
                score += 20  # 连续3日净流入
            elif negative_days == 3:
                score -= 20  # 连续3日净流出

        return max(0, min(100, score))

    def _calculate_social_score(self, latest: dict, trend: list, mentions_trend: list) -> float:
        """
        美股社交媒体情绪评分 0-100

        算法:
        - 基础分 50
        - sentiment > 0 → +20分
        - positiveRatio > 0.6 → +15分
        - 社交评分高 → 按比例加分
        - 提及量增加 → +10分
        """
        score = 50

        sentiment = latest.get("sentiment", 0)
        positive_ratio = latest.get("positiveRatio", 0.5)
        social_score = latest.get("socialScore", 50)

        # sentiment (-1到1)
        if sentiment > 0:
            score += 20
            score += min(sentiment * 30, 20)  # 最多+20
        else:
            score -= 20
            score += max(sentiment * 30, -20)  # 最多-20

        # positive_ratio (0到1)
        if positive_ratio > 0.6:
            score += 15
        elif positive_ratio < 0.4:
            score -= 15

        # social_score (0到100)
        score += (social_score - 50) * 0.3

        # mentions trend
        if len(mentions_trend) >= 2:
            if mentions_trend[0] > mentions_trend[-1] * 1.5:
                score += 10  # 提及量显著增加

        return max(0, min(100, score))

    def _get_trend_description(self, trend: list) -> str:
        """获取A股资金流向趋势描述"""
        if not trend:
            return "数据不足"

        recent = trend[:5]
        positive = sum(1 for t in recent if t > 0)

        if positive >= 4:
            return "持续流入"
        elif positive >= 3:
            return "流入为主"
        elif positive <= 1:
            return "持续流出"
        else:
            return "震荡"

    def _get_social_trend_description(self, trend: list) -> str:
        """获取美股社交媒体趋势描述"""
        if not trend:
            return "数据不足"

        recent = trend[:5]
        positive = sum(1 for t in recent if t > 0)

        if positive >= 4:
            return "持续正面"
        elif positive >= 3:
            return "正面为主"
        elif positive <= 1:
            return "持续负面"
        else:
            return "震荡"
