"""定投(DCA)XIRR 回报分布 + 定投 vs 满仓 纯计算测试(注入固定价格序列)。"""
import os
import sys

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from holdings import holding_returns, TRADING_DAYS
from dca import dca_returns, dca_summary, dca_vs_lumpsum, analyze_dca


def test_dca_returns_short_series():
    # 序列短于持有窗口 → 空数组(1 年=250 点,序列不足)
    assert len(dca_returns([1, 2, 3], years=1)) == 0


def test_dca_xirr_monotonic_up():
    # 单调上行(每年翻倍):定投每笔都赚资产增长率(100%/年)→ XIRR≈100%
    # 验证多笔现金流被正确折现(旧公式此处给 55.6%,系统性低估)
    n = TRADING_DAYS
    closes = [100 * (2 ** (i / n)) for i in range(n * 5 + 1)]
    rets = dca_returns(closes, years=5)
    assert len(rets) > 0
    assert abs(float(rets.mean()) - 1.0) < 0.05  # 平均 XIRR≈100%


def test_dca_summary_monotonic_up():
    # 单调上行:定投 XIRR≈100%、必不亏(每笔都赚资产增长率)
    n = TRADING_DAYS
    closes = [100 * (2 ** (i / n)) for i in range(n * 5 + 1)]
    s = dca_summary(closes, years_list=(1,))
    assert s[1] is not None
    assert s[1]["samples"] > 0
    assert s[1]["prob_no_loss"] == 100.0
    assert abs(s[1]["median_cagr"] - 100.0) < 5  # XIRR≈资产增长率,非旧公式的 ~55%


def test_monotonic_up_dca_equals_lumpsum():
    # 单调上行:每笔投入的边际收益率 = 资产增长率 → 定投 XIRR ≈ 满仓 XIRR(持平)
    # 关键:不是「满仓赢」(旧错误公式 + 旧断言的结论),而是持平
    n = TRADING_DAYS
    closes = [100 * (2 ** (i / n)) for i in range(n * 5 + 1)]
    r = dca_vs_lumpsum(closes)
    assert abs(r["dca_cagr"] - r["lumpsum_cagr"]) < 2  # 两者都≈100%
    assert r["winner"] == "持平"


def test_dca_beats_lumpsum_smile():
    # 微笑曲线:1.0 → 0.5(前半段跌)→ 1.0(后半段涨回)。定投低位多买 → 定投 XIRR 赢
    n = 5 * TRADING_DAYS + 1
    half = n // 2
    closes = [1.0 * (0.5 ** (i / half)) if i < half
              else 0.5 * (2.0 ** ((i - half) / (n - half)))
              for i in range(n)]
    r = dca_vs_lumpsum(closes)
    assert r["winner"] == "定投"
    assert r["dca_cagr"] > r["lumpsum_cagr"]
    assert r["smile_advantage"] > 0
    s = dca_summary(closes, years_list=(5,))
    assert s[5] is not None and s[5]["samples"] > 0


def test_flat_series_draw():
    # 平坦序列:定投 = 满仓 = 0 → 持平
    r = dca_vs_lumpsum([100] * (5 * TRADING_DAYS + 1))
    assert r["dca_cagr"] == 0.0
    assert r["lumpsum_cagr"] == 0.0
    assert r["winner"] == "持平"
    assert r["smile_advantage"] == 0.0


def test_window_count_matches_holdings():
    # 同一根序列,dca 与 holdings 每个 years 窗口数必须相等(同边界 range(len-n))
    closes = [100 + i * 0.1 for i in range(2600)]
    for y in (3, 5, 10):
        h = holding_returns(closes, y)          # 返回 list
        d = dca_returns(closes, y)             # 返回 ndarray
        assert len(h) == len(d), f"years={y}: holdings={len(h)} dca={len(d)}"


def test_empty_and_single():
    assert len(dca_returns([], 1)) == 0
    assert dca_vs_lumpsum([]) == {}
    assert analyze_dca([])["empty"] is True
    assert analyze_dca([100])["empty"] is True
