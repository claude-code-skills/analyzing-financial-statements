"""
市场情绪综合指标模块
7维加权合成：恐贪+杠杆+外资+资金+热度+估值+散户
ETF专属增强：份额变动+溢折价+指数PE分位
"""

import os
import time
from typing import Any

os.environ['NO_PROXY'] = '*'

import numpy as np

try:
    import akshare as ak
    HAS_AKSHARE = True
except ImportError:
    HAS_AKSHARE = False

from data.fetchers.etf import ETFFetcher


class SentimentIndexAnalyzer:
    """市场情绪综合指标分析器"""

    # 维度权重
    WEIGHTS = {
        "fear_greed": 0.20,    # 恐贪指数
        "leverage": 0.15,      # 融资杠杆
        "northbound": 0.15,    # 北向资金
        "fund_flow": 0.15,     # 主力资金
        "limit_up": 0.15,      # 涨跌停热度
        "valuation": 0.10,     # 估值百分位
        "retail": 0.10,        # 散户行为
    }

    def __init__(self):
        self._rate_limit_delay = 0.3
        self._last_request_time = 0
        self._etf_fetcher = ETFFetcher()

    def _rate_limit(self):
        now = time.time()
        elapsed = now - self._last_request_time
        if elapsed < self._rate_limit_delay:
            time.sleep(self._rate_limit_delay - elapsed)
        self._last_request_time = time.time()

    def _safe_float(self, value: Any) -> float:
        if value is None or value == '' or value == '--':
            return 0.0
        try:
            v = float(value)
            return 0.0 if np.isnan(v) or np.isinf(v) else v
        except (TypeError, ValueError):
            return 0.0

    def _normalize_to_100(self, value: float, min_val: float, max_val: float) -> float:
        """标准化到0-100"""
        if max_val == min_val:
            return 50
        return max(0, min(100, (value - min_val) / (max_val - min_val) * 100))

    # ─────────────────────────────────────────────
    # 各维度指标获取
    # ─────────────────────────────────────────────

    def _get_fear_greed(self) -> dict:
        """恐贪指数（韭圈儿）"""
        try:
            self._rate_limit()
            df = ak.index_fear_greed_funddb()
            if df is not None and not df.empty:
                latest = df.iloc[0]
                value = self._safe_float(latest.get("恐贪指数", latest.get("数值", 50)))
                return {
                    "value": round(value, 1),
                    "score": round(value, 1),  # 直接0-100
                    "status": "极度恐惧" if value < 25 else "恐惧" if value < 45 else "中性" if value < 55 else "贪婪" if value < 75 else "极度贪婪",
                }
        except Exception:
            pass
        return {"value": 50, "score": 50, "status": "未知", "error": "恐贪指数获取失败"}

    def _get_leverage(self) -> dict:
        """融资余额变化"""
        try:
            self._rate_limit()
            df_sse = ak.stock_margin_sse(start_date="", end_date="")
            if df_sse is not None and not df_sse.empty:
                recent = df_sse.head(5)
                if len(recent) >= 2:
                    latest = self._safe_float(recent.iloc[0].get("融资余额", 0))
                    prev = self._safe_float(recent.iloc[-1].get("融资余额", 0))
                    if prev > 0:
                        change_rate = (latest - prev) / prev * 100
                        score = self._normalize_to_100(change_rate, -2, 2)
                        return {
                            "change_rate": round(change_rate, 2),
                            "score": round(score, 1),
                            "status": "加杠杆" if change_rate > 0.5 else "减杠杆" if change_rate < -0.5 else "平稳",
                        }
        except Exception:
            pass
        return {"change_rate": 0, "score": 50, "status": "未知", "error": "融资数据获取失败"}

    def _get_northbound(self) -> dict:
        """北向资金5日累计"""
        try:
            self._rate_limit()
            df = ak.stock_hsgt_hist_em(symbol="北向资金")
            if df is not None and not df.empty:
                recent = df.head(5)
                flows = [self._safe_float(row.get("当日净买额", 0)) for _, row in recent.iterrows()]
                sum_5d = sum(flows)
                # 标准化：500亿=100分，-500亿=0分
                score = self._normalize_to_100(sum_5d / 1e8, -500, 500)
                return {
                    "sum_5d_yi": round(sum_5d / 1e8, 2),
                    "score": round(score, 1),
                    "status": "大幅流入" if sum_5d > 200e8 else "流入" if sum_5d > 0 else "流出" if sum_5d > -200e8 else "大幅流出",
                }
        except Exception:
            pass
        return {"sum_5d_yi": 0, "score": 50, "status": "未知", "error": "北向资金获取失败"}

    def _get_fund_flow(self) -> dict:
        """主力资金净流入"""
        try:
            self._rate_limit()
            df = ak.stock_market_fund_flow()
            if df is not None and not df.empty:
                latest = df.iloc[0]
                net_inflow = self._safe_float(latest.get("主力净流入-净额", 0))
                # 标准化
                score = self._normalize_to_100(net_inflow / 1e8, -200, 200)
                return {
                    "net_inflow_yi": round(net_inflow / 1e8, 2),
                    "score": round(score, 1),
                    "status": "主力流入" if net_inflow > 0 else "主力流出",
                }
        except Exception:
            pass
        return {"net_inflow_yi": 0, "score": 50, "status": "未知", "error": "主力资金获取失败"}

    def _get_limit_up(self) -> dict:
        """涨跌停热度"""
        try:
            self._rate_limit()
            from datetime import datetime
            date = datetime.now().strftime("%Y%m%d")
            df = ak.stock_zt_pool_em(date=date)
            zt_count = len(df) if df is not None and not df.empty else 0

            # 涨跌停比 → 标准化
            # 通常A股涨停20-100只，跌停0-50只
            score = self._normalize_to_100(zt_count, 10, 100)
            return {
                "limit_up_count": zt_count,
                "score": round(score, 1),
                "status": "火热" if zt_count > 80 else "偏热" if zt_count > 50 else "正常" if zt_count > 20 else "冷清",
            }
        except Exception:
            pass
        return {"limit_up_count": 0, "score": 50, "status": "未知", "error": "涨跌停数据获取失败"}

    def _get_valuation_percentile(self) -> dict:
        """沪深300PE历史百分位"""
        try:
            self._rate_limit()
            df = ak.stock_a_indicator_lg(symbol="000300")
            if df is not None and not df.empty:
                pe = self._safe_float(df.iloc[0].get("pe", 0))
                pe_values = df["pe"].dropna()
                if len(pe_values) > 0 and pe > 0:
                    percentile = (pe_values < pe).sum() / len(pe_values) * 100
                    # 逆向：百分位低=低估=高分（买入机会）
                    score = 100 - percentile
                    return {
                        "pe": round(pe, 2),
                        "percentile": round(percentile, 1),
                        "score": round(score, 1),
                        "status": "低估" if percentile < 30 else "合理" if percentile < 70 else "高估",
                    }
        except Exception:
            pass
        return {"pe": 0, "percentile": 50, "score": 50, "status": "未知", "error": "估值数据获取失败"}

    def _get_retail(self) -> dict:
        """散户行为（新基金发行规模，逆向指标）"""
        try:
            self._rate_limit()
            df = ak.fund_new_found_em()
            if df is not None and not df.empty:
                # 近4周发行规模
                recent = df.head(20)  # 近1个月
                total = sum(self._safe_float(row.get("募集份额", 0)) for _, row in recent.iterrows())
                # 发行冰点=高分=机会，发行火热=低分=风险
                score = self._normalize_to_100(total / 1e8, 0, 500)
                score = 100 - score  # 逆向
                return {
                    "new_fund_yi": round(total / 1e8, 2),
                    "score": round(score, 1),
                    "status": "发行冰点" if score > 70 else "偏冷" if score > 50 else "偏热" if score > 30 else "发行火热",
                }
        except Exception:
            pass
        return {"new_fund_yi": 0, "score": 50, "status": "未知", "error": "新基金数据获取失败"}

    # ─────────────────────────────────────────────
    # 综合情绪指标
    # ─────────────────────────────────────────────

    def analyze_market_sentiment(self, market: str = "cn") -> dict:
        """
        7维市场情绪综合分析（仅 A股;美股/港股的 A股大盘指标不适用 → 降级）

        Returns:
            综合情绪分（0-100）+ 各维度分项 + 情绪趋势
        """
        if market != "cn":
            return {
                "composite_score": None,
                "level": "暂不支持",
                "advice": f"{market} 个股情绪面暂仅支持 A股(融资/北向/涨跌停为 A股大盘指标),参考估值历史百分位段",
                "dimensions": {},
                "weights": self.WEIGHTS,
            }
        dimensions = {}

        dimensions["fear_greed"] = self._get_fear_greed()
        dimensions["leverage"] = self._get_leverage()
        dimensions["northbound"] = self._get_northbound()
        dimensions["fund_flow"] = self._get_fund_flow()
        dimensions["limit_up"] = self._get_limit_up()
        dimensions["valuation"] = self._get_valuation_percentile()
        dimensions["retail"] = self._get_retail()

        # 加权合成
        total_score = 0
        total_weight = 0
        for dim_name, weight in self.WEIGHTS.items():
            if dim_name in dimensions and "score" in dimensions[dim_name]:
                total_score += dimensions[dim_name]["score"] * weight
                total_weight += weight

        composite_score = total_score / total_weight if total_weight > 0 else 50

        # 情绪等级
        if composite_score < 25:
            level = "极度恐惧"
            advice = "买入机会（别人恐惧时贪婪）"
        elif composite_score < 45:
            level = "偏冷"
            advice = "可以逐步建仓"
        elif composite_score < 55:
            level = "中性"
            advice = "观望为主"
        elif composite_score < 75:
            level = "偏热"
            advice = "注意控制仓位"
        else:
            level = "极度贪婪"
            advice = "风险警示（别人贪婪时恐惧）"

        return {
            "composite_score": round(composite_score, 1),
            "level": level,
            "advice": advice,
            "dimensions": dimensions,
            "weights": self.WEIGHTS,
        }

    def analyze_etf_sentiment(self, symbol: str) -> dict:
        """
        ETF专属情绪增强
        跨境ETF：只用恐贪指数+溢折价（A股情绪维度不适用）
        国内ETF：A股大盘情绪+指数PE分位
        """
        CROSS_BORDER = {"NDX", "KWEB", "SPX", "HSTECH", "HSI", "N225", "SENSEX"}
        index_map = {
            # 国内ETF
            "510300": "000300", "510500": "000905", "159915": "399006",
            "510050": "000016",
            # 跨境ETF
            "159941": "NDX", "513100": "NDX", "159509": "NDX",
            "513050": "KWEB", "164906": "KWEB",
            "513010": "HSI", "159920": "HSTECH", "513030": "HSTECH",
            "513520": "N225", "159932": "N225",
            "164824": "SENSEX",
        }
        index_code = index_map.get(symbol, "")
        is_cross_border = index_code in CROSS_BORDER
        # 兜底：未映射的513xxx（上海跨境ETF）按跨境处理
        if not index_code and symbol.startswith("513"):
            is_cross_border = True

        etf_data = {}

        # 溢折价（三通道降级：雪球 → 东财 → 新浪）
        try:
            rt = self._etf_fetcher.get_etf_realtime(symbol)
            if rt and "error" not in rt:
                etf_data["premium_rate"] = self._safe_float(rt.get("premium_rate", 0))
                etf_data["iopv"] = self._safe_float(rt.get("iopv", 0))
                etf_data["price"] = self._safe_float(rt.get("price", 0))
        except Exception:
            pass

        if is_cross_border:
            # 跨境ETF：只用恐贪指数+溢折价，跳过A股特有维度
            dimensions = {}
            dimensions["fear_greed"] = self._get_fear_greed()
            # 溢折价作为情绪维度
            premium = self._safe_float(etf_data.get("premium_rate", 0))
            premium_score = self._normalize_to_100(premium, -2, 8)
            dimensions["premium"] = {
                "premium_rate": round(premium, 2),
                "score": round(premium_score, 1),
                "status": "高溢价" if premium > 5 else "溢价" if premium > 2 else "折价" if premium < -2 else "正常",
            }
            # 加权合成
            weights = {"fear_greed": 0.70, "premium": 0.30}
            total_score = sum(dimensions[d]["score"] * w for d, w in weights.items() if d in dimensions)
            composite_score = round(total_score, 1)
            if composite_score < 25:
                level, advice = "极度恐惧", "买入机会"
            elif composite_score < 45:
                level, advice = "偏冷", "可以逐步建仓"
            elif composite_score < 55:
                level, advice = "中性", "观望为主"
            elif composite_score < 75:
                level, advice = "偏热", "注意控制仓位"
            else:
                level, advice = "极度贪婪", "风险警示，不宜追高"
            result = {
                "composite_score": composite_score,
                "level": level,
                "advice": advice,
                "dimensions": dimensions,
                "weights": weights,
                "etf_data": etf_data,
                "is_cross_border": True,
            }
            return result

        # 国内ETF：A股大盘情绪 + 指数PE分位
        result = self.analyze_market_sentiment()

        if index_code:
            try:
                self._rate_limit()
                df = ak.stock_a_indicator_lg(symbol=index_code)
                if df is not None and not df.empty:
                    pe = self._safe_float(df.iloc[0].get("pe", 0))
                    pb = self._safe_float(df.iloc[0].get("pb", 0))
                    pe_values = df["pe"].dropna()
                    pe_pct = (pe_values < pe).sum() / len(pe_values) * 100 if len(pe_values) > 0 and pe > 0 else 50
                    etf_data["index_pe"] = pe
                    etf_data["index_pb"] = pb
                    etf_data["index_pe_percentile"] = round(pe_pct, 1)
            except Exception:
                pass

        result["etf_data"] = etf_data
        result["is_cross_border"] = False
        return result
