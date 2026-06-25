"""
AKShare 数据获取器 v2
双通道：akshare直调为主，MCP补充为辅
删除 FIELD_MAPPING 硬编码，直接用标准化接口
"""

import os
import time
from datetime import datetime, timedelta
from typing import Any

os.environ['NO_PROXY'] = '*'

import akshare as ak
import pandas as pd
import numpy as np


class AKShareFetcher:
    """AKShare 数据获取器 v2 - 双通道架构"""

    def __init__(self, cache_instance=None):
        self._cache = cache_instance
        self._rate_limit_delay = 0.5
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

    def _epoch_to_iso(self, epoch_ms) -> str:
        """epoch毫秒或YYYYMMDD → ISO日期字符串"""
        try:
            s = str(epoch_ms).strip()
            if len(s) == 8 and s.isdigit():
                return f"{s[:4]}-{s[4:6]}-{s[6:]}"
            ts = int(epoch_ms) / 1000
            return datetime.fromtimestamp(ts).strftime("%Y-%m-%d")
        except (ValueError, TypeError, OSError):
            return str(epoch_ms)

    def _cached_request(self, cache_key: str, fetch_func, ttl: int = 3600):
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                return cached
        data = fetch_func()
        if self._cache:
            self._cache.set(cache_key, data)
        return data

    # ─────────────────────────────────────────────
    # 核心财务数据（主通道：stock_financial_report_sina）
    # ─────────────────────────────────────────────

    def get_financial_data(self, symbol: str) -> dict[str, Any]:
        """获取最新一期完整三表数据"""
        return self._cached_request(
            f"{symbol}_financial_v2",
            lambda: self._fetch_financial_data(symbol)
        )

    def _fetch_financial_data(self, symbol: str) -> dict[str, Any]:
        """从akshare获取三表数据"""
        result = {
            "income_statement": {},
            "balance_sheet": {},
            "cash_flow": {},
        }

        # 利润表
        try:
            self._rate_limit()
            df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
            if df is not None and not df.empty:
                latest = df.iloc[0]
                date_raw = latest.get("报告日", "")
                date_str = self._epoch_to_iso(date_raw) if isinstance(date_raw, (int, float, str)) and str(date_raw).isdigit() else str(date_raw)

                result["income_statement"] = {
                    "date": date_str,
                    "revenue": self._safe_float(latest.get("营业总收入", 0)),
                    "operating_cost": self._safe_float(latest.get("营业总成本", 0)),
                    "operating_profit": self._safe_float(latest.get("营业利润", 0)),
                    "total_profit": self._safe_float(latest.get("利润总额", 0)),
                    "net_income": self._safe_float(latest.get("净利润", 0)),
                    "net_income_attributable": self._safe_float(latest.get("归属于母公司所有者的净利润", 0)),
                    "income_tax_expense": self._safe_float(latest.get("所得税费用", 0)),
                    "finance_expense": self._safe_float(latest.get("财务费用", 0)),
                    "admin_expense": self._safe_float(latest.get("管理费用", 0)),
                    "selling_expense": self._safe_float(latest.get("销售费用", 0)),
                    "rd_expense": self._safe_float(latest.get("研发费用", 0)),
                }
        except Exception as e:
            result["income_statement"]["error"] = str(e)

        # 资产负债表
        try:
            self._rate_limit()
            df = ak.stock_financial_report_sina(stock=symbol, symbol="资产负债表")
            if df is not None and not df.empty:
                latest = df.iloc[0]
                date_raw = latest.get("报告日", "")
                date_str = self._epoch_to_iso(date_raw) if isinstance(date_raw, (int, float, str)) and str(date_raw).isdigit() else str(date_raw)

                total_assets = self._safe_float(latest.get("资产总计", 0))
                total_liabilities = self._safe_float(latest.get("负债合计", 0))
                current_assets = self._safe_float(latest.get("流动资产合计", 0))
                current_liabilities = self._safe_float(latest.get("流动负债合计", 0))

                result["balance_sheet"] = {
                    "date": date_str,
                    "total_assets": total_assets,
                    "total_liabilities": total_liabilities,
                    "current_assets": current_assets,
                    "current_liabilities": current_liabilities,
                    "cash_and_equivalents": self._safe_float(latest.get("货币资金", 0)),
                    "accounts_receivable": self._safe_float(latest.get("应收账款", 0)),
                    "inventory": self._safe_float(latest.get("存货", 0)),
                    "prepayments": self._safe_float(latest.get("预付款项", 0)),
                    "goodwill": self._safe_float(latest.get("商誉", 0)),
                    "fixed_assets_net": self._safe_float(latest.get("固定资产净额", 0)),
                    "intangible_assets": self._safe_float(latest.get("无形资产", 0)),
                    "shareholders_equity": total_assets - total_liabilities,
                    "total_equity": self._safe_float(latest.get("所有者权益(或股东权益)合计", 0)),
                    "parent_equity": self._safe_float(latest.get("归属于母公司股东权益合计", 0)),
                    "outstanding_shares": self._safe_float(latest.get("实收资本(或股本)", 0)),
                    "long_term_debt": self._safe_float(latest.get("长期借款", 0)),
                    "short_term_debt": self._safe_float(latest.get("短期借款", 0)),
                    "working_capital": current_assets - current_liabilities,
                }
        except Exception as e:
            result["balance_sheet"]["error"] = str(e)

        # 现金流量表
        try:
            self._rate_limit()
            df = ak.stock_financial_report_sina(stock=symbol, symbol="现金流量表")
            if df is not None and not df.empty:
                latest = df.iloc[0]
                date_raw = latest.get("报告日", "")
                date_str = self._epoch_to_iso(date_raw) if isinstance(date_raw, (int, float, str)) and str(date_raw).isdigit() else str(date_raw)

                result["cash_flow"] = {
                    "date": date_str,
                    "net_cash_flow_from_operations": self._safe_float(latest.get("经营活动产生的现金流量净额", 0)),
                    "total_cash_inflow_from_investing": self._safe_float(latest.get("投资活动现金流入小计", 0)),
                    "total_cash_outflow_from_investing": self._safe_float(latest.get("投资活动现金流出小计", 0)),
                    "net_cash_flow_from_investing": self._safe_float(latest.get("投资活动产生的现金流量净额", 0)),
                    "net_cash_flow_from_financing": self._safe_float(latest.get("筹资活动产生的现金流量净额", 0)),
                    "capital_expenditure": self._safe_float(latest.get("购建固定资产、无形资产和其他长期资产所支付的现金", 0)),
                }
                # 如果资本开支字段为0，用投资活动现金流出近似
                if result["cash_flow"]["capital_expenditure"] == 0:
                    result["cash_flow"]["capital_expenditure"] = abs(result["cash_flow"]["total_cash_outflow_from_investing"])
        except Exception as e:
            result["cash_flow"]["error"] = str(e)

        return result

    def get_financial_data_multi_period(self, symbol: str, n: int = 5) -> list[dict]:
        """获取多期三表数据，供杜邦/DCF/风险检测用"""
        return self._cached_request(
            f"{symbol}_multi_{n}",
            lambda: self._fetch_multi_period(symbol, n),
            ttl=7200
        )

    def _is_annual_report(self, date_str: str) -> bool:
        """判断是否为年报（12-31结尾）"""
        return date_str.endswith("-12-31")

    def _filter_annual_rows(self, df, n: int) -> list:
        """从DataFrame中筛选最近n条年报"""
        annual_rows = []
        for _, row in df.iterrows():
            date_raw = row.get("报告日", "")
            date_str = self._epoch_to_iso(date_raw) if isinstance(date_raw, (int, float, str)) and str(date_raw).isdigit() else str(date_raw)
            if self._is_annual_report(date_str):
                annual_rows.append(row)
            if len(annual_rows) >= n:
                break
        return annual_rows

    def _fetch_multi_period(self, symbol: str, n: int) -> list[dict]:
        """获取最近n期年报数据（仅年报，确保同比可比性）"""
        periods = []

        # 利润表多期
        income_multi = []
        try:
            self._rate_limit()
            df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
            if df is not None and not df.empty:
                rows = self._filter_annual_rows(df, n)
                for row in rows:
                    date_raw = row.get("报告日", "")
                    date_str = self._epoch_to_iso(date_raw)
                    income_multi.append({
                        "date": date_str,
                        "revenue": self._safe_float(row.get("营业总收入", 0)),
                        "operating_cost": self._safe_float(row.get("营业总成本", 0)),
                        "operating_profit": self._safe_float(row.get("营业利润", 0)),
                        "total_profit": self._safe_float(row.get("利润总额", 0)),
                        "net_income": self._safe_float(row.get("净利润", 0)),
                        "net_income_attributable": self._safe_float(row.get("归属于母公司所有者的净利润", 0)),
                        "income_tax_expense": self._safe_float(row.get("所得税费用", 0)),
                        "finance_expense": self._safe_float(row.get("财务费用", 0)),
                        "selling_expense": self._safe_float(row.get("销售费用", 0)),
                        "admin_expense": self._safe_float(row.get("管理费用", 0)),
                        "rd_expense": self._safe_float(row.get("研发费用", 0)),
                    })
        except Exception:
            pass

        # 资产负债表多期
        balance_multi = []
        try:
            self._rate_limit()
            df = ak.stock_financial_report_sina(stock=symbol, symbol="资产负债表")
            if df is not None and not df.empty:
                rows = self._filter_annual_rows(df, n)
                for row in rows:
                    date_raw = row.get("报告日", "")
                    date_str = self._epoch_to_iso(date_raw)
                    total_assets = self._safe_float(row.get("资产总计", 0))
                    total_liabilities = self._safe_float(row.get("负债合计", 0))
                    current_assets = self._safe_float(row.get("流动资产合计", 0))
                    current_liabilities = self._safe_float(row.get("流动负债合计", 0))
                    balance_multi.append({
                        "date": date_str,
                        "total_assets": total_assets,
                        "total_liabilities": total_liabilities,
                        "current_assets": current_assets,
                        "current_liabilities": current_liabilities,
                        "cash_and_equivalents": self._safe_float(row.get("货币资金", 0)),
                        "accounts_receivable": self._safe_float(row.get("应收账款", 0)),
                        "inventory": self._safe_float(row.get("存货", 0)),
                        "prepayments": self._safe_float(row.get("预付款项", 0)),
                        "goodwill": self._safe_float(row.get("商誉", 0)),
                        "fixed_assets_net": self._safe_float(row.get("固定资产净额", 0)),
                        "shareholders_equity": total_assets - total_liabilities,
                        "total_equity": self._safe_float(row.get("所有者权益(或股东权益)合计", 0)),
                        "parent_equity": self._safe_float(row.get("归属于母公司股东权益合计", 0)),
                        "outstanding_shares": self._safe_float(row.get("实收资本(或股本)", 0)),
                        "long_term_debt": self._safe_float(row.get("长期借款", 0)),
                        "short_term_debt": self._safe_float(row.get("短期借款", 0)),
                        "working_capital": current_assets - current_liabilities,
                    })
        except Exception:
            pass

        # 现金流量表多期
        cashflow_multi = []
        try:
            self._rate_limit()
            df = ak.stock_financial_report_sina(stock=symbol, symbol="现金流量表")
            if df is not None and not df.empty:
                rows = self._filter_annual_rows(df, n)
                for row in rows:
                    date_raw = row.get("报告日", "")
                    date_str = self._epoch_to_iso(date_raw)
                    ocf = self._safe_float(row.get("经营活动产生的现金流量净额", 0))
                    capex = self._safe_float(row.get("购建固定资产、无形资产和其他长期资产所支付的现金", 0))
                    investing_out = self._safe_float(row.get("投资活动现金流出小计", 0))
                    if capex == 0:
                        capex = abs(investing_out)
                    cashflow_multi.append({
                        "date": date_str,
                        "net_cash_flow_from_operations": ocf,
                        "net_cash_flow_from_investing": self._safe_float(row.get("投资活动产生的现金流量净额", 0)),
                        "net_cash_flow_from_financing": self._safe_float(row.get("筹资活动产生的现金流量净额", 0)),
                        "capital_expenditure": capex,
                    })
        except Exception:
            pass

        # 按期合并
        for i in range(max(len(income_multi), len(balance_multi), len(cashflow_multi))):
            period_data = {}
            if i < len(income_multi):
                period_data["income_statement"] = income_multi[i]
            if i < len(balance_multi):
                period_data["balance_sheet"] = balance_multi[i]
            if i < len(cashflow_multi):
                period_data["cash_flow"] = cashflow_multi[i]
            if period_data:
                periods.append(period_data)

        return periods

    # ─────────────────────────────────────────────
    # 市场数据
    # ─────────────────────────────────────────────

    def get_market_data(self, symbol: str) -> dict:
        """获取实时市场数据"""
        return self._cached_request(
            f"{symbol}_market_v2",
            lambda: self._fetch_market_data(symbol),
            ttl=600
        )

    def _to_163_symbol(self, symbol: str) -> str:
        """600519 → sh600519（网易格式）"""
        if symbol.startswith(('6', '9')):
            return f"sh{symbol}"
        return f"sz{symbol}"

    def _fetch_market_data(self, symbol: str) -> dict:
        """从akshare获取A股市场数据（实时行情+个股信息）"""
        result = {
            "share_price": 0, "shares_outstanding": 0, "market_cap": 0,
            "pe_ratio": 0, "pb_ratio": 0,
            "change_pct": 0, "high": 0, "low": 0, "open": 0, "prev_close": 0,
            "volume": 0, "amount": 0, "turnover_rate": 0, "amplitude": 0,
        }

        # 通道1: stock_bid_ask_em — 实时行情（0.2秒）
        try:
            self._rate_limit()
            bid_df = ak.stock_bid_ask_em(symbol=symbol)
            if bid_df is not None and not bid_df.empty:
                data = dict(zip(bid_df["item"], bid_df["value"]))
                result["share_price"] = self._safe_float(data.get("最新", 0))
                result["change_pct"] = self._safe_float(data.get("涨幅", 0))
                result["high"] = self._safe_float(data.get("最高", 0))
                result["low"] = self._safe_float(data.get("最低", 0))
                result["open"] = self._safe_float(data.get("今开", 0))
                result["prev_close"] = self._safe_float(data.get("昨收", 0))
                result["volume"] = self._safe_float(data.get("总手", 0))
                result["amount"] = self._safe_float(data.get("金额", 0))
                result["turnover_rate"] = self._safe_float(data.get("换手", 0))
                result["amplitude"] = self._safe_float(data.get("振幅", 0)) if "振幅" in data else 0
        except Exception:
            pass

        # 通道2: stock_individual_info_em — 总股本/市值/行业
        try:
            self._rate_limit()
            info_df = ak.stock_individual_info_em(symbol=symbol)
            if info_df is not None and not info_df.empty:
                info = dict(zip(info_df["item"], info_df["value"]))
                result["shares_outstanding"] = self._safe_float(info.get("总股本", 0))
                result["market_cap"] = self._safe_float(info.get("总市值", 0))
                result["float_market_cap"] = self._safe_float(info.get("流通市值", 0))
                result["industry"] = str(info.get("行业", ""))
                self._last_industry = result["industry"]
        except Exception:
            pass

        # 如果实时价格获取失败，fallback到历史日线
        if result["share_price"] <= 0:
            try:
                self._rate_limit()
                df = ak.stock_zh_a_hist(symbol=symbol, period="daily", adjust="",
                                        start_date=(datetime.now() - timedelta(days=7)).strftime("%Y%m%d"),
                                        end_date=datetime.now().strftime("%Y%m%d"))
                if df is not None and not df.empty:
                    latest = df.iloc[-1]
                    result["share_price"] = self._safe_float(latest.get("收盘", 0))
                    if result["share_price"] > 0:
                        result["change_pct"] = self._safe_float(latest.get("涨跌幅", 0))
                        result["high"] = self._safe_float(latest.get("最高", 0))
                        result["low"] = self._safe_float(latest.get("最低", 0))
                        result["open"] = self._safe_float(latest.get("开盘", 0))
                        result["volume"] = self._safe_float(latest.get("成交量", 0))
                        result["amount"] = self._safe_float(latest.get("成交额", 0))
                        result["turnover_rate"] = self._safe_float(latest.get("换手率", 0))
            except Exception:
                pass

            # 再fallback到网易日线
            if result["share_price"] <= 0:
                try:
                    self._rate_limit()
                    sym163 = self._to_163_symbol(symbol)
                    df = ak.stock_zh_a_daily(symbol=sym163, adjust="")
                    if df is not None and not df.empty:
                        latest = df.iloc[-1]
                        result["share_price"] = self._safe_float(latest.get("close", 0))
                        shares = self._safe_float(latest.get("outstanding_share", 0))
                        if result["shares_outstanding"] <= 0:
                            result["shares_outstanding"] = shares
                        if result["market_cap"] <= 0 and shares > 0:
                            result["market_cap"] = result["share_price"] * shares
                except Exception:
                    pass

        # 股息率（异步不依赖上面的数据，用自己的缓存）
        if result["share_price"] > 0:
            try:
                div = self.get_dividend_data(symbol, current_price=result["share_price"])
                result["ttm_dps"] = div.get("ttm_dps", 0)
                result["avg_3y_dps"] = div.get("avg_3y_dps", 0)
                result["core_dps"] = div.get("core_dps", 0)
                result["dividend_yield"] = div.get("dividend_yield", 0)
                result["dividend_warning"] = div.get("dividend_warning")
            except Exception:
                pass

        return result

    # ─────────────────────────────────────────────
    # 历史行情（用于技术分析）
    # ─────────────────────────────────────────────

    def get_pe_pb_history(self, symbol: str, years: int = 10) -> dict | None:
        """A股个股 PE/PB 历史序列(百度股市通 stock_zh_valuation_baidu)。
        返回 {"pe": [...], "pb": [...]}(取正有效值),失败/空 → None。"""
        try:
            self._rate_limit()
            pe_df = ak.stock_zh_valuation_baidu(symbol=symbol, indicator="市盈率(TTM)", period="全部")
            pb_df = ak.stock_zh_valuation_baidu(symbol=symbol, indicator="市净率", period="全部")
            pe = [self._safe_float(x) for x in (pe_df["value"] if pe_df is not None and not pe_df.empty else []) if self._safe_float(x) > 0]
            pb = [self._safe_float(x) for x in (pb_df["value"] if pb_df is not None and not pb_df.empty else []) if self._safe_float(x) > 0]
            return {"pe": pe, "pb": pb} if pe else None
        except Exception:
            return None

    def get_adjusted_closes(self, symbol: str, period: int = 4000) -> list:
        """前复权收盘价序列(长期持有期/回撤用,避免除权扭曲)。失败 → []。"""
        try:
            self._rate_limit()
            sym163 = self._to_163_symbol(symbol)
            df = ak.stock_zh_a_daily(symbol=sym163, adjust="qfq")
            if df is None or df.empty:
                return []
            return df.tail(period)["close"].astype(float).tolist()
        except Exception:
            return []

    def get_history(self, symbol: str, period: int = 100) -> pd.DataFrame:
        """
        获取历史行情数据（网易源，不依赖push2）
        返回 DataFrame: 日期, 开盘, 收盘, 最高, 最低, 成交量
        """
        cache_key = f"{symbol}_hist_{period}"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                if isinstance(cached, pd.DataFrame):
                    return cached
                # JSON缓存反序列化为dict list → 恢复DataFrame
                try:
                    return pd.DataFrame(cached)
                except Exception:
                    pass

        try:
            self._rate_limit()
            sym163 = self._to_163_symbol(symbol)
            df = ak.stock_zh_a_daily(symbol=sym163, adjust="")
            if df is not None and not df.empty:
                # 重命名列：英文→中文（兼容技术分析模块）
                result = df.tail(period).rename(columns={
                    "date": "日期", "open": "开盘", "close": "收盘",
                    "high": "最高", "low": "最低", "volume": "成交量",
                })[["日期", "开盘", "收盘", "最高", "最低", "成交量"]].reset_index(drop=True)
                if self._cache:
                    # 日期字段转字符串以确保JSON可序列化
                    cache_data = result.copy()
                    for col in cache_data.columns:
                        if cache_data[col].dtype == 'object':
                            cache_data[col] = cache_data[col].astype(str)
                    self._cache.set(cache_key, cache_data.to_dict("records"))
                return result
        except Exception:
            pass
        return pd.DataFrame()

    def get_history_with_indicators(self, symbol: str, period: int = 100) -> pd.DataFrame:
        """
        获取历史行情 + pandas-ta计算的技术指标
        返回含技术指标列的 DataFrame
        """
        df = self.get_history(symbol, period)
        if df.empty:
            return df

        try:
            import pandas_ta as ta
        except ImportError:
            # pandas-ta 未安装，返回原始数据
            return df

        # 列名映射：中文 → 英文（pandas-ta 需要）
        df_ta = df.rename(columns={
            "日期": "Date", "开盘": "Open", "收盘": "Close",
            "最高": "High", "最低": "Low", "成交量": "Volume",
        })
        df_ta["Date"] = pd.to_datetime(df_ta["Date"])
        df_ta.set_index("Date", inplace=True)

        # 确保数值类型
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df_ta[col] = pd.to_numeric(df_ta[col], errors="coerce")

        # 一次性计算全部指标
        df_ta.ta.macd(fast=12, slow=26, signal=9, append=True)
        df_ta.ta.rsi(length=14, append=True)
        df_ta.ta.stoch(k=3, d=3, append=True)  # KDJ (Stochastic)
        df_ta.ta.bbands(length=20, std=2, append=True)  # 布林带
        df_ta.ta.obv(append=True)  # OBV
        df_ta.ta.atr(length=14, append=True)  # ATR
        df_ta.ta.adx(length=14, append=True)  # ADX
        df_ta.ta.cci(length=20, append=True)  # CCI
        df_ta.ta.mfi(length=14, append=True)  # MFI

        # 重置索引，把 Date 变回列
        df_ta.reset_index(inplace=True)

        return df_ta

    # ─────────────────────────────────────────────
    # 行业动态查询
    # ─────────────────────────────────────────────

    def get_industry(self, symbol: str) -> str:
        """动态查询股票所属行业"""
        try:
            self._rate_limit()
            # 先获取所有行业板块
            boards = ak.stock_board_industry_name_em()
            if boards is None or boards.empty:
                return "general"

            # 遍历板块查找股票
            for _, board in boards.iterrows():
                board_name = board.get("板块名称", "")
                try:
                    self._rate_limit()
                    cons = ak.stock_board_industry_cons_em(symbol=board_name)
                    if cons is not None and not cons.empty:
                        codes = cons["代码"].astype(str).tolist()
                        if symbol in codes:
                            return board_name
                except Exception:
                    continue
        except Exception:
            pass
        return "general"

    def get_industry_peers(self, symbol: str) -> dict:
        """获取同行业公司及其PE/PB"""
        try:
            self._rate_limit()
            boards = ak.stock_board_industry_name_em()
            if boards is None or boards.empty:
                return {"industry": "unknown", "peers": []}

            for _, board in boards.iterrows():
                board_name = board.get("板块名称", "")
                try:
                    self._rate_limit()
                    cons = ak.stock_board_industry_cons_em(symbol=board_name)
                    if cons is not None and not cons.empty:
                        codes = cons["代码"].astype(str).tolist()
                        if symbol in codes:
                            peers = []
                            for _, row in cons.iterrows():
                                peers.append({
                                    "code": str(row.get("代码", "")),
                                    "name": str(row.get("名称", "")),
                                    "pe": self._safe_float(row.get("市盈率-动态", 0)),
                                    "pb": self._safe_float(row.get("市净率", 0)),
                                })
                            return {"industry": board_name, "peers": peers}
                except Exception:
                    continue
        except Exception:
            pass
        return {"industry": "unknown", "peers": []}

    # ─────────────────────────────────────────────
    # 资金流向（保留原有逻辑）
    # ─────────────────────────────────────────────

    def get_fund_flow(self, symbol: str) -> dict:
        """获取资金流向数据"""
        def fetch():
            self._rate_limit()
            market = "sz" if symbol.startswith(('0', '2', '3')) else "sh"
            try:
                df = ak.stock_individual_fund_flow(stock=symbol, market=market)
                if df is None or df.empty:
                    return {"error": "无法获取资金流向数据"}

                latest = df.iloc[0].to_dict()
                latest_clean = {}
                for key, value in latest.items():
                    if hasattr(value, 'strftime'):
                        latest_clean[key] = str(value)
                    elif isinstance(value, pd.Timestamp):
                        latest_clean[key] = str(value)
                    elif isinstance(value, float) and pd.isna(value):
                        latest_clean[key] = None
                    else:
                        latest_clean[key] = value

                trend = []
                for _, row in df.head(5).iterrows():
                    inflow = row.get("主力净流入-净额", 0)
                    if pd.notna(inflow):
                        trend.append(float(inflow))

                return {"latest": latest_clean, "trend": trend}
            except Exception as e:
                return {"error": f"资金流向获取失败: {str(e)}"}

        return self._cached_request(f"{symbol}_fund_flow_v2", fetch, ttl=600)

    # ─────────────────────────────────────────────
    # 新闻
    # ─────────────────────────────────────────────

    def get_news(self, symbol: str, limit: int = 5) -> dict:
        """获取最新新闻"""
        def fetch():
            self._rate_limit()
            try:
                df = ak.stock_news_em(symbol=symbol)
                if df is None or df.empty:
                    return {"news": []}
                news_list = []
                for _, row in df.head(limit).iterrows():
                    news_list.append({
                        "title": row.get("新闻标题", ""),
                        "time": row.get("发布时间", ""),
                        "url": row.get("新闻链接", ""),
                        "content": row.get("新闻内容", "")[:100],
                    })
                return {"news": news_list}
            except Exception as e:
                return {"error": f"新闻获取失败: {str(e)}"}

        return self._cached_request(f"{symbol}_news_v2", fetch, ttl=1800)

    # ─────────────────────────────────────────────
    # TTM数据（滚动十二个月）
    # ─────────────────────────────────────────────

    SEASONAL_INDUSTRIES = ["白酒", "农业", "零售", "旅游", "啤酒", "乳制品", "饮料"]

    def get_ttm_data(self, symbol: str, shares: float = 0) -> dict:
        """计算TTM核心指标（从季度财报拼接）"""
        cache_key = f"{symbol}_ttm_v1"
        if self._cache:
            cached = self._cache.get(cache_key)
            if cached is not None:
                # 如果缓存中有但shares=0，且外部传了shares，用外部值补算eps
                if shares > 0 and cached.get("ttm_eps", 0) <= 0 and cached.get("ttm_net_income", 0) > 0:
                    cached["ttm_eps"] = round(cached["ttm_net_income"] / shares, 4)
                    cached["annual_eps"] = round(cached["annual_net_income"] / shares, 4) if cached.get("annual_net_income", 0) > 0 else 0
                return cached
        data = self._fetch_ttm_data(symbol, shares)
        if self._cache:
            self._cache.set(cache_key, data)
        return data

    def _fetch_ttm_data(self, symbol: str, shares: float = 0) -> dict:
        result = {
            "ttm_net_income": 0, "ttm_revenue": 0, "ttm_eps": 0,
            "report_period": "", "is_anomalous": False,
            "annual_eps": 0, "annual_net_income": 0,
        }

        # 优先用外部传入的shares，否则尝试stock_individual_info_em
        if shares <= 0:
            try:
                info_df = ak.stock_individual_info_em(symbol=symbol)
                if info_df is not None and not info_df.empty:
                    info = dict(zip(info_df["item"], info_df["value"]))
                    shares = self._safe_float(info.get("总股本", 0))
            except Exception:
                pass

        try:
            self._rate_limit()
            df = ak.stock_financial_report_sina(stock=symbol, symbol="利润表")
            if df is None or df.empty:
                return result

            rows = []
            for _, row in df.iterrows():
                date_raw = row.get("报告日", "")
                date_str = self._epoch_to_iso(date_raw) if isinstance(date_raw, (int, float, str)) and str(date_raw).isdigit() else str(date_raw)
                ni = self._safe_float(row.get("归属于母公司所有者的净利润", 0))
                rev = self._safe_float(row.get("营业总收入", 0))
                rows.append({"date": date_str, "net_income": ni, "revenue": rev})

            if not rows:
                return result

            latest = rows[0]
            result["report_period"] = latest["date"]

            if self._is_annual_report(latest["date"]):
                result["ttm_net_income"] = latest["net_income"]
                result["ttm_revenue"] = latest["revenue"]
                result["annual_net_income"] = latest["net_income"]
                result["annual_eps"] = latest["net_income"] / shares if shares > 0 else 0
            else:
                latest_quarter = self._quarter_of(latest["date"])
                # 找上一年报和上一年同季度
                prev_annual = None
                prev_same_quarter = None
                for r in rows[1:]:
                    if prev_annual is None and self._is_annual_report(r["date"]):
                        prev_annual = r
                    if prev_same_quarter is None and self._quarter_of(r["date"]) == latest_quarter and not self._is_annual_report(r["date"]):
                        prev_same_quarter = r
                    if prev_annual and prev_same_quarter:
                        break

                if prev_annual:
                    result["annual_net_income"] = prev_annual["net_income"]
                    result["annual_eps"] = prev_annual["net_income"] / shares if shares > 0 else 0
                    if prev_same_quarter:
                        result["ttm_net_income"] = latest["net_income"] + (prev_annual["net_income"] - prev_same_quarter["net_income"])
                        result["ttm_revenue"] = latest["revenue"] + (prev_annual["revenue"] - prev_same_quarter["revenue"])
                    else:
                        result["ttm_net_income"] = latest["net_income"]
                        result["ttm_revenue"] = latest["revenue"]

            result["ttm_eps"] = result["ttm_net_income"] / shares if shares > 0 else 0

            # 季节性平滑：仅对行业明确为非季节性的股票做轻微年化平滑
            # 行业未知或季节性行业 → 严格TTM，不做任何调整
            if not self._is_annual_report(latest["date"]) and result["ttm_eps"] > 0:
                industry = getattr(self, '_last_industry', '')
                is_seasonal = industry and any(kw in industry for kw in self.SEASONAL_INDUSTRIES)
                is_known_non_seasonal = industry and not is_seasonal
                if is_known_non_seasonal:
                    # 非季节性行业：允许TTM与简单年化做7:3平滑
                    q_annualized = latest["net_income"] * 4 / shares if shares > 0 else 0
                    quarters_in_year = {"Q1": 1, "Q2": 2, "Q3": 3}
                    q_count = quarters_in_year.get(self._quarter_of(latest["date"]), 1)
                    if q_annualized > 0 and q_count < 4:
                        result["ttm_eps"] = round(result["ttm_eps"] * 0.7 + q_annualized * 0.3, 4)

            # 异常年检测：最新年报 vs 上年年报净利变动 > ±40%
            annual_rows = [r for r in rows if self._is_annual_report(r["date"])]
            if len(annual_rows) >= 2 and annual_rows[1]["net_income"] > 0:
                change = abs(annual_rows[0]["net_income"] / annual_rows[1]["net_income"] - 1)
                if change > 0.4:
                    result["is_anomalous"] = True

        except Exception:
            pass

        return result

    def _quarter_of(self, date_str: str) -> str:
        """从日期字符串提取季度 'Q1'/'Q2'/'Q3'/'Q4'"""
        try:
            month = int(date_str.split("-")[1])
            if month <= 3: return "Q1"
            elif month <= 6: return "Q2"
            elif month <= 9: return "Q3"
            else: return "Q4"
        except (ValueError, IndexError):
            return "Q4"

    # ─────────────────────────────────────────────
    # 股息率数据
    # ─────────────────────────────────────────────

    def get_dividend_data(self, symbol: str, current_price: float = 0) -> dict:
        """获取股息率（含防诈骗：3年均值与TTM取孰低）"""
        return self._cached_request(
            f"{symbol}_dividend_v1",
            lambda: self._fetch_dividend_data(symbol, current_price),
            ttl=7200
        )

    def _fetch_dividend_data(self, symbol: str, current_price: float) -> dict:
        result = {
            "ttm_dps": 0, "avg_3y_dps": 0, "core_dps": 0,
            "dividend_yield": 0, "dividend_warning": None,
        }
        try:
            self._rate_limit()
            df = ak.stock_fhps_detail_em(symbol=symbol)
            if df is None or df.empty:
                return result

            # 按报告期降序排列
            df = df.sort_values("报告期", ascending=False)

            # 解析每股分红（"10派X元" → DPS = X/10）
            yearly_dividends = {}  # year -> total_dps
            for _, row in df.iterrows():
                period = str(row.get("报告期", ""))
                year = period[:4]
                if not year.isdigit():
                    continue
                dps_raw = row.get("现金分红-现金分红比例", 0)
                dps = self._safe_float(dps_raw) / 10  # "10派X元" → 每股X/10元
                if dps > 0:
                    yearly_dividends[year] = yearly_dividends.get(year, 0) + dps

            if not yearly_dividends:
                return result

            sorted_years = sorted(yearly_dividends.keys(), reverse=True)

            # TTM: 最近年度的累计分红
            if sorted_years:
                result["ttm_dps"] = yearly_dividends[sorted_years[0]]

            # 3年平均
            if len(sorted_years) >= 3:
                avg = sum(yearly_dividends[y] for y in sorted_years[:3]) / 3
                result["avg_3y_dps"] = round(avg, 4)
            elif len(sorted_years) >= 1:
                result["avg_3y_dps"] = yearly_dividends[sorted_years[0]]

            # 防诈骗：取孰低
            result["core_dps"] = min(result["ttm_dps"], result["avg_3y_dps"]) if result["avg_3y_dps"] > 0 else result["ttm_dps"]

            # 一次性分红检测
            if result["ttm_dps"] > result["avg_3y_dps"] * 1.5 and result["avg_3y_dps"] > 0:
                result["dividend_warning"] = "包含一次性分红，股息率可能不可持续"

            # 股息率
            if current_price > 0 and result["core_dps"] > 0:
                result["dividend_yield"] = round(result["core_dps"] / current_price * 100, 2)

        except Exception:
            pass

        return result
