"""
FMP 数据获取器 - 适配 Stable API
"""

from typing import Any

import pandas as pd

from .base import BaseFetcher, FetchError


class FMPFetcher(BaseFetcher):
    """Financial Modeling Prep 数据获取器"""

    def _make_v3_request(self, endpoint: str, params: dict) -> Any:
        """发起 FMP v3 API 请求"""
        import requests
        self._rate_limit()

        params = params.copy()
        params["apikey"] = self.config.api_key

        # v3 API 使用不同的 base URL
        url = f"https://financialmodelingprep.com/api/v3/{endpoint}"

        for attempt in range(self.config.max_retries):
            try:
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.config.timeout,
                    proxies={"http": None, "https": None},
                )
                response.raise_for_status()

                data = response.json()

                if isinstance(data, dict) and "Error Message" in data:
                    raise FetchError(data["Error Message"], self.__class__.__name__)

                return data

            except requests.RequestException as e:
                if attempt == self.config.max_retries - 1:
                    raise FetchError(f"请求失败: {str(e)}", self.__class__.__name__)

                wait_time = (2 ** attempt) * self.config.rate_limit_delay
                import time
                time.sleep(wait_time)

    def _make_v4_request(self, endpoint: str, params: dict) -> Any:
        """发起 FMP v4 API 请求"""
        import requests
        self._rate_limit()

        params = params.copy()
        params["apikey"] = self.config.api_key

        # v4 API 使用不同的 base URL
        url = f"https://financialmodelingprep.com/api/v4/{endpoint}"

        for attempt in range(self.config.max_retries):
            try:
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.config.timeout,
                    proxies={"http": None, "https": None},
                )
                response.raise_for_status()

                data = response.json()

                if isinstance(data, dict) and "Error Message" in data:
                    raise FetchError(data["Error Message"], self.__class__.__name__)

                return data

            except requests.RequestException as e:
                if attempt == self.config.max_retries - 1:
                    raise FetchError(f"请求失败: {str(e)}", self.__class__.__name__)

                wait_time = (2 ** attempt) * self.config.rate_limit_delay
                import time
                time.sleep(wait_time)

    def get_income_statement(self, symbol: str) -> dict:
        """获取利润表"""
        def fetch():
            data = self._make_request("income-statement", {"symbol": symbol})
            if not data or not isinstance(data, list):
                return {}
            return self._parse_income(data[0])

        return self._cached_request(f"{symbol}_income", fetch)

    def get_balance_sheet(self, symbol: str) -> dict:
        """获取资产负债表"""
        def fetch():
            data = self._make_request("balance-sheet-statement", {"symbol": symbol})
            if not data or not isinstance(data, list):
                return {}
            return self._parse_balance(data[0])

        return self._cached_request(f"{symbol}_balance", fetch)

    def get_cash_flow(self, symbol: str) -> dict:
        """获取现金流量表"""
        def fetch():
            data = self._make_request("cash-flow-statement", {"symbol": symbol})
            if not data or not isinstance(data, list):
                return {}
            return self._parse_cashflow(data[0])

        return self._cached_request(f"{symbol}_cashflow", fetch)

    def _parse_income(self, raw: dict) -> dict:
        return {
            "date": raw.get("date", ""),
            "filing_date": raw.get("filingDate", ""),
            "revenue": raw.get("revenue", 0) or 0,
            "cost_of_goods_sold": raw.get("costOfRevenue", 0) or 0,
            "gross_profit": raw.get("grossProfit", 0) or 0,
            "operating_income": raw.get("operatingIncome", 0) or 0,
            "ebit": raw.get("ebit", 0) or 0,
            "ebitda": raw.get("ebitda", 0) or 0,
            "interest_expense": raw.get("interestExpense", 0) or 0,
            "income_tax_expense": raw.get("incomeTaxExpense", 0) or 0,
            "net_income": raw.get("netIncome", 0) or 0,
        }

    def _parse_balance(self, raw: dict) -> dict:
        return {
            "date": raw.get("date", ""),
            "filing_date": raw.get("filingDate", ""),
            "total_assets": raw.get("totalAssets", 0) or 0,
            "current_assets": raw.get("totalCurrentAssets", raw.get("totalAssets", 0) or 0),
            "cash_and_equivalents": raw.get("cashAndCashEquivalents", 0) or 0,
            "accounts_receivable": raw.get("netReceivables", 0) or 0,
            "inventory": raw.get("inventory", 0) or 0,
            "current_liabilities": raw.get("totalCurrentLiabilities", 0) or 0,
            "total_liabilities": raw.get("totalLiabilities", 0) or 0,
            "total_debt": raw.get("totalDebt", 0) or 0,
            "current_portion_long_term_debt": raw.get("currentLongTermDebt", 0) or 0,
            "shareholders_equity": raw.get("totalStockholdersEquity", 0) or 0,
            "goodwill": raw.get("goodwill", 0) or 0,
        }

    def _parse_cashflow(self, raw: dict) -> dict:
        return {
            "date": raw.get("date", ""),
            "filing_date": raw.get("filingDate", ""),
            "operating_cash_flow": raw.get("operatingCashFlow", 0) or 0,
            "investing_cash_flow": raw.get("netCashProvidedByInvestingActivities", 0) or raw.get("investingCashFlow", 0) or 0,
            "financing_cash_flow": raw.get("netCashProvidedByFinancingActivities", 0) or raw.get("financingCashFlow", 0) or 0,
            "capital_expenditure": abs(raw.get("capitalExpenditure", 0) or 0),
            "depreciation_amortization": raw.get("depreciationAndAmortization", 0) or 0,
            "free_cash_flow": raw.get("freeCashFlow", 0) or 0,
            "stock_based_compensation": raw.get("stockBasedCompensation", 0) or 0,
        }

    def get_ttm_data(self, symbol: str, shares: float = 0) -> dict:
        """计算TTM核心指标（FMP ratios-ttm 端点直接获取）"""
        result = {
            "ttm_net_income": 0, "ttm_revenue": 0, "ttm_eps": 0,
            "report_period": "", "is_anomalous": False,
            "annual_eps": 0, "annual_net_income": 0,
        }

        try:
            # 从 ratios-ttm 获取 TTM EPS + 估值指标（直接用预计算值）
            ratios = self._make_request("ratios-ttm", {"symbol": symbol})
            if ratios and isinstance(ratios, list) and len(ratios) > 0:
                r = ratios[0]
                ttm_eps = r.get("netIncomePerShareTTM") or 0
                if ttm_eps > 0 and shares > 0:
                    result["ttm_eps"] = round(ttm_eps, 4)
                    result["ttm_net_income"] = round(ttm_eps * shares, 0)

                # 直接提取 FMP 预计算的估值指标
                result["pe_ttm_fmp"] = r.get("priceToEarningsRatioTTM") or 0
                result["pb_ttm_fmp"] = r.get("priceToBookRatioTTM") or 0
                result["peg_ttm_fmp"] = r.get("priceToEarningsGrowthRatioTTM") or 0
                result["bvps_ttm_fmp"] = r.get("bookValuePerShareTTM") or 0

            # 从年报获取年度数据（用于对比和异常检测）
            annual = self._make_request("income-statement", {"symbol": symbol, "period": "annual", "limit": 2})
            if annual and isinstance(annual, list) and len(annual) > 0:
                latest = annual[0]
                result["report_period"] = latest.get("date", "")
                annual_ni = (latest.get("netIncome") or 0)
                if shares > 0:
                    result["annual_net_income"] = annual_ni
                    result["annual_eps"] = round(annual_ni / shares, 4)

                # 异常年检测：最新年报 vs 上年年报净利变动 > ±40%
                if len(annual) >= 2:
                    prev_ni = (annual[1].get("netIncome") or 0)
                    if prev_ni > 0 and annual_ni > 0:
                        change = abs(annual_ni / prev_ni - 1)
                        if change > 0.4:
                            result["is_anomalous"] = True

            # TTM revenue 从 key-metrics-ttm 补充
            if shares > 0:
                metrics = self._make_request("ratios-ttm", {"symbol": symbol})
                if metrics and isinstance(metrics, list) and len(metrics) > 0:
                    rev_per_share = metrics[0].get("revenuePerShareTTM") or 0
                    if rev_per_share > 0:
                        result["ttm_revenue"] = round(rev_per_share * shares, 0)

        except Exception:
            pass

        return result

    def get_pe_pb_history(self, symbol: str, years: int = 10) -> dict | None:
        """美股 PE/PB 年度历史(FMP /api/v3/ratios)。返回 {"pe":[...],"pb":[...]} 或 None(无 key/失败 → 降级)。"""
        try:
            data = self._make_v3_request("ratios", {"symbol": symbol, "limit": years})
            if not data or not isinstance(data, list):
                return None
            pe = [float(r.get("priceEarningsRatio") or 0) for r in data]
            pb = [float(r.get("priceToBookRatio") or 0) for r in data]
            pe = [x for x in pe if x > 0]
            pb = [x for x in pb if x > 0]
            return {"pe": pe, "pb": pb} if pe else None
        except Exception:
            return None

    def get_adjusted_closes(self, symbol: str, period: int = 4000) -> list:
        """美股前复权收盘(akshare stock_us_hist,免费;FMP historical-price-full 付费 403 已弃)。
        东财美股编码 105.XXX(纳斯达克)/106.XXX(纽交所),逐一试。
        降级链:qfq带日期 → 不复权带日期 → 不复权全历史(规避 qfq 返回空 + 超长 start_date 边界)。全失败 → []。"""
        import akshare as ak
        from datetime import datetime, timedelta
        end = datetime.now().strftime("%Y%m%d")
        start = (datetime.now() - timedelta(days=period)).strftime("%Y%m%d")
        variants = [("qfq", True), ("", True), ("", False)]
        for sym in (f"105.{symbol}", f"106.{symbol}"):
            for adjust, with_dates in variants:
                try:
                    if with_dates:
                        df = ak.stock_us_hist(symbol=sym, period="daily", start_date=start, end_date=end, adjust=adjust)
                    else:
                        df = ak.stock_us_hist(symbol=sym, period="daily", adjust=adjust)
                    if df is not None and not df.empty:
                        closes = df["收盘"].astype(float).tolist()
                        return closes[-period:] if len(closes) > period else closes
                except Exception:
                    continue
        return []

    def get_financial_data(self, symbol: str) -> dict[str, Any]:
        """获取完整财务数据"""
        return {
            "income_statement": self.get_income_statement(symbol),
            "balance_sheet": self.get_balance_sheet(symbol),
            "cash_flow": self.get_cash_flow(symbol),
        }

    def get_financial_data_multi_period(self, symbol: str, n: int = 5) -> list[dict]:
        """获取多期财务数据（年报）"""
        income_data = self._make_request("income-statement", {"symbol": symbol, "period": "annual", "limit": n})
        balance_data = self._make_request("balance-sheet-statement", {"symbol": symbol, "period": "annual", "limit": n})
        cashflow_data = self._make_request("cash-flow-statement", {"symbol": symbol, "period": "annual", "limit": n})

        if not income_data or not isinstance(income_data, list):
            return []

        results = []
        for i in range(min(n, len(income_data))):
            income = income_data[i] if i < len(income_data) else {}
            balance = balance_data[i] if i < len(balance_data) else {}
            cashflow = cashflow_data[i] if i < len(cashflow_data) else {}

            results.append({
                "income_statement": self._parse_income(income),
                "balance_sheet": self._parse_balance(balance),
                "cash_flow": self._parse_cashflow(cashflow),
            })

        return results

    def get_market_data(self, symbol: str) -> dict:
        """获取市场数据"""
        def fetch():
            quote = self._make_request("quote", {"symbol": symbol})
            if not quote or not isinstance(quote, list):
                return {}

            price = quote[0].get("price", 0) or 0

            if price <= 0:
                return {
                    "share_price": 0,
                    "shares_outstanding": 0,
                    "earnings_growth_rate": 0,
                }

            market_cap = quote[0].get("marketCap", 0) or 0
            shares_outstanding = market_cap / price if price > 0 else 0

            # 新 API 使用不同的增长率端点
            try:
                growth = self._make_request("financial-growth", {"symbol": symbol})
                earnings_growth = 0
                if growth and isinstance(growth, list) and len(growth) > 0:
                    eg = growth[0].get("netIncomeGrowth", 0) or 0
                    # netIncomeGrowth 已是小数形式（0.32 = 32%），无需再除100
                    earnings_growth = eg if isinstance(eg, (int, float)) else 0
            except FetchError:
                earnings_growth = 0

            return {
                "share_price": price,
                "shares_outstanding": shares_outstanding,
                "earnings_growth_rate": earnings_growth,
            }

        return self._cached_request(f"{symbol}_market", fetch)

    def get_social_sentiment(self, symbol: str, limit: int = 5) -> dict:
        """
        获取社交媒体情绪 (FMP v3 API)

        官方端点: /api/v3/historical/social-sentiment?symbol={symbol}

        注意: 此 API 可能需要付费订阅计划

        Args:
            symbol: 股票代码
            limit: 获取天数

        Returns:
            {
                "latest": 最新一日数据,
                "trend": [sentiment序列, ...],  # 最近5日
                "mentions_trend": [mentions序列, ...]
            }
        """
        def fetch():
            self._rate_limit()

            try:
                # FMP v3 API: historical/social-sentiment
                # 端点: /api/v3/historical/social-sentiment?symbol={symbol}
                data = self._make_v3_request(
                    "historical/social-sentiment",
                    {"symbol": symbol}
                )

                if not data or not isinstance(data, list):
                    return {"error": "无法获取社交媒体情绪，可能需要付费订阅"}

                # 获取最新数据
                latest = data[0]

                # 获取趋势 (最近5日)
                trend = []
                mentions_trend = []
                for item in data[:limit]:
                    sentiment = item.get("sentiment", 0)
                    mentions = item.get("mentions", 0)
                    if sentiment is not None:
                        trend.append(float(sentiment))
                    if mentions is not None:
                        mentions_trend.append(int(mentions))

                return {
                    "latest": latest,
                    "trend": trend,
                    "mentions_trend": mentions_trend
                }

            except FetchError as e:
                return {"error": f"社交媒体情绪获取失败: {str(e)}"}
            except Exception as e:
                return {"error": f"社交媒体情绪获取失败: {str(e)}"}

        # 缓存时间较短（情绪数据时效性高）
        return self._cached_request(f"{symbol}_social_sentiment", fetch)

    def get_news(self, symbol: str, limit: int = 5) -> dict:
        """
        获取最新新闻 (FMP Stable API)

        官方端点: /stable/news/stock?tickers={symbol}

        Args:
            symbol: 股票代码
            limit: 新闻数量

        Returns:
            {
                "news": [
                    {"title": "", "date": "", "url": "", "text": ""},
                    ...
                ]
            }
        """
        def fetch():
            self._rate_limit()

            try:
                # FMP Stable API: news/stock
                # 端点: /stable/news/stock?tickers={symbol}
                data = self._make_request(
                    "news/stock",
                    {"tickers": symbol}
                )

                if not data or not isinstance(data, list):
                    return {"news": []}

                news_list = []
                for item in data[:limit]:
                    news_list.append({
                        "title": item.get("title", ""),
                        "date": item.get("publishedDate", ""),
                        "url": item.get("url", ""),
                        "text": item.get("text", "")[:200],  # 截取前200字符
                    })

                return {"news": news_list}

            except FetchError as e:
                return {"error": f"新闻获取失败: {str(e)}"}
            except Exception as e:
                return {"error": f"新闻获取失败: {str(e)}"}

        # 新闻缓存时间较短
        return self._cached_request(f"{symbol}_news", fetch)

    def get_history(self, symbol: str, period: int = 100):
        """
        获取历史行情数据 (FMP Stable API)

        使用官方文档端点: /historical-price-eod/full?symbol={symbol}

        Args:
            symbol: 股票代码
            period: 获取天数

        Returns:
            DataFrame or None
        """
        self._rate_limit()

        try:
            # FMP Stable API: historical-price-eod/full
            # 官方文档: https://financialmodelingprep.com/stable/historical-price-eod/full?symbol=AAPL
            data = self._make_request(
                f"historical-price-eod/full",
                {"symbol": symbol}
            )

            if not data or not isinstance(data, list):
                return None

            # 转换为 DataFrame
            df = pd.DataFrame(data)

            # 标准化列名（与 AKShare 保持一致）
            df = df.rename(columns={
                "date": "日期",
                "open": "开盘",
                "close": "收盘",
                "high": "最高",
                "low": "最低",
                "volume": "成交量"
            })

            # 按日期升序排列（旧→新），技术指标计算要求时序正确
            df = df.sort_values("日期", ascending=True).tail(period).reset_index(drop=True)

            return df

        except Exception:
            return None
