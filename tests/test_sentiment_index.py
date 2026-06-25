"""sentiment_index 美股/港股降级测试(不联网,只验降级标记)。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sentiment_index import SentimentIndexAnalyzer


def test_non_cn_degrades_to_none():
    """美股/港股不应跑 A股大盘指标(融资/北向/涨跌停)→ composite_score=None,综合评分排除。"""
    s = SentimentIndexAnalyzer()
    for m in ("us", "hk"):
        r = s.analyze_market_sentiment(market=m)
        assert r["composite_score"] is None
        assert r["level"] == "暂不支持"
        assert r["dimensions"] == {}
