"""
ETF数据获取器
ETF行情/历史/溢折价/份额变动
"""

import os
import json
import time
from datetime import datetime, timedelta, timezone
from typing import Any

os.environ['NO_PROXY'] = '*'

import akshare as ak
import pandas as pd
import numpy as np
import requests


class ETFFetcher:
    """ETF专用数据获取"""

    # 常用ETF名称映射（网络失败时的兜底）
    ETF_NAME_MAP = {
        "159941": "纳指ETF", "513100": "纳指ETF",
        "510300": "沪深300ETF", "510500": "中证500ETF",
        "159915": "创业板ETF", "510050": "上证50ETF",
        "513050": "中概互联ETF", "159949": "创业板50ETF",
        "512880": "证券ETF", "512000": "券商ETF",
        "515030": "新能源车ETF", "516160": "新能源ETF",
        "512480": "半导体ETF", "512660": "军工ETF",
        "512690": "酒ETF", "515170": "食品饮料ETF",
        "512100": "中证1000ETF", "159901": "深证100ETF",
        "588000": "科创50ETF", "510880": "红利ETF",
        "159920": "恒生ETF", "513060": "恒生医疗ETF",
        "513130": "恒生科技ETF", "164906": "印度基金ETF",
        "513520": "日经ETF", "513030": "德国ETF",
        "159611": "纳指生物科技ETF", "513080": "法国ETF",
    }

    XUEQIU_TOKEN_CACHE = os.path.expanduser("~/.epm_xueqiu_token.json")

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

    def _to_sina_symbol(self, symbol: str) -> str:
        """510300 → sh510300"""
        if symbol.startswith(('5', '6', '9')):
            return f"sh{symbol}"
        return f"sz{symbol}"

    def _to_xueqiu_symbol(self, symbol: str) -> str:
        """159941 → SZ159941"""
        if symbol.startswith(("SZ", "SH")):
            return symbol
        return f"SH{symbol}" if symbol.startswith(("5", "6")) else f"SZ{symbol}"

    # ─────────────────────────────────────────────
    # 雪球 Token（Playwright 静默获取 + 本地缓存）
    # ─────────────────────────────────────────────

    # 系统 Playwright chromium 路径（与 MCP 共享）
    _CHROMIUM_PATH = os.path.expanduser(
        "~/Library/Caches/ms-playwright/chromium-1208/chrome-mac-arm64/"
        "Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing"
    )

    def _get_xueqiu_token(self) -> str | None:
        """获取雪球 token（缓存优先，过期则 Playwright 刷新）"""
        # 1. 读缓存
        if os.path.exists(self.XUEQIU_TOKEN_CACHE):
            try:
                with open(self.XUEQIU_TOKEN_CACHE, "r") as f:
                    data = json.load(f)
                expires = datetime.fromisoformat(data["expires_at"])
                if datetime.now(timezone.utc) < expires:
                    return data["token"]
            except (json.JSONDecodeError, KeyError):
                pass

        # 2. Playwright 静默刷新
        return self._refresh_xueqiu_token()

    def _refresh_xueqiu_token(self) -> str | None:
        """Playwright headless 获取 xq_a_token 并缓存"""
        try:
            from playwright.sync_api import sync_playwright
        except ImportError:
            return None

        if not os.path.exists(self._CHROMIUM_PATH):
            return None

        try:
            with sync_playwright() as p:
                browser = p.chromium.launch(
                    headless=True, executable_path=self._CHROMIUM_PATH
                )
                page = browser.new_page()
                page.goto("https://xueqiu.com/", timeout=30000,
                          wait_until="domcontentloaded")
                page.wait_for_timeout(5000)
                cookies = browser.contexts[0].cookies()
                browser.close()

            token = None
            for c in cookies:
                if c["name"] == "xq_a_token":
                    token = c["value"]
                    break

            if token:
                expires = datetime.now(timezone.utc) + timedelta(hours=4)
                with open(self.XUEQIU_TOKEN_CACHE, "w") as f:
                    json.dump({"token": token, "expires_at": expires.isoformat()}, f)
                return token
        except Exception:
            pass

        return None

    # ─────────────────────────────────────────────
    # 雪球通道（含名称/IOPV/溢折率）
    # ─────────────────────────────────────────────

    def _fetch_xueqiu_realtime(self, symbol: str) -> dict | None:
        """通过雪球API获取ETF实时数据"""
        token = self._get_xueqiu_token()
        if not token:
            return None

        xq_sym = self._to_xueqiu_symbol(symbol)
        try:
            session = requests.Session()
            session.headers.update({
                "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36",
                "X-Requested-With": "XMLHttpRequest",
            })
            session.cookies.set("xq_a_token", token, domain=".xueqiu.com")

            r = session.get(
                "https://stock.xueqiu.com/v5/stock/quote.json",
                params={"symbol": xq_sym, "extend": "detail"},
                timeout=10,
            )
            r.raise_for_status()
            data = r.json()
            if data.get("error_code") != 0:
                return None

            q = data["data"]["quote"]
            price = self._safe_float(q.get("current", 0))
            iopv = self._safe_float(q.get("iopv", 0))
            premium = self._safe_float(q.get("premium_rate", 0))
            # API未返回溢价率时，从价格和IOPV自行计算
            if premium == 0 and price > 0 and iopv > 0:
                premium = round((price - iopv) / iopv * 100, 2)
            return {
                "code": symbol,
                "name": q.get("name", ""),
                "price": price,
                "change_pct": round(self._safe_float(q.get("percent", 0)), 2),
                "volume": self._safe_float(q.get("volume", 0)),
                "amount": self._safe_float(q.get("amount", 0)),
                "iopv": iopv,
                "premium_rate": premium,
                "open": self._safe_float(q.get("open", 0)),
                "high": self._safe_float(q.get("high", 0)),
                "low": self._safe_float(q.get("low", 0)),
                "prev_close": self._safe_float(q.get("last_close", 0)),
            }
        except Exception:
            return None

    # ─────────────────────────────────────────────
    # 实时数据（三通道降级）
    # ─────────────────────────────────────────────

    def _fetch_name_from_spot(self, symbol: str) -> str:
        """从 eastmoney spot 表获取 ETF 名称，失败则查本地映射"""
        try:
            self._rate_limit()
            df = ak.fund_etf_spot_em()
            if df is not None and not df.empty:
                row = df[df["代码"].astype(str) == symbol]
                if not row.empty:
                    name = str(row.iloc[0].get("名称", ""))
                    if name:
                        return name
        except Exception:
            pass
        return self.ETF_NAME_MAP.get(symbol, "")

    def get_etf_realtime(self, symbol: str) -> dict:
        """
        获取ETF实时数据（含溢折价、IOPV）
        优先级：雪球 → eastmoney → Sina
        """
        # 先尝试单独拿名称（eastmoney spot 表轻量但含名称）
        name = self._fetch_name_from_spot(symbol)

        # 首选：雪球（有名称/IOPV/溢折率）
        # 如果缓存过期，尝试自动刷新一次
        result = self._fetch_xueqiu_realtime(symbol)
        if result and result.get("price", 0) > 0:
            if name and not result.get("name"):
                result["name"] = name
            result["_data_source"] = "xueqiu"
            return result

        # 次选：eastmoney spot
        try:
            self._rate_limit()
            df = ak.fund_etf_spot_em()
            if df is not None and not df.empty:
                etf_data = df[df["代码"].astype(str) == symbol]
                if not etf_data.empty:
                    row = etf_data.iloc[0]
                    r = {
                        "code": symbol,
                        "name": str(row.get("名称", "")),
                        "price": self._safe_float(row.get("最新价", 0)),
                        "change_pct": self._safe_float(row.get("涨跌幅", 0)),
                        "volume": self._safe_float(row.get("成交量", 0)),
                        "amount": self._safe_float(row.get("成交额", 0)),
                        "iopv": self._safe_float(row.get("IOPV实时估值", 0)),
                        "premium_rate": self._safe_float(row.get("溢折率", 0)),
                        "open": self._safe_float(row.get("开盘价", 0)),
                        "high": self._safe_float(row.get("最高价", 0)),
                        "low": self._safe_float(row.get("最低价", 0)),
                        "prev_close": self._safe_float(row.get("昨收", 0)),
                        "_data_source": "eastmoney_spot",
                        "_warning": "雪球数据不可用，IOPV/溢价率可能缺失" if self._safe_float(row.get("IOPV实时估值", 0)) == 0 else None,
                    }
                    return r
        except Exception:
            pass

        # 兜底：Sina历史最新一条
        try:
            self._rate_limit()
            sina_sym = self._to_sina_symbol(symbol)
            df = ak.fund_etf_hist_sina(symbol=sina_sym)
            if df is not None and not df.empty:
                latest = df.iloc[-1]
                prev = df.iloc[-2] if len(df) >= 2 else latest
                price = self._safe_float(latest.get("close", 0))
                prev_close = self._safe_float(prev.get("close", 0))
                change_pct = (price - prev_close) / prev_close * 100 if prev_close > 0 else 0
                return {
                    "code": symbol,
                    "name": name,
                    "price": price,
                    "change_pct": round(change_pct, 2),
                    "volume": self._safe_float(latest.get("volume", 0)),
                    "amount": self._safe_float(latest.get("amount", 0)),
                    "iopv": 0,
                    "premium_rate": 0,
                    "open": self._safe_float(latest.get("open", 0)),
                    "high": self._safe_float(latest.get("high", 0)),
                    "low": self._safe_float(latest.get("low", 0)),
                    "prev_close": prev_close,
                }
        except Exception:
            pass

        return {"error": f"ETF {symbol} 数据获取失败"}

    # 历史数据标准输出列
    _STD_COLS = ["日期", "开盘", "收盘", "最高", "最低", "成交量"]

    def _normalize_hist(self, df: pd.DataFrame, period: int) -> pd.DataFrame:
        """统一历史数据列名，只保留标准列"""
        result = df.tail(period).copy()
        col_map = {
            "date": "日期", "open": "开盘", "close": "收盘",
            "high": "最高", "low": "最低", "volume": "成交量",
        }
        result.rename(columns=col_map, inplace=True)
        keep = [c for c in self._STD_COLS if c in result.columns]
        return result[keep].reset_index(drop=True)

    def get_etf_hist(self, symbol: str, period: int = 100) -> pd.DataFrame:
        """
        获取ETF历史行情（主通道eastmoney，备用Sina）
        返回 DataFrame: 日期, 开盘, 收盘, 最高, 最低, 成交量
        """
        # 主通道：eastmoney
        try:
            self._rate_limit()
            start_date = (datetime.now() - timedelta(days=period + 30)).strftime("%Y%m%d")
            end_date = datetime.now().strftime("%Y%m%d")
            df = ak.fund_etf_hist_em(symbol=symbol, period="daily",
                                     start_date=start_date, end_date=end_date, adjust="")
            if df is not None and not df.empty:
                return self._normalize_hist(df, period)
        except Exception:
            pass

        # 备用：Sina
        try:
            self._rate_limit()
            sina_sym = self._to_sina_symbol(symbol)
            df = ak.fund_etf_hist_sina(symbol=sina_sym)
            if df is not None and not df.empty:
                return self._normalize_hist(df, period)
        except Exception:
            pass

        return pd.DataFrame()

    def get_adjusted_closes(self, symbol: str, period: int = 4000) -> list:
        """ETF 收盘序列(长期持有期/回撤/定投用)。
        东财 fund_etf_hist_em 对部分 ETF 超长 start_date 返回空 → 新浪 fund_etf_hist_sina 兜底。
        降级链:东财qfq带日期 → 东财不复权带日期 → 新浪全历史(不复权)。
        QDII(如纳指ETF)分红极少,不复权几乎无损。全失败 → []。"""
        start_date = (datetime.now() - timedelta(days=period + 30)).strftime("%Y%m%d")
        end_date = datetime.now().strftime("%Y%m%d")
        # 东财:优先 qfq(前复权),失败降级不复权
        for adjust in ("qfq", ""):
            try:
                self._rate_limit()
                df = ak.fund_etf_hist_em(symbol=symbol, period="daily",
                                         start_date=start_date, end_date=end_date, adjust=adjust)
                if df is not None and not df.empty:
                    closes = df["收盘"].astype(float).tolist()
                    return closes[-period:] if len(closes) > period else closes
            except Exception:
                continue
        # 新浪兜底:全历史(不复权),规避东财长 start_date 边界(实测 159941→2659行)
        try:
            self._rate_limit()
            df = ak.fund_etf_hist_sina(symbol=self._to_sina_symbol(symbol))
            if df is not None and not df.empty:
                closes = df["close"].astype(float).tolist()
                return closes[-period:] if len(closes) > period else closes
        except Exception:
            pass
        return []

    def get_etf_hist_with_indicators(self, symbol: str, period: int = 100) -> pd.DataFrame:
        """
        获取ETF历史行情 + pandas-ta技术指标
        """
        df = self.get_etf_hist(symbol, period)
        if df.empty:
            return df

        try:
            import pandas_ta as ta
        except ImportError:
            return df

        # 列名映射
        col_map = {
            "日期": "Date", "开盘": "Open", "收盘": "Close",
            "最高": "High", "最低": "Low", "成交量": "Volume",
        }
        df_ta = df.rename(columns=col_map)
        df_ta["Date"] = pd.to_datetime(df_ta["Date"])
        df_ta.set_index("Date", inplace=True)

        for col in ["Open", "High", "Low", "Close", "Volume"]:
            df_ta[col] = pd.to_numeric(df_ta[col], errors="coerce")

        # 计算指标
        df_ta.ta.macd(fast=12, slow=26, signal=9, append=True)
        df_ta.ta.rsi(length=14, append=True)
        df_ta.ta.stoch(k=3, d=3, append=True)
        df_ta.ta.bbands(length=20, std=2, append=True)
        df_ta.ta.obv(append=True)
        df_ta.ta.atr(length=14, append=True)

        df_ta.reset_index(inplace=True)
        return df_ta

    def get_etf_basic_info(self, symbol: str) -> dict:
        """
        获取ETF基本信息：名称、跟踪指数、基金规模等
        """
        try:
            self._rate_limit()
            # fund_etf_spot_em 包含基本信息
            df = ak.fund_etf_spot_em()
            if df is not None and not df.empty:
                etf_data = df[df["代码"].astype(str) == symbol]
                if not etf_data.empty:
                    row = etf_data.iloc[0]
                    return {
                        "code": symbol,
                        "name": str(row.get("名称", "")),
                        "type": "ETF",
                    }
        except Exception:
            pass

        return {"code": symbol, "name": "", "type": "ETF"}

    def get_etf_with_index_pe(self, symbol: str) -> dict:
        """
        获取ETF及其跟踪指数的PE/PB百分位
        用于估值判断
        """
        result = self.get_etf_realtime(symbol)
        if "error" in result:
            return result

        # 尝试获取跟踪指数的估值数据
        # 常见ETF→指数映射
        index_map = {
            "510300": "000300",  # 沪深300ETF → 沪深300
            "510500": "000905",  # 中证500ETF → 中证500
            "159915": "399006",  # 创业板ETF → 创业板指
            "510050": "000016",  # 上证50ETF → 上证50
            "159941": "NDX",     # 纳指ETF → 纳斯达克100
            "513100": "NDX",     # 纳指ETF
            "513050": "KWEB",    # 中概互联ETF
        }

        index_code = index_map.get(symbol, "")
        if index_code:
            try:
                self._rate_limit()
                # 获取指数估值
                df = ak.stock_a_indicator_lg(symbol=index_code)
                if df is not None and not df.empty:
                    latest = df.iloc[0]
                    pe = self._safe_float(latest.get("pe", 0))
                    pb = self._safe_float(latest.get("pb", 0))

                    # 计算历史百分位
                    if "pe" in df.columns:
                        pe_values = df["pe"].dropna()
                        pe_percentile = (pe_values < pe).sum() / len(pe_values) * 100 if len(pe_values) > 0 else 50
                    else:
                        pe_percentile = 50

                    result["index_pe"] = pe
                    result["index_pb"] = pb
                    result["index_pe_percentile"] = round(pe_percentile, 1)
            except Exception:
                pass

        return result
