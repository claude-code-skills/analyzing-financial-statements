"""
港股数据获取器
主通道：腾讯财经(gtimg)，备选：新浪(akshare)
东方财富push2/push2his对港股secid不返回数据，已弃用
"""

import time
from datetime import datetime, timedelta
from typing import Any

import akshare as ak
import numpy as np
import pandas as pd
import requests


class HKShareFetcher:
    """港股数据获取"""

    def __init__(self):
        self._rate_limit_delay = 0.3
        self._last_request_time = 0
        self._session = requests.Session()
        self._session.headers.update({"User-Agent": "Mozilla/5.0"})

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

    def _fetch_kline_tencent(self, symbol: str, period: int) -> pd.DataFrame:
        """腾讯财经K线（主通道）"""
        self._rate_limit()
        url = "https://web.ifzq.gtimg.cn/appstock/app/fqkline/get"
        params = {
            "param": f"hk{symbol},day,,,{min(period + 30, 500)},qfq",
        }
        r = self._session.get(url, params=params, timeout=15)
        data = r.json()
        stock_data = data.get("data")
        if not isinstance(stock_data, dict):
            return pd.DataFrame()
        klines = stock_data.get(f"hk{symbol}", {}).get("qfqday") or []
        if not klines:
            klines = stock_data.get(f"hk{symbol}", {}).get("day") or []
        if not klines:
            return pd.DataFrame()

        # gtimg格式: [date, open, close, high, low, volume]（有时多出第7列，截取前6列）
        df = pd.DataFrame([k[:6] for k in klines],
                          columns=["日期", "开盘", "收盘", "最高", "最低", "成交量"])
        for col in ["开盘", "收盘", "最高", "最低", "成交量"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期").tail(period).reset_index(drop=True)
        df["成交额"] = 0.0
        df["振幅"] = 0.0
        df["涨跌幅"] = 0.0
        df["涨跌额"] = 0.0
        df["换手率"] = 0.0
        return df

    def _fetch_kline_sina(self, symbol: str, period: int) -> pd.DataFrame:
        """新浪K线（备选通道）"""
        self._rate_limit()
        df = ak.stock_hk_daily(symbol=symbol, adjust="")
        if df is None or df.empty:
            return pd.DataFrame()
        # 新浪列名: date, open, high, low, close, volume
        df = df.rename(columns={
            "date": "日期", "open": "开盘", "close": "收盘",
            "high": "最高", "low": "最低", "volume": "成交量",
        })
        for col in ["开盘", "收盘", "最高", "最低", "成交量"]:
            df[col] = pd.to_numeric(df[col], errors="coerce")
        df["日期"] = pd.to_datetime(df["日期"])
        df = df.sort_values("日期").tail(period).reset_index(drop=True)
        df["成交额"] = 0.0
        df["振幅"] = 0.0
        df["涨跌幅"] = 0.0
        df["涨跌额"] = 0.0
        df["换手率"] = 0.0
        return df

    def get_history(self, symbol: str, period: int = 100) -> pd.DataFrame:
        """
        获取港股历史行情
        返回 DataFrame: 日期, 开盘, 收盘, 最高, 最低, 成交量
        """
        for fetcher in [self._fetch_kline_tencent, self._fetch_kline_sina]:
            try:
                df = fetcher(symbol, period)
                if df is not None and not df.empty:
                    return df
            except Exception:
                continue
        return pd.DataFrame()

    def get_pe_pb_history(self, symbol: str, years: int = 10) -> dict | None:
        """港股 PE/PB 历史:数据源待补,暂返回 None(降级,不假装有估值)。"""
        return None

    def get_adjusted_closes(self, symbol: str, period: int = 4000) -> list:
        """港股前复权收盘(复用 get_history,腾讯源已是 qfq)。失败 → []。"""
        try:
            df = self.get_history(symbol, period=period)
            if df is None or df.empty:
                return []
            return df["收盘"].astype(float).tolist()
        except Exception:
            return []

    def get_history_with_indicators(self, symbol: str, period: int = 100) -> pd.DataFrame:
        """
        获取港股历史行情 + pandas-ta技术指标
        """
        df = self.get_history(symbol, period)
        if df.empty:
            return df

        try:
            import pandas_ta as ta
        except ImportError:
            return df

        col_map = {
            "日期": "Date", "开盘": "Open", "收盘": "Close",
            "最高": "High", "最低": "Low", "成交量": "Volume",
        }
        df_ta = df.rename(columns=col_map)
        df_ta["Date"] = pd.to_datetime(df_ta["Date"])
        df_ta.set_index("Date", inplace=True)

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df_ta[col] = pd.to_numeric(df_ta[col], errors="coerce")

        df_ta.ta.macd(fast=12, slow=26, signal=9, append=True)
        df_ta.ta.rsi(length=14, append=True)
        df_ta.ta.stoch(k=3, d=3, append=True)
        df_ta.ta.bbands(length=20, std=2, append=True)
        df_ta.ta.obv(append=True)
        df_ta.ta.atr(length=14, append=True)

        df_ta.reset_index(inplace=True)
        return df_ta

    def _fetch_realtime_tencent(self, symbol: str) -> dict:
        """腾讯财经实时行情（主通道）"""
        self._rate_limit()
        url = f"https://qt.gtimg.cn/q=hk{symbol}"
        r = self._session.get(url, timeout=10)
        text = r.text.strip()
        if not text or '~' not in text:
            return {}
        parts = text.split("~")
        # qt.gtimg.cn港股字段映射（key索引）
        price = self._safe_float(parts[3]) if len(parts) > 3 else 0
        change_pct = self._safe_float(parts[32]) if len(parts) > 32 else 0
        volume = self._safe_float(parts[6]) if len(parts) > 6 else 0
        amount = self._safe_float(parts[37]) if len(parts) > 37 else 0
        high = self._safe_float(parts[33]) if len(parts) > 33 else 0
        low = self._safe_float(parts[34]) if len(parts) > 34 else 0
        market_cap = self._safe_float(parts[45]) if len(parts) > 45 else 0  # 总市值(亿)
        if market_cap > 0 and market_cap < 1e5:
            market_cap = market_cap * 1e8  # 亿→元

        return {
            "share_price": price,
            "change_pct": change_pct,
            "volume": volume,
            "amount": amount,
            "high": high,
            "low": low,
            "market_cap": market_cap,
            "shares_outstanding": market_cap / price if price > 0 and market_cap > 0 else 0,
        }

    def get_market_data(self, symbol: str) -> dict:
        """获取港股实时行情"""
        result = {"share_price": 0, "error": "港股行情获取失败"}

        # 方法1：腾讯财经实时行情
        try:
            rt = self._fetch_realtime_tencent(symbol)
            if rt.get("share_price", 0) > 0:
                result = rt
        except Exception:
            pass

        # 方法2：从历史K线取最新收盘价
        if result.get("share_price", 0) <= 0:
            try:
                df = self.get_history(symbol, period=10)
                if df is not None and not df.empty:
                    price = self._safe_float(df.iloc[-1]["收盘"])
                    if price > 0:
                        result = {
                            "share_price": price,
                            "change_pct": 0,
                            "volume": self._safe_float(df.iloc[-1].get("成交量", 0)),
                            "amount": 0,
                            "market_cap": 0,
                            "shares_outstanding": 0,
                            "_price_source": "历史K线",
                        }
            except Exception:
                pass

        # 如果shares为0，从财务指标获取已发行股本
        if result.get("shares_outstanding", 0) <= 0:
            shares = self._get_shares_outstanding(symbol)
            if shares > 0:
                result["shares_outstanding"] = shares
                if result.get("share_price", 0) > 0:
                    result["market_cap"] = result["share_price"] * shares

        return result

    def _get_shares_outstanding(self, symbol: str) -> float:
        """获取港股总股本"""
        try:
            self._rate_limit()
            df = ak.stock_hk_financial_indicator_em(symbol=symbol)
            if df is not None and not df.empty:
                return self._safe_float(df.iloc[0].get("已发行股本(股)", 0))
        except Exception:
            pass
        return 0

    def get_financial_data(self, symbol: str) -> dict:
        """获取最新一期财务数据"""
        periods = self.get_financial_data_multi_period(symbol, n=1)
        if periods:
            return periods[0]
        return {"income_statement": {}, "balance_sheet": {}, "cash_flow": {}}

    def get_financial_data_multi_period(self, symbol: str, n: int = 5) -> list[dict]:
        """获取多期财务数据（从akshare港股分析指标构建）"""
        try:
            self._rate_limit()
            df = ak.stock_financial_hk_analysis_indicator_em(symbol=symbol)
            if df is None or df.empty:
                return []

            shares = self._get_shares_outstanding(symbol)
            results = []

            for _, row in df.head(n).iterrows():
                revenue = self._safe_float(row.get("OPERATE_INCOME", 0))
                net_income = self._safe_float(row.get("HOLDER_PROFIT", 0))
                gross_profit = self._safe_float(row.get("GROSS_PROFIT", 0))
                cogs = revenue - gross_profit if revenue and gross_profit else 0
                roa = self._safe_float(row.get("ROA", 0))
                total_assets = (net_income / (roa / 100)) if roa > 0 else 0
                bps = self._safe_float(row.get("BPS", 0))
                equity = bps * shares if bps and shares else 0
                current_ratio = self._safe_float(row.get("CURRENT_RATIO", 0))
                ocf_per_share = self._safe_float(row.get("PER_NETCASH_OPERATE", 0))
                ocf = ocf_per_share * shares if ocf_per_share and shares else 0

                # 估算营业利润（EBIT）：operating_profit ≈ net_income / (1 - tax_rate)
                tax_rate = self._safe_float(row.get("TAX_EBT", 0)) / 100
                if not (0.05 < tax_rate < 0.5):
                    tax_rate = 0.20
                operating_profit = net_income / (1 - tax_rate) if net_income > 0 and tax_rate < 1 else 0

                # 估算总负债
                total_liabilities = total_assets - equity if total_assets > 0 and equity > 0 else 0

                # 估算资本支出：capex ≈ OCF * 30%（互联网公司典型比率）
                capex = ocf * 0.30 if ocf > 0 else 0

                # 估算现金：从流动比率和负债推算
                current_liabilities_est = total_liabilities * 0.6 if total_liabilities > 0 else 0
                current_assets_est = current_liabilities_est * current_ratio if current_ratio > 0 and current_liabilities_est > 0 else 0
                cash_est = current_assets_est * 0.5 if current_assets_est > 0 else 0

                results.append({
                    "income_statement": {
                        "date": str(row.get("REPORT_DATE", ""))[:10],
                        "revenue": revenue,
                        "cost_of_goods_sold": cogs,
                        "gross_profit": gross_profit,
                        "operating_profit": operating_profit,
                        "net_income": net_income,
                        "income_tax_expense": operating_profit - net_income if operating_profit > net_income else 0,
                        "total_profit": operating_profit,
                        "_estimated_fields": ["operating_profit", "income_tax_expense", "total_profit"],
                    },
                    "balance_sheet": {
                        "date": str(row.get("REPORT_DATE", ""))[:10],
                        "total_assets": total_assets,
                        "total_liabilities": total_liabilities,
                        "shareholders_equity": equity,
                        "cash_and_equivalents": cash_est,
                        "current_assets": current_assets_est,
                        "current_liabilities": current_liabilities_est,
                        "_estimated_fields": ["total_liabilities", "cash_and_equivalents", "current_assets", "current_liabilities"],
                    },
                    "cash_flow": {
                        "date": str(row.get("REPORT_DATE", ""))[:10],
                        "operating_cash_flow": ocf,
                        "capital_expenditure": capex,
                        "total_cash_outflow_from_investing": capex,
                        "_estimated_fields": ["capital_expenditure", "total_cash_outflow_from_investing"],
                    },
                })

            return results

        except Exception:
            return []
