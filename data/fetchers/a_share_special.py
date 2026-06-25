"""
A股特色数据获取器
akshare直调，覆盖MCP不支持的A股特有数据
"""

import os
import time
from datetime import datetime, timedelta
from typing import Any

os.environ['NO_PROXY'] = '*'

import akshare as ak
import pandas as pd
import numpy as np


class AShareSpecialFetcher:
    """A股特色数据（龙虎榜/北向/融资融券/涨跌停/宏观）"""

    def __init__(self):
        self._rate_limit_delay = 0.3
        self._last_request_time = 0

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

    def get_dragon_tiger(self, symbol: str, days: int = 30) -> dict:
        """
        龙虎榜数据
        返回：近N日上榜次数、机构净买入、上榜后收益
        """
        try:
            self._rate_limit()
            end_date = datetime.now().strftime("%Y%m%d")
            start_date = (datetime.now() - timedelta(days=days)).strftime("%Y%m%d")
            df = ak.stock_lhb_detail_em(start_date=start_date, end_date=end_date)

            if df is None or df.empty:
                return {"count": 0, "data": []}

            # 筛选目标股票
            stock_data = df[df["代码"].astype(str) == symbol]
            if stock_data.empty:
                return {"count": 0, "data": []}

            records = []
            for _, row in stock_data.iterrows():
                records.append({
                    "date": str(row.get("上榜日期", "")),
                    "reason": str(row.get("解读", row.get("上榜原因", ""))),
                    "net_buy": self._safe_float(row.get("龙虎榜净买额", 0)),
                    "pct_change": self._safe_float(row.get("涨跌幅", 0)),
                    "return_1d": self._safe_float(row.get("上榜后1日", 0)),
                    "return_5d": self._safe_float(row.get("上榜后5日", 0)),
                    "return_10d": self._safe_float(row.get("上榜后10日", 0)),
                })

            return {"count": len(records), "data": records}

        except Exception as e:
            return {"error": f"龙虎榜数据获取失败: {str(e)}", "count": 0}

    def get_northbound_flow(self, symbol: str) -> dict:
        """
        个股北向资金持股变动
        返回：持股数、持股市值、持股占比、增减持
        """
        try:
            self._rate_limit()
            df = ak.stock_hsgt_individual_em(symbol=symbol)

            if df is None or df.empty:
                return {"error": "无北向资金数据"}

            latest = df.iloc[0]
            return {
                "date": str(latest.get("日期", "")),
                "shares_held": self._safe_float(latest.get("持股数", 0)),
                "market_value": self._safe_float(latest.get("持股市值", 0)),
                "holding_ratio": self._safe_float(latest.get("持股占比", 0)),
                "change_shares": self._safe_float(latest.get("增减持数", 0)),
                "change_value": self._safe_float(latest.get("增减持资金", 0)),
            }

        except Exception as e:
            return {"error": f"北向资金获取失败: {str(e)}"}

    def get_northbound_summary(self) -> dict:
        """
        北向资金整体流向（当日/5日/10日累计）
        """
        try:
            self._rate_limit()
            df = ak.stock_hsgt_hist_em(symbol="北向资金")

            if df is None or df.empty:
                return {"error": "无北向资金汇总数据"}

            # 取最近5日
            recent = df.head(5)
            daily_flows = []
            for _, row in recent.iterrows():
                daily_flows.append({
                    "date": str(row.get("日期", "")),
                    "net_buy": self._safe_float(row.get("当日净买额", 0)),
                    "cumulative": self._safe_float(row.get("累计净买额", 0)),
                    "market_value": self._safe_float(row.get("持股市值", 0)),
                })

            sum_5d = sum(d["net_buy"] for d in daily_flows)

            return {
                "latest": daily_flows[0] if daily_flows else {},
                "sum_5d": sum_5d,
                "trend": "inflow" if sum_5d > 0 else "outflow",
                "daily": daily_flows,
            }

        except Exception as e:
            return {"error": f"北向资金汇总获取失败: {str(e)}"}

    def get_margin_data(self, symbol: str) -> dict:
        """
        融资融券数据
        """
        try:
            self._rate_limit()
            # 判断市场
            if symbol.startswith(('6',)):
                df = ak.stock_margin_detail_sse(date=datetime.now().strftime("%Y%m%d"))
            else:
                df = ak.stock_margin_detail_szse(date=datetime.now().strftime("%Y%m%d"))

            if df is None or df.empty:
                return {"error": "无融资融券数据"}

            # 查找目标股票
            code_col = "标的证券代码" if "标的证券代码" in df.columns else "证券代码"
            stock_data = df[df[code_col].astype(str) == symbol]
            if stock_data.empty:
                return {"error": f"{symbol} 无融资融券数据"}

            latest = stock_data.iloc[0]
            return {
                "margin_balance": self._safe_float(latest.get("融资余额", latest.get("融资余额(元)", 0))),
                "margin_buy": self._safe_float(latest.get("融资买入额", latest.get("融资买入额(元)", 0))),
                "short_balance": self._safe_float(latest.get("融券余额", latest.get("融券余额(元)", 0))),
                "short_volume": self._safe_float(latest.get("融券余量", 0)),
            }

        except Exception as e:
            return {"error": f"融资融券获取失败: {str(e)}"}

    def get_price_limit_pool(self, date: str = None) -> dict:
        """
        涨跌停池
        返回：涨停/跌停数量、封板成功率
        """
        if date is None:
            date = datetime.now().strftime("%Y%m%d")

        try:
            self._rate_limit()
            df = ak.stock_zt_pool_em(date=date)

            zt_count = 0
            if df is not None and not df.empty:
                zt_count = len(df)

            return {
                "date": date,
                "limit_up_count": zt_count,
                "data": df.head(10).to_dict("records") if df is not None and not df.empty else [],
            }

        except Exception as e:
            return {"error": f"涨跌停池获取失败: {str(e)}", "limit_up_count": 0}

    def get_macro_snapshot(self) -> dict:
        """
        宏观经济快照：CPI/PMI/GDP/LPR最新值
        """
        result = {}

        # CPI
        try:
            self._rate_limit()
            df = ak.macro_china_cpi_yearly()
            if df is not None and not df.empty:
                latest = df.iloc[0]
                result["cpi"] = {
                    "value": self._safe_float(latest.get("今值", 0)),
                    "forecast": self._safe_float(latest.get("预测", 0)),
                    "previous": self._safe_float(latest.get("前值", 0)),
                }
        except Exception:
            result["cpi"] = {"error": "获取失败"}

        # PMI
        try:
            self._rate_limit()
            df = ak.macro_china_pmi_yearly()
            if df is not None and not df.empty:
                latest = df.iloc[0]
                result["pmi"] = {
                    "value": self._safe_float(latest.get("今值", 0)),
                    "forecast": self._safe_float(latest.get("预测", 0)),
                    "previous": self._safe_float(latest.get("前值", 0)),
                }
        except Exception:
            result["pmi"] = {"error": "获取失败"}

        # GDP
        try:
            self._rate_limit()
            df = ak.macro_china_gdp_yearly()
            if df is not None and not df.empty:
                latest = df.iloc[0]
                result["gdp"] = {
                    "value": self._safe_float(latest.get("今值", 0)),
                    "forecast": self._safe_float(latest.get("预测", 0)),
                    "previous": self._safe_float(latest.get("前值", 0)),
                }
        except Exception:
            result["gdp"] = {"error": "获取失败"}

        # LPR
        try:
            self._rate_limit()
            df = ak.macro_china_lpr()
            if df is not None and not df.empty:
                latest = df.iloc[0]
                result["lpr"] = {
                    "lpr_1y": self._safe_float(latest.get("LPR1Y", 0)),
                    "lpr_5y": self._safe_float(latest.get("LPR5Y", 0)),
                }
        except Exception:
            result["lpr"] = {"error": "获取失败"}

        return result

    def get_pledge_data(self, symbol: str) -> dict:
        """
        股票质押数据
        返回：质押比例、质押笔数
        """
        try:
            self._rate_limit()
            df = ak.stock_gpledge_em(symbol=symbol)

            if df is None or df.empty:
                return {"pledge_ratio": 0, "pledge_count": 0, "status": "无质押"}

            latest = df.iloc[0]
            pledge_ratio = self._safe_float(latest.get("质押比例", 0))

            if pledge_ratio > 80:
                status = "极度危险"
            elif pledge_ratio > 50:
                status = "高风险"
            elif pledge_ratio > 30:
                status = "中等"
            else:
                status = "安全"

            return {
                "pledge_ratio": pledge_ratio,
                "pledge_count": int(self._safe_float(latest.get("质押笔数", 0))),
                "status": status,
            }

        except Exception as e:
            return {"error": f"质押数据获取失败: {str(e)}", "pledge_ratio": 0}
