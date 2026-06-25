"""持有期回报 + 回撤体验 纯计算测试(注入固定价格序列)。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holdings import holding_returns, holding_summary, max_drawdown, analyze_holdings


def test_holding_returns_short_series():
    # 序列短于持有窗口 → 空
    assert holding_returns([1, 2, 3], years=1) == []  # 1 年=250 点,序列不足


def test_holding_summary_synthetic():
    # 每 250 天翻倍 → 持有 1 年年化 ~100%
    n = 250
    closes = [100 * (2 ** (i / n)) for i in range(n * 5 + 1)]
    s = holding_summary(closes, years_list=(1,))
    assert s[1] is not None
    assert abs(s[1]["median_cagr"] - 100.0) < 5
    assert s[1]["prob_no_loss"] == 100.0  # 单调上行,全不亏


def test_max_drawdown_unrecovered():
    # 100→120→80→110:峰值120,谷底80,回撤 −33.3%,110 未回 120 → 未恢复
    dd = max_drawdown([100, 120, 80, 110])
    assert dd["max_drawdown"] == -33.3
    assert dd["recovery_days"] is None


def test_max_drawdown_recovered():
    # 100→120→80→130:回到 130>120,谷底 idx=2 → 恢复 1 天
    dd = max_drawdown([100, 120, 80, 130])
    assert dd["max_drawdown"] == -33.3
    assert dd["recovery_days"] == 1
    assert dd["recovery_years"] is not None


def test_empty_and_single():
    assert holding_returns([], 1) == []
    assert max_drawdown([]) == {}
    assert max_drawdown([100]) == {}
    assert analyze_holdings([])["empty"] is True
    assert analyze_holdings([100])["empty"] is True
