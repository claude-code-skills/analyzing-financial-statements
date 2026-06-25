"""长期持有期回报 + 回撤体验(纯 pandas/numpy,基于收盘价序列)。

长期价值投资者最关心的:持有 3/5/10 年的年化收益分布(最坏情况)、
不亏钱概率、历史最大回撤与恢复时长 —— 决定「拿不拿得住」。
输入收盘价序列(应为前复权,避免除权扭曲)。"""

import numpy as np

TRADING_DAYS = 250  # 年交易日近似(A股~244、美股~252)


def holding_returns(closes: list, years: int) -> list:
    """所有「持有 years 年」窗口的年化收益率(小数,0.1=10%)序列。不足 → []。"""
    n = int(years * TRADING_DAYS)
    c = [float(x) for x in closes if x and x > 0]
    if len(c) <= n:
        return []
    return [(c[i + n] / c[i]) ** (1 / years) - 1 for i in range(len(c) - n)]


def holding_summary(closes: list, years_list=(3, 5, 10)) -> dict:
    """各持有期的年化收益分布(中位/最坏/最好)+ 不亏概率。"""
    summary = {}
    for y in years_list:
        rets = holding_returns(closes, y)
        if not rets:
            summary[y] = None
            continue
        arr = np.array(rets)
        summary[y] = {
            "median_cagr": round(float(np.median(arr)) * 100, 1),
            "worst_cagr": round(float(arr.min()) * 100, 1),
            "best_cagr": round(float(arr.max()) * 100, 1),
            "prob_no_loss": round(float((arr > 0).mean()) * 100, 1),
            "samples": len(arr),
        }
    return summary


def max_drawdown(closes: list) -> dict:
    """最大回撤(%)+ 恢复天数(跌至谷底后回到前期高点所用工夫)。未恢复 → None。"""
    c = [float(x) for x in closes if x and x > 0]
    if len(c) < 2:
        return {}
    arr = np.array(c)
    running_max = np.maximum.accumulate(arr)
    dd = (arr - running_max) / running_max  # 负值序列
    max_dd = float(dd.min())
    max_dd_idx = int(dd.argmin())
    peak = running_max[max_dd_idx]
    recovery = None
    for j in range(max_dd_idx + 1, len(arr)):
        if arr[j] >= peak:
            recovery = j - max_dd_idx
            break
    return {
        "max_drawdown": round(max_dd * 100, 1),
        "recovery_days": recovery,
        "recovery_years": round(recovery / TRADING_DAYS, 1) if recovery else None,
    }


def analyze_holdings(closes: list) -> dict:
    """一键:持有期分布 + 最大回撤。closes 为空 → {empty: True}。"""
    if not closes or len(closes) < 2:
        return {"empty": True}
    return {
        "holding_periods": holding_summary(closes),
        "drawdown": max_drawdown(closes),
        "data_points": len(closes),
    }
