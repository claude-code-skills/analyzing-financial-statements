A股估值系统 V2.0 升级方案（终极版）

 问题总览（三方交叉校验）

 ┌─────┬──────────────────────┬────────────────────────────────┬────────┐
 │  #  │         缺陷         │              后果              │  来源  │
 ├─────┼──────────────────────┼────────────────────────────────┼────────┤
 │ 1   │ 只用年报EPS          │ EPS偏差35%                     │ AI-1   │
 ├─────┼──────────────────────┼────────────────────────────────┼────────┤
 │ 2   │ 不抓取股息率         │ 5.64%铁底信号遗漏              │ AI-2   │
 ├─────┼──────────────────────┼────────────────────────────────┼────────┤
 │ 3   │ 只展示静态PE         │ 38x vs 动态11x，结论反转       │ AI-1+2 │
 ├─────┼──────────────────────┼────────────────────────────────┼────────┤
 │ 4   │ 单年增长率           │ FY2025的-72%代入DCF荒谬        │ AI-1   │
 ├─────┼──────────────────────┼────────────────────────────────┼────────┤
 │ 5   │ 操作建议只看安全边际 │ 风控满分+超卖→仍建议观望       │ AI-2   │
 ├─────┼──────────────────────┼────────────────────────────────┼────────┤
 │ 6   │ Q1直接年化           │ 白酒等季节性行业严重失真       │ AI-3   │
 ├─────┼──────────────────────┼────────────────────────────────┼────────┤
 │ 7   │ 不识别一次性分红     │ 特别分红伪装成高股息           │ AI-3   │
 ├─────┼──────────────────────┼────────────────────────────────┼────────┤
 │ 8   │ FCF<0时DCF直接废掉   │ 错杀高资本开支成长股           │ AI-3   │
 ├─────┼──────────────────────┼────────────────────────────────┼────────┤
 │ 9   │ 单点DCF预测          │ 一个数字代表不了十字路口的公司 │ AI-3   │
 └─────┴──────────────────────┴────────────────────────────────┴────────┘

 ---
 改动清单（5个文件）

 ---
 改动1: data/fetchers/akshare.py — 数据清洗层

 1a. TTM计算 + 季节性过滤

 新增 get_ttm_data(symbol):

 TTM拼接逻辑:

- 调用 stock_financial_report_sina(stock=symbol, symbol="利润表") 取所有报告期
- 不过滤季报，按日期倒序
- 拼接最近4个季度（Q1+Q2+Q3+Q4组合，非简单年化）
  - 最新年报 → TTM = 年报本身
  - 最新Q1 → TTM = Q1_new + (FY_prev - Q1_prev)
  - 最新Q3 → TTM = Q1+Q2+Q3_new + (FY_prev - Q1_prev - Q2_prev - Q3_prev)

 季节性保护（防止Q1年化失真）:
 SEASONAL_INDUSTRIES = ["白酒", "农业", "零售", "旅游", "啤酒", "乳制品"]

 if industry in SEASONAL_INDUSTRIES:
     # 强季节性：严格TTM，不允许Q1年化
     dynamic_eps = ttm_eps
 else:
     # 弱季节性：允许Q1年化与TTM平滑
     dynamic_eps = ttm_eps *0.7 + (q1_eps* 4) * 0.3

 异常年检测:

- 最新年报净利 vs 上年年报变动 > ±40% → is_anomalous = True
- 返回: {ttm_net_income, ttm_revenue, ttm_eps, report_period, is_anomalous, annual_eps, annual_net_income}

 1b. 股息率获取 + 防诈骗

 在 _fetch_market_data() 中新增 get_dividend_data(symbol):

 def get_dividend_data(self, symbol: str) -> dict:
     df = ak.stock_fhps_detail_em(symbol=symbol)
     # 取最近3年分红记录
     # 解析 "10派X元" → DPS = X/10
     # 同一年有多次分红的累加

     # TTM股息 = 最近4个季度的累计分红
     ttm_dps = sum(最近4季度的每股分红)

     # 3年平均股息
     avg_3y_dps = mean(最近3年的年度累计分红)

     # 防诈骗：取孰低值
     core_dps = min(ttm_dps, avg_3y_dps)

     # 一次性分红检测
     if ttm_dps > avg_3y_dps * 1.5:
         warning = "包含一次性分红，股息率可能不可持续"
     else:
         warning = None

     return {
         "ttm_dps": ttm_dps,
         "avg_3y_dps": avg_3y_dps,
         "core_dps": core_dps,
         "dividend_yield": core_dps / current_price * 100,
         "dividend_warning": warning,
     }

 已验证数据源: ak.stock_fhps_detail_em(symbol='000858') 返回每期分红数据，字段 现金分红-现金分红比例 为"10派X元"格式。

 ---
 改动2: analyzer.py — 数据流整合

 2a. deep_analysis() 注入TTM + 股息率（约line 166后）

# TTM数据

 try:
     ttm_data = fetcher.get_ttm_data(symbol)
     market_data.update({
         "ttm_eps": ttm_data.get("ttm_eps", 0),
         "ttm_net_income": ttm_data.get("ttm_net_income", 0),
         "is_anomalous_year": ttm_data.get("is_anomalous", False),
         "annual_eps": ttm_data.get("annual_eps", 0),
     })
     if market_data["share_price"] > 0 and market_data["ttm_eps"] > 0:
         market_data["pe_ttm"] = round(market_data["share_price"] / market_data["ttm_eps"], 2)
         market_data["pe_static"] = round(market_data["share_price"] / market_data["annual_eps"], 2) if market_data["annual_eps"] > 0 else 0
 except Exception:
     pass

# 股息率

 try:
     div_data = fetcher.get_dividend_data(symbol)
     market_data.update(div_data)
 except Exception:
     pass

 2b. format_report() 新增"估值对比"板块

 在"基础财务指标"后新增：

## 💡 估值对比

- 静态PE: 39.6x（基于年报EPS=2.31）
- TTM PE: 28.2x（滚动12月EPS=3.25）
- 股息率: 5.6%（3年均值: 5.2%）🛡️ 高股息支撑
 ⚠️ 盈利异常波动期：静态PE可能失真，建议参考TTM数据

 条件显示规则:

- is_anomalous_year=True → 显示盈利异常警告
- dividend_yield > 4% → 标注"🛡️ 高股息支撑"
- dividend_warning 存在 → 显示一次性分红警告
- pe_ttm 和 pe_static 差异 > 30% → 标注"估值口径分歧"

 ---
 改动3: valuation.py — 估值引擎升级（核心改动）

 3a. EPS优先用TTM（line 357）

 eps = market_data.get("ttm_eps", 0)
 if eps <= 0:
     eps = inc.get("net_income_attributable", 0) / shares if shares > 0 else 0

 3b. DCF柔性降级（line 309）

 当FCF < 0时，不再直接用0：

 if fcff <= 0:
     # 尝试用正常年数据
     normal_fcf = self._find_normal_year_fcf(multi_period)
     if normal_fcf > 0:
         fcff = normal_fcf
         valuation_method = "DCF (正常年基线)"
     else:
         # 完全降级：关闭DCF，标记使用相对估值
         dcf_valid = False
         valuation_method = "Relative_Valuation (PS/PB)"

 3c. 增长率：排除异常年的多年CAGR（line 335-341）

 if multi_period and len(multi_period) >= 3:
     normal_rev = []
     for i, p in enumerate(multi_period):
         ni = p.get("income_statement", {}).get("net_income", 0)
         rev = p.get("income_statement", {}).get("revenue", 0)
         if i < len(multi_period) - 1:
             prev_ni = multi_period[i+1].get("income_statement", {}).get("net_income", 0)
             if prev_ni > 0 and abs(ni/prev_ni - 1) < 0.5:  # 非异常年
                 normal_rev.append(rev)
     if len(normal_rev) >= 2:
         n = len(normal_rev) - 1
         growth_rate = (normal_rev[0] / normal_rev[-1]) ** (1/n) - 1
         growth_rate = max(min(growth_rate, 0.25), -0.05)

 3d. 蒙特卡洛：用历史波动率替代固定σ（line 366）

# 从正常年序列计算实际σ

 if len(normal_growth_list) >= 2:
     growth_std = max(np.std(normal_growth_list), 0.03)
 else:
     growth_std = 0.05

 3e. ⭐ 情景分析（新增核心能力）

 替代单点DCF，输出三维情景：

 def scenario_analysis(self, base_fcf, shares, net_debt, scenarios_config=None):
     """三情景DCF模拟"""
     if scenarios_config is None:
         # 默认情景：根据历史波动自动生成
         scenarios = {
             "bull": {"growth": growth_rate *1.5, "prob": 0.20},    # 乐观
             "base": {"growth": growth_rate,       "prob": 0.50},    # 中性
             "bear": {"growth": growth_rate* 0.5, "prob": 0.30},    # 悲观
         }

     results = {}
     for name, cfg in scenarios.items():
         dcf = self.dcf_2_stage(
             base_fcf=base_fcf, growth_rate=cfg["growth"],
             years=5, terminal_growth=0.03, wacc=0.10,
             net_debt=net_debt, shares=shares
         )
         results[name] = {
             "value": dcf["per_share_value"],
             "probability": cfg["prob"],
         }

     # 加权期望值
     expected_value = sum(r["value"] * r["probability"] for r in results.values())

     return {
         "scenarios": results,
         "expected_value": expected_value,
         "upside": results["bull"]["value"],   # 乐观目标
         "downside": results["bear"]["value"], # 悲观底线
     }

 3f. 估值信号标记

 在 comprehensive_valuation() 返回中新增:

 "valuation_signals": {
     "anomalous_year": market_data.get("is_anomalous_year", False),
     "dividend_support": "strong" if dividend_yield >= 4 else "moderate" if dividend_yield >= 2 else "none",
     "dcf_method": valuation_method,  # "DCF" | "DCF (正常年基线)" | "Relative_Valuation"
     "pe_spread": pe_static - pe_ttm,
     "dividend_warning": dividend_warning,
 }

 ---
 改动4: comprehensive_score.py — 决策中枢升级

 4a. _score_valuation() 增加股息率加分

 def _score_valuation(self, valuation: dict) -> float:
     margin = valuation.get("safety_margin", {}).get("safety_margin", 0)
     dividend_yield = valuation.get("dividend_yield", 0)

     # 基础分
     if margin > 30: base = 90
     elif margin > 15: base = 75
     elif margin > 0: base = 60
     elif margin > -15: base = 40
     else: base = 20

     # 股息率加分
     if dividend_yield >= 5: base = min(100, base + 15)
     elif dividend_yield >= 3: base = min(100, base + 8)

     return base

 4b. _generate_recommendation() 赔率决策树

 def _generate_recommendation(self, overall, data, scores):
     margin = data.get("valuation", {}).get("safety_margin", {}).get("safety_margin", 0)
     dividend_yield = data.get("valuation", {}).get("dividend_yield", 0)
     is_anomalous = data.get("valuation", {}).get("anomalous_year", False)
     scenario = data.get("valuation", {}).get("scenario_analysis", {})

     # 新增：价值分歧区
     if margin < 0 and dividend_yield >= 4 and is_anomalous:
         # DCF说高估 + 高股息 + 异常年 → 可能错杀
         action, confidence = "左侧关注", "中"
     elif margin < 0 and dividend_yield >= 5:
         action, confidence = "逢低关注", "中"
     else:
         # 原有决策树（不变）
         ...

     # 情景分析赔率信息
     if scenario:
         expected = scenario.get("expected_value", 0)
         upside = scenario.get("upside", 0)
         downside = scenario.get("downside", 0)
         current = safety.get("current_price", 0)
         if current > 0:
             upside_pct = (upside - current) / current * 100
             downside_pct = (downside - current) / current * 100

     return {
         "action": action,
         "confidence": confidence,
         "scenario_odds": {
             "expected_value": expected,
             "upside_target": upside,
             "downside_floor": downside,
             "upside_pct": upside_pct,
             "downside_pct": downside_pct,
         },
         ...
     }

 ---
 改动5: analyzer.py 报告输出 — 赔率格式

 在综合评分板块中，情景分析结果展示为：

## 📊 情景分析（概率加权）

- 乐观路径 (20%): 120元 (+30%)
- 中性路径 (50%): 95元 (+3%)
- 悲观路径 (30%): 70元 (-24%)
- 综合期望值: 93元

 💡 赔率判断: 当前92元接近期望值，上行空间30% vs 下行风险24%，赔率略偏正面
 🛡️ 高股息(5.6%)封杀下行空间，悲观路径(70元)难以触及

 ---
 改动6: SKILL.md — 更新执行指引

 在"3. 输出后处理"中增加:

- Claude必须关注"估值对比"板块中的异常年警告
- 股息率>4%时必须提及"高股息支撑"
- 情景分析结果中，给出赔率判断而非单一"高估/低估"
- 当DCF和动态PE方向矛盾时，标注"价值分歧区"

 ---
 不改动的文件

 ┌───────────────────────────┬──────────────────────┐
 │           文件            │         理由         │
 ├───────────────────────────┼──────────────────────┤
 │ technical.py              │ 用历史日线，逻辑正确 │
 ├───────────────────────────┼──────────────────────┤
 │ risk_screening.py         │ 多期年报对比足够     │
 ├───────────────────────────┼──────────────────────┤
 │ sentiment_index.py        │ 不依赖个股财报       │
 ├───────────────────────────┼──────────────────────┤
 │ dupont.py                 │ 已用多期数据         │
 ├───────────────────────────┼──────────────────────┤
 │ data/fetchers/etf.py      │ ETF路径独立          │
 ├───────────────────────────┼──────────────────────┤
 │ data/fetchers/hk_share.py │ 港股路径独立         │
 └───────────────────────────┴──────────────────────┘

 ---
 验证

# 1. TTM计算

 python3 -c "
 import sys; sys.path.insert(0, '.claude/skills/analyzing-financial-statements')
 from data.fetchers.akshare import AKShareFetcher
 f = AKShareFetcher()
 ttm = f.get_ttm_data('000858')
 print(ttm)
 "

# 预期: ttm_eps ≈ 3.25, is_anomalous = True

# 2. 股息率

 python3 -c "
 import sys; sys.path.insert(0, '.claude/skills/analyzing-financial-statements')
 from data.fetchers.akshare import AKShareFetcher
 f = AKShareFetcher()
 div = f.get_dividend_data('000858')
 print(div)
 "

# 预期: dividend_yield ≈ 5.6%, core_dps取孰低值, 无一次性分红警告

# 3. 全量分析

 python3 .claude/skills/analyzing-financial-statements/run.py 000858

# 预期

# - 估值对比: 静态PE≈40 / TTM PE≈28 / 股息率≈5.6%

# - 格雷厄姆≈49

# - 情景分析: 三路径+期望值

# - 操作建议: "左侧关注"而非"规避"

# - 异常年警告标注

# 4. 回归测试 — 正常年

 python3 .claude/skills/analyzing-financial-statements/run.py 600519

# 预期: 不触发异常年，TTM≈年报，情景分析差异小
