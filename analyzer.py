"""
主分析器 v2
整合数据获取、杜邦分析、估值、风控、情绪、技术面
支持六维综合分析
"""

from typing import Any

from data import create_fetcher, parse_stock_input
from data.fetchers.akshare import AKShareFetcher
from data.fetchers.a_share_special import AShareSpecialFetcher
from data.fetchers.etf import ETFFetcher
from data.fetchers.hk_share import HKShareFetcher
from calculate_ratios import calculate_ratios_from_data
from interpret_ratios import perform_comprehensive_analysis
from sentiment import SentimentAnalyzer
from technical import TechnicalAnalyzer
from news import NewsFetcher
from comprehensive_score import ComprehensiveScorer
from dupont import DuPontAnalyzer
from holdings import analyze_holdings
from dca import analyze_dca
from valuation import ValuationAnalyzer
from risk_screening import RiskScreener
from sentiment_index import SentimentIndexAnalyzer

try:
    import pandas as pd
    HAS_PANDAS = True
except ImportError:
    HAS_PANDAS = False


class FinancialAnalyzer:
    """财务分析器 v2 — 六维综合分析"""

    def __init__(self):
        self.special_fetcher = AShareSpecialFetcher()
        self.etf_fetcher = ETFFetcher()
        self.hk_fetcher = HKShareFetcher()

    def analyze(self, user_input: str, industry: str = None, full_analysis: bool = False) -> dict[str, Any]:
        """
        基础分析（保留原有功能）
        """
        parsed = parse_stock_input(user_input)
        symbol = parsed.get("symbol", "")
        market = parsed.get("market", "")

        if not symbol:
            return {"error": "无法识别股票代码"}

        if market == "unknown":
            return {"error": f"无法识别市场类型: {symbol}"}

        # ETF 检测 — 走专用路径
        is_etf = len(symbol) == 6 and symbol[0] in ('1', '5')
        if is_etf:
            return self._analyze_etf(symbol, full_analysis)

        if industry is None:
            industry = self._auto_detect_industry(symbol, market)

        try:
            fetcher = create_fetcher(market=market)
            financial_data = fetcher.get_financial_data(symbol)
            market_data = fetcher.get_market_data(symbol)

            complete_data = {
                "income_statement": financial_data.get("income_statement", {}),
                "balance_sheet": financial_data.get("balance_sheet", {}),
                "cash_flow": financial_data.get("cash_flow", {}),
                "market_data": market_data,
            }

            if not complete_data["income_statement"].get("revenue"):
                return {"error": f"未找到 {symbol} 的财务数据"}

        except Exception as e:
            return {"error": f"数据获取失败: {str(e)}"}

        ratios = calculate_ratios_from_data(complete_data)
        analysis = perform_comprehensive_analysis(ratios["ratios"], industry=industry)

        dates = {}
        for stmt_name in ["income_statement", "balance_sheet", "cash_flow"]:
            stmt = financial_data.get(stmt_name, {})
            if stmt.get("date"):
                dates[stmt_name] = stmt["date"]

        result = {
            "symbol": symbol, "market": market,
            "data_source": fetcher.__class__.__name__,
            "dates": dates, "ratios": ratios, "analysis": analysis,
            "industry": industry, "market_data": market_data,
        }

        if full_analysis:
            try:
                result.update(self._get_extended_analysis(symbol, market, fetcher, result))
            except Exception as e:
                result["extended_error"] = f"扩展分析失败: {str(e)}"

        return result

    def _analyze_etf(self, symbol: str, full_analysis: bool = False) -> dict[str, Any]:
        """ETF 专用分析路径"""
        result = {"symbol": symbol, "market": "cn", "is_etf": True,
                  "data_source": "ETFFetcher"}

        # 实时数据
        try:
            realtime = self.etf_fetcher.get_etf_realtime(symbol)
            result["etf_realtime"] = realtime
            result["name"] = realtime.get("name", "")
        except Exception as e:
            result["etf_realtime"] = {"error": str(e)}

        # 基本信息
        try:
            info = self.etf_fetcher.get_etf_basic_info(symbol)
            if info.get("name") and not result.get("name"):
                result["name"] = info["name"]
        except Exception:
            pass

        # 技术面
        try:
            hist = self.etf_fetcher.get_etf_hist(symbol, period=100)
            if hist is not None and not hist.empty:
                ta = TechnicalAnalyzer(hist)
                result["technical"] = ta.analyze()
            else:
                result["technical"] = {"error": "无法获取历史数据"}
        except Exception as e:
            result["technical"] = {"error": str(e)}

        # 情绪面
        if full_analysis:
            try:
                sentiment = SentimentIndexAnalyzer()
                result["sentiment"] = sentiment.analyze_etf_sentiment(symbol)
            except Exception as e:
                result["sentiment"] = {"error": str(e)}

        return result

    def deep_analysis(self, user_input: str) -> dict[str, Any]:
        """深度六维分析"""
        parsed = parse_stock_input(user_input)
        symbol = parsed.get("symbol", "")
        market = parsed.get("market", "cn")

        if not symbol:
            return {"error": "无法识别股票代码"}

        # ETF → 专用深度路径
        is_etf = len(symbol) == 6 and symbol.startswith(('1', '5'))
        if is_etf:
            return self._deep_analyze_etf(symbol)

        # ── A股/港股/美股 深度分析 ──
        result = {"symbol": symbol, "market": market, "is_etf": False}

        try:
            fetcher = create_fetcher(market=market)
            financial_data = fetcher.get_financial_data(symbol)
            market_data = fetcher.get_market_data(symbol)
            multi_period = fetcher.get_financial_data_multi_period(symbol, n=5)

            result["financial_data"] = financial_data
            result["market_data"] = market_data
            result["multi_period"] = multi_period

        except Exception as e:
            result["error"] = f"数据获取失败: {str(e)}"
            return result

        # 年报数据（杜邦/估值/风控统一用年报，避免季报偏差）
        annual_data = multi_period[0] if multi_period else financial_data

        # TTM + 股息率注入（优先使用 FMP ratios-ttm 预计算值）
        shares = market_data.get("shares_outstanding", 0)
        try:
            ttm_data = fetcher.get_ttm_data(symbol, shares=shares)
            market_data["ttm_eps"] = ttm_data.get("ttm_eps", 0)
            market_data["ttm_net_income"] = ttm_data.get("ttm_net_income", 0)
            market_data["is_anomalous_year"] = ttm_data.get("is_anomalous", False)
            market_data["annual_eps"] = ttm_data.get("annual_eps", 0)

            # FMP ratios-ttm 预计算估值指标（直接使用，不再自己算）
            fmp_pe = ttm_data.get("pe_ttm_fmp", 0)
            if fmp_pe > 0:
                market_data["pe_ttm"] = round(fmp_pe, 2)
            elif market_data["share_price"] > 0 and market_data["ttm_eps"] > 0:
                market_data["pe_ttm"] = round(market_data["share_price"] / market_data["ttm_eps"], 2)

            fmp_pb = ttm_data.get("pb_ttm_fmp", 0)
            if fmp_pb > 0:
                market_data["pb_ttm"] = round(fmp_pb, 2)

            # PEG：不用 FMP 预计算值（经常失真），用 3 年净利润 CAGR 自算
            # FMP 的 peg_ttm_fmp 对高增长股经常给出极端值（如 GOOGL 的 0.66）
            earnings_cagr = 0
            if multi_period and len(multi_period) >= 3:
                ni_list = []
                for p in multi_period[:4]:  # 取最近4年算3年CAGR
                    ni = p.get("income_statement", {}).get("net_income", 0)
                    if ni > 0:
                        ni_list.append(ni)
                if len(ni_list) >= 2 and ni_list[-1] > 0:
                    n = len(ni_list) - 1
                    earnings_cagr = (ni_list[0] / ni_list[-1]) ** (1 / n) - 1
                    earnings_cagr = max(min(earnings_cagr, 0.50), 0.01)  # 限制在 1%-50%
            if earnings_cagr > 0 and market_data.get("pe_ttm", 0) > 0:
                market_data["peg_ratio"] = round(market_data["pe_ttm"] / (earnings_cagr * 100), 2)
                market_data["peg_growth_rate"] = round(earnings_cagr * 100, 1)
            else:
                fmp_peg = ttm_data.get("peg_ttm_fmp", 0)
                if fmp_peg > 0:
                    market_data["peg_ratio"] = round(fmp_peg, 2)

            fmp_bvps = ttm_data.get("bvps_ttm_fmp", 0)
            if fmp_bvps > 0:
                market_data["book_value_per_share"] = round(fmp_bvps, 2)

            if market_data["share_price"] > 0 and market_data["annual_eps"] > 0:
                market_data["pe_static"] = round(market_data["share_price"] / market_data["annual_eps"], 2)
        except Exception:
            pass

        # 基础比率
        complete_data = {
            "income_statement": annual_data.get("income_statement", {}),
            "balance_sheet": annual_data.get("balance_sheet", {}),
            "cash_flow": annual_data.get("cash_flow", {}),
            "market_data": market_data,
        }
        result["ratios"] = calculate_ratios_from_data(
            complete_data,
            prev_period=multi_period[1] if len(multi_period) > 1 else None,
        )

        # 杜邦分析
        try:
            dupont = DuPontAnalyzer()
            result["dupont"] = dupont.analyze_trend(multi_period)
        except Exception as e:
            result["dupont"] = {"error": str(e)}

        # 估值分析
        try:
            val = ValuationAnalyzer()
            industry_peers = fetcher.get_industry_peers(symbol) if hasattr(fetcher, 'get_industry_peers') else {}
            pe_history = fetcher.get_pe_pb_history(symbol) if hasattr(fetcher, 'get_pe_pb_history') else None
            result["valuation"] = val.comprehensive_valuation(
                annual_data, market_data, multi_period, industry_peers, pe_history=pe_history
            )
        except Exception as e:
            result["valuation"] = {"error": str(e)}

        # 技术面
        try:
            hist = fetcher.get_history(symbol, period=100)
            if hist is not None and not hist.empty:
                ta = TechnicalAnalyzer(hist)
                result["technical"] = ta.analyze()
            else:
                result["technical"] = {"error": "无法获取历史数据"}
        except Exception as e:
            result["technical"] = {"error": str(e)}

        # 持有体验（长期持有期回报 + 回撤 + 定投，长期价值决策核心）
        closes = fetcher.get_adjusted_closes(symbol, period=4000) if hasattr(fetcher, 'get_adjusted_closes') else []
        try:
            result["holdings"] = analyze_holdings(closes)
        except Exception as e:
            result["holdings"] = {"error": str(e)}
        try:
            result["dca"] = analyze_dca(closes)  # 复用同一根 closes，无二次取数；独立 try 与 holdings 隔离降级
        except Exception as e:
            result["dca"] = {"error": str(e)}

        # 风控
        try:
            risk = RiskScreener()
            pledge_data = self.special_fetcher.get_pledge_data(symbol)
            result["risk"] = risk.comprehensive_risk_check(multi_period, market_data, pledge_data, market=market)
        except Exception as e:
            result["risk"] = {"error": str(e)}

        # 情绪面
        try:
            sentiment = SentimentIndexAnalyzer()
            result["sentiment"] = sentiment.analyze_market_sentiment(market=market)
        except Exception as e:
            result["sentiment"] = {"error": str(e)}

        # 综合评分
        try:
            scorer = ComprehensiveScorer()
            result["comprehensive"] = scorer.calculate_overall_score({
                "fundamental": result.get("dupont", {}),
                "valuation": result.get("valuation", {}),
                "technical": result.get("technical", {}),
                "sentiment": result.get("sentiment", {}),
                "risk": result.get("risk", {}),
                "market_temp": result.get("sentiment", {}),
            })
        except Exception as e:
            result["comprehensive"] = {"error": str(e)}

        return result

    def _deep_analyze_etf(self, symbol: str) -> dict[str, Any]:
        """ETF 深度六维分析（无财报，走溢价+技术+情绪路径）"""
        result = {"symbol": symbol, "market": "cn", "is_etf": True}

        # 1. 实时行情（含溢价/IOPV）
        try:
            realtime = self.etf_fetcher.get_etf_realtime(symbol)
            result["etf_realtime"] = realtime
            result["name"] = realtime.get("name", "")
            if realtime.get("_data_source"):
                result["_premium_source"] = realtime["_data_source"]
        except Exception as e:
            result["etf_realtime"] = {"error": str(e)}

        # 2. 历史行情 + 统计
        try:
            hist = self.etf_fetcher.get_etf_hist(symbol, period=120)
            if hist is not None and not hist.empty:
                result["hist_stats"] = self._calc_hist_stats(hist)
            else:
                result["hist_stats"] = {"error": "无法获取历史数据"}
        except Exception as e:
            result["hist_stats"] = {"error": str(e)}

        # 3. 技术面
        try:
            hist = self.etf_fetcher.get_etf_hist(symbol, period=120)
            if hist is not None and not hist.empty:
                ta = TechnicalAnalyzer(hist)
                result["technical"] = ta.analyze()
            else:
                result["technical"] = {"error": "无法获取历史数据"}
        except Exception as e:
            result["technical"] = {"error": str(e)}

        # 持有体验（ETF 长期持有期 + 回撤 + 定投,前复权避免分红除息扭曲）
        closes = self.etf_fetcher.get_adjusted_closes(symbol, period=4000) if hasattr(self.etf_fetcher, 'get_adjusted_closes') else []
        try:
            result["holdings"] = analyze_holdings(closes) if closes else {"empty": True}
        except Exception as e:
            result["holdings"] = {"error": str(e)}
        try:
            result["dca"] = analyze_dca(closes) if closes else {"empty": True}
        except Exception as e:
            result["dca"] = {"error": str(e)}

        # 4. 情绪面（ETF专用：恐贪+资金流向+溢价情绪）
        try:
            sentiment = SentimentIndexAnalyzer()
            result["sentiment"] = sentiment.analyze_etf_sentiment(symbol)
        except Exception as e:
            result["sentiment"] = {"error": str(e)}

        # 5. 综合评分（ETF维度：技术面+情绪面+溢价风险）
        try:
            scorer = ComprehensiveScorer()
            result["comprehensive"] = scorer.calculate_etf_score({
                "technical": result.get("technical", {}),
                "sentiment": result.get("sentiment", {}),
                "premium": result.get("etf_realtime", {}),
            })
        except Exception as e:
            result["comprehensive"] = {"error": str(e)}

        return result

    def _format_holdings(self, h: dict) -> list:
        """格式化持有体验段(持有期分布 + 回撤)。空/错误 → []。"""
        if not h or h.get("empty") or "error" in h:
            return []
        out = ["## ⏳ 持有体验（长期）"]
        for y in (3, 5, 10):
            p = h.get("holding_periods", {}).get(y)
            if p:
                out.append(f"- 持有 {y} 年：中位年化 **{p['median_cagr']}%** · 最坏 **{p['worst_cagr']}%** · 不亏概率 **{p['prob_no_loss']}%**（{p['samples']} 个样本）")
        dd = h.get("drawdown", {})
        if dd:
            rec = f"· {dd['recovery_years']} 年恢复" if dd.get("recovery_years") else "· 至今未恢复"
            out.append(f"- 历史最大回撤 **{dd['max_drawdown']}%** {rec}")
        out.append("")
        return out

    def _format_dca(self, d: dict) -> list:
        """格式化定投体验段(定投滚动分布 + 定投 vs 满仓)。空/错误 → []。"""
        if not d or d.get("empty") or "error" in d:
            return []
        out = ["## 📅 定投体验（月定投）"]
        for y in (3, 5, 10):
            p = d.get("dca_periods", {}).get(y)
            if p:
                out.append(f"- 定投 {y} 年：中位年化 **{p['median_cagr']}%** · 最坏 **{p['worst_cagr']}%** · 不亏概率 **{p['prob_no_loss']}%**（{p['samples']} 个样本）")
        v = d.get("vs_lumpsum", {})
        if v:
            yrs = v.get("years_full")
            def _pct(x):
                return f"+{x}%" if isinstance(x, (int, float)) and x >= 0 else f"{x}%"
            # 短历史标的(成立<3年):连最小滚动期(3年)都凑不齐,全周期单一样本 XIRR
            # 无统计意义(实测 0.5 年标的 XIRR 飙到 140%、2.8 年 109%),不输出全周期对照
            if isinstance(yrs, (int, float)) and yrs < 3:
                out.append(f"- 全周期仅 {yrs} 年：⚠️ 成立不足 3 年，定投/满仓全周期对照样本严重不足、XIRR 易被短线暴涨扭曲，**不具参考价值**；请待更长历史后再看")
            else:
                yrs_s = yrs if isinstance(yrs, (int, float)) else "?"
                # 并列两个口径、不二选一:累计收益(谁赚得多)与 XIRR(资金效率年化)常矛盾——
                # 满仓累计通常更高(资金全程在场),定投 XIRR 常更高(晚期短线暴利放大),
                # 简单给「定投/满仓胜」会误导。定投真正优势在风险(分批摊低、最坏更稳)
                out.append(f"- 全周期（{yrs_s}年，单一样本）：满仓累计 **{_pct(v.get('lumpsum_total_return'))}** vs 定投累计 **{_pct(v.get('dca_total_return'))}**")
                out.append(f"  · 满仓绝对收益通常更高（资金全程在场吃满涨幅）；定投 XIRR（{v.get('dca_cagr')}% vs 满仓 {v.get('lumpsum_cagr')}%）更高，但那是资金效率年化、对后期暴涨敏感、非真实年均")
                out.append(f"  · 定投真正价值在风险：分批摊低成本、最坏情况更稳（见上方滚动「最坏」）。看概率请参考 3/5 年滚动分布")
        out.append("")
        return out

    def _calc_hist_stats(self, hist) -> dict:
        """计算历史行情统计"""
        import pandas as pd
        closes = hist["收盘"].astype(float)
        volumes = hist["成交量"].astype(float)
        return {
            "high_120d": round(closes.max(), 3),
            "low_120d": round(closes.min(), 3),
            "return_120d": round((closes.iloc[-1] / closes.iloc[0] - 1) * 100, 2),
            "return_20d": round((closes.iloc[-1] / closes.iloc[-20] - 1) * 100, 2) if len(closes) >= 20 else None,
            "return_5d": round((closes.iloc[-1] / closes.iloc[-5] - 1) * 100, 2) if len(closes) >= 5 else None,
            "avg_volume_20d": round(volumes.tail(20).mean() / 1e8, 2),
        }

    def valuation_analysis(self, user_input: str) -> dict[str, Any]:
        """估值分析：杜邦 + DCF + 蒙特卡洛（仅限A股/美股，ETF无财报）"""
        parsed = parse_stock_input(user_input)
        symbol = parsed.get("symbol", "")

        is_etf = len(symbol) == 6 and symbol.startswith(('1', '5'))
        if is_etf:
            return {"error": "ETF无财报数据，估值分析不适用。请使用基础分析或深度分析。"}

        market = parsed.get("market", "cn")
        fetcher = create_fetcher(market=market)
        financial_data = fetcher.get_financial_data(symbol)
        market_data = fetcher.get_market_data(symbol)
        multi_period = fetcher.get_financial_data_multi_period(symbol, n=5)

        annual_data = multi_period[0] if multi_period else financial_data

        dupont = DuPontAnalyzer()
        val = ValuationAnalyzer()

        return {
            "symbol": symbol,
            "dupont": dupont.analyze_trend(multi_period),
            "valuation": val.comprehensive_valuation(annual_data, market_data, multi_period),
        }

    def timing_analysis(self, user_input: str) -> dict[str, Any]:
        """择时分析：全量技术指标 + 多指标共振"""
        parsed = parse_stock_input(user_input)
        symbol = parsed.get("symbol", "")

        is_etf = len(symbol) == 6 and symbol.startswith(('1', '5'))

        if is_etf:
            hist = self.etf_fetcher.get_etf_hist(symbol, period=120)
            realtime = self.etf_fetcher.get_etf_realtime(symbol)
        else:
            market = parsed.get("market", "cn")
            fetcher = create_fetcher(market=market)
            hist = fetcher.get_history(symbol, period=100)
            realtime = {}

        if hist is None or hist.empty:
            return {"error": "无法获取历史数据"}

        ta = TechnicalAnalyzer(hist)
        result = {"symbol": symbol, "technical": ta.analyze()}
        if is_etf and realtime:
            result["etf_realtime"] = realtime
            result["name"] = realtime.get("name", "")
        return result

    def risk_check(self, user_input: str) -> dict[str, Any]:
        """风险排查：Beneish + Altman + Piotroski + A股特色（仅限A股，ETF无财报）"""
        parsed = parse_stock_input(user_input)
        symbol = parsed.get("symbol", "")

        is_etf = len(symbol) == 6 and symbol.startswith(('1', '5'))
        if is_etf:
            return {"error": "ETF无财报数据，风控排查不适用。请使用深度分析查看溢价风险。"}

        market = parsed.get("market", "cn")
        fetcher = create_fetcher(market=market)
        financial_data = fetcher.get_financial_data(symbol)
        market_data = fetcher.get_market_data(symbol)
        multi_period = fetcher.get_financial_data_multi_period(symbol, n=5)

        risk = RiskScreener()
        pledge_data = self.special_fetcher.get_pledge_data(symbol)

        return {
            "symbol": symbol,
            "risk": risk.comprehensive_risk_check(multi_period, market_data, pledge_data),
        }

    def _get_extended_analysis(self, symbol: str, market: str, fetcher, base_result: dict) -> dict:
        """扩展分析（兼容旧接口）"""
        extended = {}

        if not HAS_PANDAS:
            return {"extended_error": "需要 pandas 库"}

        # 情绪
        try:
            sentiment_analyzer = SentimentAnalyzer(fetcher)
            extended["sentiment"] = sentiment_analyzer.analyze_social_sentiment(symbol, market)
        except Exception as e:
            extended["sentiment"] = {"error": str(e)}

        # 技术面
        try:
            hist_data = fetcher.get_history(symbol, period=100)
            if hist_data is not None and not hist_data.empty:
                ta = TechnicalAnalyzer(hist_data)
                extended["technical"] = ta.analyze()
            else:
                extended["technical"] = {"error": "无法获取历史数据"}
        except Exception as e:
            extended["technical"] = {"error": str(e)}

        # 新闻
        try:
            news_fetcher = NewsFetcher(fetcher)
            news_data = news_fetcher.get_latest_news(symbol)
            extended["news"] = news_fetcher.analyze_news_sentiment(news_data, market)
        except Exception as e:
            extended["news"] = {"error": str(e)}

        # 综合评分
        try:
            scorer = ComprehensiveScorer()
            extended["comprehensive"] = scorer.calculate_overall_score({
                "fundamental": base_result,
                "sentiment": extended.get("sentiment", {}),
                "technical": extended.get("technical", {}),
                "news": extended.get("news", {}),
            })
        except Exception as e:
            extended["comprehensive"] = {"error": str(e)}

        return extended

    def _auto_detect_industry(self, symbol: str, market: str) -> str:
        """动态行业检测"""
        if market == "cn":
            try:
                fetcher = create_fetcher(market="cn")
                if hasattr(fetcher, 'get_industry'):
                    return fetcher.get_industry(symbol)
            except Exception:
                pass
        return "general"

    def format_report(self, analysis_result: dict) -> str:
        """格式化分析报告"""
        if "error" in analysis_result:
            return f"❌ {analysis_result['error']}"

        lines = []
        symbol = analysis_result.get("symbol", "")
        name = analysis_result.get("name", "")

        # ETF 报告
        if analysis_result.get("is_etf"):
            return self._format_etf_report(analysis_result)

        title = f"{name} ({symbol})" if name else symbol
        lines.append(f"# 📊 {title} 财务分析报告")
        lines.append("")

        # 实时行情（A股）
        md = analysis_result.get("market_data", {})
        if md and md.get("share_price", 0) > 0 and not analysis_result.get("is_etf"):
            lines.append("## 实时行情")
            lines.append(f"- 最新价: {md['share_price']}")
            cp = md.get("change_pct", 0)
            if cp:
                lines.append(f"- 涨跌幅: {cp}%")
            if md.get("open") or md.get("prev_close"):
                lines.append(f"- 今开/昨收: {md.get('open', 0)} / {md.get('prev_close', 0)}")
            if md.get("high") or md.get("low"):
                lines.append(f"- 最高/最低: {md.get('high', 0)} / {md.get('low', 0)}")
            amt = md.get("amount", 0)
            if amt:
                lines.append(f"- 成交额: {amt / 1e8:.2f} 亿")
            tr = md.get("turnover_rate", 0)
            if tr:
                lines.append(f"- 换手率: {tr}%")
            mc = md.get("market_cap", 0)
            if mc:
                lines.append(f"- 总市值: {mc / 1e8:.0f} 亿")
            lines.append("")

        # 基础分析（兼容旧格式）
        if "ratios" in analysis_result:
            lines.append("## 基础财务指标")
            interp = analysis_result["ratios"].get("interpretations", {})
            if interp:
                metric_zh = {
                    "roe": "ROE", "roa": "ROA", "gross_margin": "毛利率",
                    "operating_margin": "营业利润率", "net_margin": "净利率",
                    "current_ratio": "流动比率", "quick_ratio": "速动比率", "cash_ratio": "现金比率",
                    "debt_to_equity": "资产负债率", "interest_coverage": "利息覆盖",
                    "asset_turnover": "资产周转率", "inventory_turnover": "存货周转率",
                    "pe_ratio": "PE", "pb_ratio": "PB", "ps_ratio": "PS", "eps": "EPS",
                }
                for category, metrics in interp.items():
                    if isinstance(metrics, dict):
                        parts = []
                        for metric_name, metric_data in metrics.items():
                            if isinstance(metric_data, dict) and metric_data.get("formatted"):
                                val = metric_data["value"]
                                if val != 0:
                                    label = metric_zh.get(metric_name, metric_name)
                                    parts.append(f"{label}={metric_data['formatted']}")
                        if parts:
                            lines.append(f"- {', '.join(parts)}")
            lines.append("")

        # 估值对比（TTM vs 静态 + 股息率）
        pe_ttm = md.get("pe_ttm", 0)
        pe_static = md.get("pe_static", 0)
        dividend_yield = md.get("dividend_yield", 0)
        is_anomalous = md.get("is_anomalous_year", False)
        div_warning = md.get("dividend_warning")
        if pe_ttm > 0 or dividend_yield > 0:
            lines.append("## 💡 估值对比")
            if pe_static > 0:
                lines.append(f"- 静态PE: {pe_static}x（基于年报EPS={md.get('annual_eps', 0):.2f}）")
            if pe_ttm > 0:
                lines.append(f"- TTM PE: {pe_ttm}x（滚动12月EPS={md.get('ttm_eps', 0):.2f}）")
            if dividend_yield > 0:
                avg_dps = md.get("avg_3y_dps", 0)
                tag = " 🛡️ 高股息支撑" if dividend_yield >= 4 else ""
                extra = f"（3年均值: {avg_dps:.2f}）" if avg_dps > 0 else ""
                lines.append(f"- 股息率: {dividend_yield}%{extra}{tag}")
            if is_anomalous:
                lines.append("⚠️ 盈利异常波动期：静态PE可能失真，建议参考TTM数据")
            if div_warning:
                lines.append(f"⚠️ {div_warning}")
            if pe_static > 0 and pe_ttm > 0 and abs(pe_static - pe_ttm) / pe_ttm > 0.3:
                lines.append("⚠️ 估值口径分歧：静态PE与TTM PE差异超30%，建议关注TTM")
            lines.append("")

        # PE/PB 历史百分位（长期价值买点核心）
        val_full = analysis_result.get("valuation", {})
        pct = val_full.get("pe_pb_percentile") or {}
        if pct.get("pe_percentile") is not None:
            lines.append("## 📐 估值历史百分位")
            lines.append(f"- PE 百分位: **{pct['pe_percentile']}%**（{pct.get('pe_status')}）— 当前 PE {pct.get('current_pe')} 在近 {pct.get('sample_years')} 年的位置（<30% 便宜，>70% 偏贵）")
            if pct.get("pb_percentile") is not None:
                lines.append(f"- PB 百分位: **{pct['pb_percentile']}%**（{pct.get('pb_status')}）— 当前 PB {pct.get('current_pb')}")
            lines.append("")
        elif val_full and "error" not in val_full:
            lines.append("## 📐 估值历史百分位")
            lines.append("- 暂无 PE 历史百分位（美股/港股免费源待补），参考上方 DCF 内在价值 + 当前 PE 绝对值判断贵贱")
            lines.append("")

        # 杜邦分析
        if "dupont" in analysis_result:
            lines.append("## 📐 杜邦分析")
            dp = analysis_result["dupont"]
            if "error" not in dp:
                latest = dp.get("latest", {}).get("dupont_3", {})
                lines.append(f"- ROE: {latest.get('roe', 0)}%")
                lines.append(f"- 净利率: {latest.get('net_profit_margin', 0)}%")
                lines.append(f"- 资产周转率: {latest.get('asset_turnover', 0)}")
                lines.append(f"- 权益乘数: {latest.get('equity_multiplier', 0)}")
                driver = dp.get("driver", {})
                lines.append(f"- 驱动因素: {driver.get('main_driver', '未知')} — {driver.get('explanation', '')}")
                quality = dp.get("quality", {})
                lines.append(f"- ROE质量: {quality.get('rating', '未知')} ({quality.get('score', 0)}/8)")
            else:
                lines.append(f"⚠️ {dp['error']}")
            lines.append("")

        # 估值分析
        if "valuation" in analysis_result:
            lines.append("## 💰 估值分析")
            val = analysis_result["valuation"]
            if "error" not in val:
                dcf = val.get("dcf", {})
                lines.append(f"- DCF内在价值: {dcf.get('per_share_value', 0)} 元/股")
                safety = val.get("safety_margin", {})
                lines.append(f"- 安全边际: {safety.get('safety_margin', 0)}% ({safety.get('signal', '')})")
                reverse = val.get("reverse_dcf", {})
                lines.append(f"- 隐含增长率: {reverse.get('implied_growth_rate', 0)}% — {reverse.get('interpretation', '')}")
                graham = val.get("graham_number", {})
                if graham.get("graham_number"):
                    lines.append(f"- 格雷厄姆数值: {graham['graham_number']} 元")
                mc = val.get("monte_carlo", {}).get("fair_value_distribution", {})
                if mc:
                    lines.append(f"- 蒙特卡洛 P25-P75: {mc.get('p25', 0)} - {mc.get('p75', 0)} 元")
            else:
                lines.append(f"⚠️ {val['error']}")
            lines.append("")

            # 情景分析（概率加权）
            scenario = val.get("scenario_analysis", {})
            if scenario and scenario.get("scenarios"):
                lines.append("## 📊 情景分析（概率加权）")
                current = md.get("share_price", 0)
                for path_name, path_data in scenario["scenarios"].items():
                    path_zh = {"bull": "乐观路径", "base": "中性路径", "bear": "悲观路径"}.get(path_name, path_name)
                    v = path_data["value"]
                    prob = path_data["probability"]
                    pct_str = ""
                    if current > 0 and v > 0:
                        pct = (v - current) / current * 100
                        pct_str = f" ({'+' if pct > 0 else ''}{pct:.0f}%)"
                    lines.append(f"- {path_zh} ({int(prob*100)}%): {v}元{pct_str}")
                expected = scenario.get("expected_value", 0)
                lines.append(f"- 综合期望值: {expected}元")
                if current > 0 and expected > 0:
                    upside = scenario.get("upside", 0)
                    downside = scenario.get("downside", 0)
                    up_pct = (upside - current) / current * 100
                    dn_pct = (downside - current) / current * 100
                    lines.append(f"💡 赔率判断: 上行空间{up_pct:.0f}% vs 下行风险{dn_pct:.0f}%")
                    if dividend_yield >= 4:
                        lines.append(f"🛡️ 高股息({dividend_yield}%)封杀下行空间")
                lines.append("")

            # 估值信号
            signals = val.get("valuation_signals", {})
            if signals and signals.get("dcf_method") and signals["dcf_method"] != "DCF":
                lines.append(f"📌 估值方法: {signals['dcf_method']}")
                lines.append("")

        # 技术面
        if "technical" in analysis_result:
            lines.append("## 📈 技术面")
            tech = analysis_result["technical"]
            if "error" not in tech:
                lines.append(f"- 择时信号: {tech.get('timing_signal', '未知')} (置信度: {tech.get('confidence', 0)}%)")
                macd = tech.get("macd", {})
                lines.append(f"- MACD: DIF={macd.get('dif', 0)}, DEA={macd.get('dea', 0)}, 信号={macd.get('signal', '')}")
                rsi = tech.get("rsi", {})
                lines.append(f"- RSI: {rsi.get('rsi', 0)} ({rsi.get('status', '')})")
                kdj = tech.get("kdj", {})
                lines.append(f"- KDJ: K={kdj.get('k', 0)}, D={kdj.get('d', 0)}, J={kdj.get('j', 0)}")
                boll = tech.get("bollinger", {})
                lines.append(f"- 布林带: 上={boll.get('upper', 0)}, 中={boll.get('middle', 0)}, 下={boll.get('lower', 0)}")
                vol = tech.get("volume_price", {})
                lines.append(f"- 量价: {vol.get('signal', '')} {vol.get('warning', '')}")
            else:
                lines.append(f"⚠️ {tech['error']}")
            lines.append("")

        # 风控
        if "risk" in analysis_result:
            lines.append("## 🛡️ 风险排查")
            risk = analysis_result["risk"]
            if "error" not in risk:
                lines.append(f"- 综合风险: {risk.get('total_risk_level', '未知')} (评分: {risk.get('total_risk_score', 0)}/100)")
                beneish = risk.get("beneish_m", {})
                lines.append(f"- Beneish M-Score: {beneish.get('m_score', 'N/A')} — {beneish.get('risk', '')}")
                altman = risk.get("altman_z", {})
                lines.append(f"- Altman Z-Score: {altman.get('z_score', 'N/A')} — {altman.get('zone', '')}")
                piotroski = risk.get("piotroski_f", {})
                lines.append(f"- Piotroski F-Score: {piotroski.get('f_score', 'N/A')}/9 — {piotroski.get('signal', '')}")
                a_share = risk.get("a_share_checks", {})
                if a_share.get("checks"):
                    lines.append("- A股特色检查:")
                    for check in a_share["checks"]:
                        lines.append(f"  - {check['name']}: {check['value']} [{check['light']}] {check['desc']}")
            else:
                lines.append(f"⚠️ {risk['error']}")
            lines.append("")

        # 情绪面
        if "sentiment" in analysis_result:
            lines.append("## 🌡️ 市场情绪")
            sent = analysis_result["sentiment"]
            if "error" not in sent:
                if sent.get("composite_score") is None:
                    lines.append(f"- {sent.get('advice', '情绪面暂不支持')}")
                elif "composite_score" in sent:
                    lines.append(f"- 综合情绪: {sent['composite_score']}/100 — {sent['level']}")
                    lines.append(f"- 建议: {sent['advice']}")
                    for dim_name, dim_data in sent.get("dimensions", {}).items():
                        if isinstance(dim_data, dict) and "score" in dim_data:
                            lines.append(f"  - {dim_name}: {dim_data['score']}/100 — {dim_data.get('status', '')}")
                elif "sentiment_score" in sent:
                    lines.append(f"- 情绪评分: {sent['sentiment_score']}/100")
            else:
                lines.append(f"⚠️ {sent.get('error', '')}")
            lines.append("")

        # 持有体验（长期持有期 + 回撤 + 定投）
        lines.extend(self._format_holdings(analysis_result.get("holdings") or {}))
        lines.extend(self._format_dca(analysis_result.get("dca") or {}))

        # 综合评分
        if "comprehensive" in analysis_result:
            lines.append("## 🎯 综合评分")
            comp = analysis_result["comprehensive"]
            if "error" not in comp:
                rating_emoji = {"优秀": "🟢", "良好": "🟡", "一般": "🟠", "较差": "🔴"}.get(comp.get('rating', ''), "⚪")
                lines.append(f"- 综合评分: {comp.get('overall_score', 0)}/100 ({rating_emoji} {comp.get('rating', '')})")
                for name, score in comp.get("scores", {}).items():
                    name_zh = {"fundamental": "基本面", "valuation": "估值", "technical": "技术面", "sentiment": "情绪面", "risk": "风控", "market_temp": "市场温度"}.get(name, name)
                    lines.append(f"  - {name_zh}: {score}/100")
                rec = comp.get("recommendation", {})
                lines.extend([
                    "", "**操作建议**:",
                    f"  - 操作: {rec.get('action', '')}",
                    f"  - 信心: {rec.get('confidence', '')}",
                ])
                if rec.get("target_price"):
                    lines.append(f"  - 目标价: {rec['target_price']}元")
                if rec.get("stop_loss"):
                    lines.append(f"  - 止损价: {rec['stop_loss']}元")
                lines.append(f"  - 周期: {rec.get('time_horizon', '')}")
                lines.append(f"  - 安全边际: {rec.get('safety_margin', '')}")
            else:
                lines.append(f"⚠️ {comp['error']}")

        return "\n".join(lines)

    def _format_etf_report(self, r: dict) -> str:
        """ETF 专用报告格式"""
        lines = []
        symbol = r.get("symbol", "")
        name = r.get("name", "")
        title = f"{name} ({symbol})" if name else symbol
        lines.append(f"# 📊 {title} ETF 分析报告")
        lines.append("")

        # 实时行情
        rt = r.get("etf_realtime", {})
        if "error" not in rt:
            lines.append("## 实时行情")
            lines.append(f"- 最新价: {rt.get('price', 0)}")
            lines.append(f"- 涨跌幅: {rt.get('change_pct', 0)}%")
            lines.append(f"- 今开/昨收: {rt.get('open', 0)} / {rt.get('prev_close', 0)}")
            lines.append(f"- 最高/最低: {rt.get('high', 0)} / {rt.get('low', 0)}")
            amt = rt.get("amount", 0)
            if amt:
                lines.append(f"- 成交额: {amt / 1e8:.2f} 亿")
            iopv = rt.get("iopv", 0)
            premium = rt.get("premium_rate", 0)
            if iopv or premium:
                lines.append(f"- IOPV净值: {iopv}")
                lines.append(f"- 溢折价率: {premium}%")
            lines.append("")

        # 技术面
        tech = r.get("technical", {})
        if "error" not in tech:
            lines.append("## 📈 技术面")
            signal = tech.get("timing_signal", "")
            confidence = tech.get("confidence", 0)
            signal_zh = {"buy": "偏多", "sell": "偏空", "neutral": "中性"}.get(signal, signal)
            lines.append(f"- 择时信号: **{signal_zh}** (置信度 {confidence}%)")
            macd = tech.get("macd", {})
            lines.append(f"- MACD: DIF={macd.get('dif', 0)}, DEA={macd.get('dea', 0)}, 信号={macd.get('signal', '')}")
            rsi = tech.get("rsi", {})
            lines.append(f"- RSI: {rsi.get('rsi', 0)} ({rsi.get('status', '')})")
            kdj = tech.get("kdj", {})
            lines.append(f"- KDJ: K={kdj.get('k', 0)}, D={kdj.get('d', 0)}, J={kdj.get('j', 0)}")
            boll = tech.get("bollinger", {})
            lines.append(f"- 布林带: 上={boll.get('upper', 0)}, 中={boll.get('middle', 0)}, 下={boll.get('lower', 0)}")
            ma = tech.get("ma_system", {})
            if ma:
                trend_zh = {"bullish": "多头排列", "bearish": "空头排列", "neutral": "震荡"}.get(ma.get("trend", ""), ma.get("trend", ""))
                lines.append(f"- 均线: {trend_zh} (MA5={ma.get('ma5', 0)}, MA20={ma.get('ma20', 0)}, MA60={ma.get('ma60', 0)})")
            vp = tech.get("volume_price", {})
            lines.append(f"- 量价: {vp.get('signal', '')} {vp.get('warning', '')}")
            lines.append("")

        # 情绪面
        sent = r.get("sentiment", {})
        if "error" not in sent and sent:
            lines.append("## 🌡️ 市场情绪")
            if "composite_score" in sent:
                lines.append(f"- 综合情绪: {sent['composite_score']}/100 — {sent.get('level', '')}")
                lines.append(f"- 建议: {sent.get('advice', '')}")
                for dim_name, dim_data in sent.get("dimensions", {}).items():
                    if isinstance(dim_data, dict) and "score" in dim_data:
                        lines.append(f"  - {dim_name}: {dim_data['score']}/100 — {dim_data.get('status', '')}")
            lines.append("")

        # 持有体验（长期持有期 + 回撤 + 定投）
        lines.extend(self._format_holdings(r.get("holdings") or {}))
        lines.extend(self._format_dca(r.get("dca") or {}))

        # 综合评分
        comp = r.get("comprehensive", {})
        if "error" not in comp and comp:
            lines.append("## 🎯 综合评分")
            rating_emoji = {"优秀": "🟢", "良好": "🟡", "一般": "🟠", "较差": "🔴"}.get(comp.get('rating', ''), "⚪")
            lines.append(f"- 综合评分: {comp.get('overall_score', 0)}/100 ({rating_emoji} {comp.get('rating', '')})")
            for name, score in comp.get("scores", {}).items():
                name_zh = {"technical": "技术面", "sentiment": "情绪面", "premium": "溢价风险"}.get(name, name)
                lines.append(f"  - {name_zh}: {score}/100")
            rec = comp.get("recommendation", {})
            if rec:
                lines.extend(["", "**操作建议**:"])
                lines.append(f"  - 操作: {rec.get('action', '')}")
                lines.append(f"  - 信心: {rec.get('confidence', '')}")
                lines.append(f"  - 溢价风险: {rec.get('premium_risk', '')}")
                if rec.get("stop_loss"):
                    lines.append(f"  - 止损价: {rec['stop_loss']}")
                if rec.get("fair_value_ref"):
                    lines.append(f"  - IOPV参考: {rec['fair_value_ref']}")
            lines.append("")

        return "\n".join(lines)


def analyze_stock(user_input: str, industry: str = "general") -> str:
    """快速分析"""
    analyzer = FinancialAnalyzer()
    result = analyzer.analyze(user_input, industry)
    return analyzer.format_report(result)
