"""PE/PB 历史百分位纯计算测试(注入固定序列,断言百分位与档位)。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from valuation import ValuationAnalyzer


def test_percentile_basic():
    v = ValuationAnalyzer()
    # range(10,20) = 10 个值,当前 12 → 小于 12 的有 2 个 → 20% 低估
    r = v.pe_pb_percentile(list(range(10, 20)), [], 12, 0)
    assert r["pe_percentile"] == 20.0
    assert r["pe_status"] == "低估"
    # 当前 19 → 90% 高估
    r2 = v.pe_pb_percentile(list(range(10, 20)), [], 19, 0)
    assert r2["pe_percentile"] == 90.0
    assert r2["pe_status"] == "高估"
    # 当前 15 → 50% 适中
    r3 = v.pe_pb_percentile(list(range(10, 20)), [], 15, 0)
    assert r3["pe_percentile"] == 50.0
    assert r3["pe_status"] == "适中"


def test_percentile_filters_invalid():
    v = ValuationAnalyzer()
    # 负值/零被过滤:有效 [10,20],当前 12 → 1/2 = 50%
    r = v.pe_pb_percentile([-5, 0, 10, 20], [], 12, 0)
    assert r["pe_percentile"] == 50.0


def test_percentile_none_cases():
    v = ValuationAnalyzer()
    # 无历史 → None
    assert v.pe_pb_percentile([], [], 15, 0)["pe_percentile"] is None
    # 当前 PE <=0 → None(无法定位)
    assert v.pe_pb_percentile([10, 20], [], 0, 0)["pe_percentile"] is None
    # 全无效历史 → None
    assert v.pe_pb_percentile([-1, 0], [], 15, 0)["pe_percentile"] is None


def test_pb_percentile():
    v = ValuationAnalyzer()
    # pb=[1,2,3,4,5],当前 1.5 → 小于 1.5 的有 1 个 → 20%
    r = v.pe_pb_percentile([10, 20], [1, 2, 3, 4, 5], 15, 1.5)
    assert r["pb_percentile"] == 20.0
    assert r["pb_status"] == "低估"
