"""定投(Dollar Cost Averaging)回报分布 + 定投 vs 满仓对比(纯 numpy,基于收盘价序列)。

与 holdings.py 互补:holdings 回答「满仓持有 N 年的滚动分布」,dca 回答
「每月定投、持有 N 年的滚动分布」——分批摊低成本,在「先跌后涨(微笑曲线)」
体验优于满仓,在单边上行逊于满仓。给长期价值投资者判断「定投划不划算」。
输入收盘价序列(应为前复权,避免除权扭曲)。

年化口径:定投是多笔不同时点的现金流,用 XIRR(资金时间价值标准)——
对每笔投入按其真实时点折现。满仓(holdings)是单笔,几何年化即其 XIRR,
故两模块结果口径一致、可直接并排对比。
(旧版误用 (市值/投入)^(1/年) 把多笔当单笔,系统性低估约一半,已弃。)"""

import numpy as np

TRADING_DAYS = 250                   # 与 holdings.py 同值(年交易日近似)
INVEST_PERIOD = TRADING_DAYS // 12   # 每月一次 ≈ 20 个交易日


def dca_returns(closes: list, years: int) -> np.ndarray:
    """所有「月定投 + 持有 years 年」窗口的定投 XIRR(年化,小数,0.1=10%)。
    模型:从窗口起点起,每 INVEST_PERIOD 个交易日投入等额现金(相对值 1.0/期,
    金额不影响 XIRR),用当日收盘价买入;期末按收盘价清仓。
    XIRR 对每笔现金流按其投入时点折现(多笔现金流的标准年化)。
    不足(序列长度 <= years*TRADING_DAYS)→ 空数组。"""
    n = int(years * TRADING_DAYS)
    c = np.array([float(x) for x in closes if x and x > 0], dtype=float)
    if len(c) <= n:
        return np.array([])
    inv = 1.0 / c
    ks = np.arange(0, n + 1, INVEST_PERIOD)         # 买入偏移(交易日),含 0 含 n
    ks_years = ks / TRADING_DAYS                     # 买入时点(年,相对窗口起点)
    starts = np.arange(0, len(c) - n)                # 每个窗口起点 (W,)
    shares = inv[starts[:, None] + ks[None, :]].sum(axis=1)  # 每窗口累计份额 (W,)
    mv = shares * c[starts + n]                      # 每窗口期末市值 (W,)
    # 向量化二分求 XIRR:NPV_i(r) = -Σ_j(1+r)^(-ks_years_j) + mv_i·(1+r)^(-years) = 0
    # Σ_j(1+r)^(-ks_years_j) 对所有窗口同形(ks_years 固定),但 mid 每窗口不同 → 逐窗口算
    lo = np.full(len(starts), -0.99)
    hi = np.full(len(starts), 100.0)
    for _ in range(80):
        mid = (lo + hi) * 0.5
        S = np.sum((1.0 + mid)[:, None] ** (-ks_years[None, :]), axis=1)  # Σ_j (W,)
        npv = -S + mv * (1.0 + mid) ** (-years)                          # (W,)
        lower = npv > 0   # NPV>0 → r 偏低 → 抬 lo
        lo = np.where(lower, mid, lo)
        hi = np.where(~lower, mid, hi)
    return (lo + hi) * 0.5


def dca_summary(closes: list, years_list=(3, 5, 10)) -> dict:
    """各持有期的定投 XIRR 分布(中位/最坏/最好)+ 不亏概率。不足 → 该 years 为 None。"""
    summary = {}
    for y in years_list:
        rets = dca_returns(closes, y)
        if len(rets) == 0:
            summary[y] = None
            continue
        summary[y] = {
            "median_cagr": round(float(np.median(rets)) * 100, 1),
            "worst_cagr": round(float(rets.min()) * 100, 1),
            "best_cagr": round(float(rets.max()) * 100, 1),
            "prob_no_loss": round(float((rets > 0).mean()) * 100, 1),
            "samples": int(len(rets)),
        }
    return summary


def dca_vs_lumpsum(closes: list) -> dict:
    """整条序列上「定投 vs 满仓」XIRR 单条对照(非滚动分布,样本数=1):
    从序列起点月定投到终点 vs 起点满仓到终点,各算 XIRR,比较谁占优。
    满仓单笔 XIRR =(终点/起点)^(1/年数)-1(解析);定投多笔 XIRR 数值二分求解。
    不足 2 个买入点(序列极短)→ {}。
    注:全周期为单一样本,易被起止点主导,仅供直觉参考;
    看概率应参考 dca_summary 的滚动分布(横截面统计)。"""
    c = np.array([float(x) for x in closes if x and x > 0], dtype=float)
    if len(c) < INVEST_PERIOD + 1:      # 至少能定投 2 次
        return {}
    idx = np.arange(0, len(c), INVEST_PERIOD)      # 全周期买入点 [0,20,...,末]
    shares = (1.0 / c[idx]).sum()
    mv = shares * c[-1]
    years_full = (len(c) - 1) / TRADING_DAYS       # 区间数,与 (end/c0) 口径一致
    times = idx / TRADING_DAYS
    # 定投 XIRR(标量二分):NPV(r) = -Σ(1+r)^(-t_j) + mv·(1+r)^(-years_full)
    lo, hi = -0.99, 100.0
    for _ in range(100):
        mid = (lo + hi) * 0.5
        npv = -float(np.sum((1.0 + mid) ** (-times))) + mv * (1.0 + mid) ** (-years_full)
        if npv > 0:
            lo = mid
        else:
            hi = mid
    dca_cagr = (lo + hi) * 0.5
    lumpsum_cagr = float((c[-1] / c[0]) ** (1.0 / years_full) - 1.0)
    diff = float(dca_cagr) - lumpsum_cagr
    winner = "定投" if diff > 1e-4 else ("满仓" if diff < -1e-4 else "持平")  # 1bp 阈值避浮点噪声
    return {
        "dca_cagr": round(float(dca_cagr) * 100, 1),
        "lumpsum_cagr": round(lumpsum_cagr * 100, 1),
        "winner": winner,
        "smile_advantage": round(diff * 100, 1),   # 定投 XIRR − 满仓 XIRR(pp)
    }


def analyze_dca(closes: list) -> dict:
    """一键:定投滚动 XIRR 分布 + 定投 vs 满仓对照。closes 为空 → {empty: True}。"""
    if not closes or len(closes) < 2:
        return {"empty": True}
    return {
        "dca_periods": dca_summary(closes),
        "vs_lumpsum": dca_vs_lumpsum(closes),
        "data_points": len(closes),
    }
