"""
新闻获取模块
获取并分析股票相关新闻 (支持 A股和美股)
"""

from typing import Any


class NewsFetcher:
    """新闻获取器"""

    def __init__(self, fetcher):
        self.fetcher = fetcher

    def get_latest_news(self, symbol: str, limit: int = 5) -> dict[str, Any]:
        """获取最新新闻"""
        return self.fetcher.get_news(symbol, limit)

    def analyze_news_sentiment(self, news_data: dict, market: str = "cn") -> dict[str, Any]:
        """
        分析新闻情绪 (支持 A股和美股)

        Args:
            news_data: 新闻数据
            market: cn=A股, us=美股
        """
        if "error" in news_data:
            return {"error": news_data["error"]}

        news_list = news_data.get("news", [])

        if not news_list:
            return {
                "score": 70,  # 中性
                "count": 0,
                "latest": "",
                "sentiment": "neutral"
            }

        # 根据市场选择关键词
        if market == "cn":
            positive_keywords = ["回购", "增持", "利好", "突破", "上涨", "增长", "盈利", "分红"]
            negative_keywords = ["减持", "利空", "下跌", "下滑", "亏损", "风险", "调查", "诉讼"]
        else:  # us
            positive_keywords = [
                "buy", "upgrade", "beat", "growth", "profit", "dividend",
                "surge", "rally", "bullish", "strong", "record", "expansion"
            ]
            negative_keywords = [
                "sell", "downgrade", "miss", "loss", "decline", "drop",
                "plunge", "bearish", "weak", "layoff", "lawsuit", "investigation"
            ]

        positive_count = 0
        negative_count = 0

        latest_news = news_list[0]["title"] if news_list else ""

        for news in news_list:
            title = news.get("title", "").lower()
            text = news.get("text", "").lower()

            content = title + " " + text

            for keyword in positive_keywords:
                if keyword.lower() in content:
                    positive_count += 1
            for keyword in negative_keywords:
                if keyword.lower() in content:
                    negative_count += 1

        # 计算情绪评分
        base_score = 70
        score = base_score + positive_count * 5 - negative_count * 10
        score = max(0, min(100, score))

        # 判断情绪
        if score >= 80:
            sentiment = "positive"
        elif score <= 50:
            sentiment = "negative"
        else:
            sentiment = "neutral"

        return {
            "score": round(score),
            "count": len(news_list),
            "latest": latest_news,
            "sentiment": sentiment,
            "positive_count": positive_count,
            "negative_count": negative_count
        }
