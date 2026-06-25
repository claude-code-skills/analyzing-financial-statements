# analyzing-financial-statements Skill 升级方案（基于实测调研 v4.2）

> 调研日期：2026-04-30
> 调研方法：MCP工具实测 + akshare v1.18.59官方文档验证 + 网络调研

## Context

当前Skill的核心问题：技术分析只有MACD/RSI/MA、无估值模型、无风险检测、行业映射硬编码15只股票、数据获取依赖不稳定的中文字段名。

本次升级聚焦5个能力：**DCF+蒙特卡洛**、**杜邦分析**、**技术面择时**、**极端风险排查**、**市场情绪综合指标**。

---

## 一、MCP工具实测结果（600519贵州茅台）

### 实测通过的工具

| 工具 | 状态 | 字段数 | report_date格式 | 关键发现 |
|------|------|--------|----------------|----------|
| `get_financial_metrics` | ✅ | 17 | ISO字符串 `"2026-03-31"` | 含ROE/ROA/毛利率等预计算指标，raw CNY |
| `get_income_statement` | ✅ | 24 | epoch毫秒 `1774915200000` | 含EBIT/利息/税，`asset_impairment_loss` 全null |
| `get_balance_sheet` | ✅ | 33 | epoch毫秒 | 含 `outstanding_shares`，但 **goodwill/fixed_assets_net/property_plant_and_equipment 部分期null** |
| `get_cash_flow` | ✅ | 26 | epoch毫秒 | **`capital_expenditure` 全null**，需用投资活动现金流推算 |
| `get_realtime_data` | ✅ | 11 | - | volume单位是手（×100=股），pct_change是百分比 |
| `get_inner_trade_data` | ✅ | - | - | 茅台返回空数组，该接口覆盖有限 |

### 实测失败的工具

| 工具 | 状态 | 原因 |
|------|------|------|
| `get_hist_data` + `indicators_list` | ❌ | **序列化bug**：`indicators_list`定义为array类型，但MCP客户端传JSON字符串，Pydantic验证报错。只能拿到裸OHLCV |
| `get_hist_data`（不带indicators） | ✅ | 返回timestamp/open/high/low/close/volume，10日数据 |

### report_date格式不统一问题

```
get_financial_metrics → "2026-03-31"（ISO字符串）
get_income_statement  → 1774915200000（epoch毫秒）
get_balance_sheet     → 1774915200000（epoch毫秒）
get_cash_flow         → 1774915200000（epoch毫秒）
```

**应对**：数据层统一做日期转换，epoch毫秒 → ISO字符串。

---

## 二、akshare函数名验证（v1.18.59官方文档）

### 不存在的函数（之前调研推荐的，实际不存在）

| 错误函数名 | 正确替代 |
|-----------|----------|
| `ak.stock_hsgt_north_net_flow_in_em()` | `ak.stock_hsgt_hist_em(symbol="北向资金")`（整体）+ `ak.stock_hsgt_individual_em(symbol=code)`（个股） |
| `ak.macro_china_gdp()` | `ak.macro_china_gdp_yearly()` |
| `ak.fund_etf_portfolio_hold_em()` | `ak.stock_report_fund_hold(symbol="基金持仓", date="20200630")` |

### 已验证存在的函数

| 函数 | 参数 | 输出 |
|------|------|------|
| `ak.stock_lhb_detail_em(start_date, end_date)` | 日期范围 | 20列：代码/名称/净买额/涨跌幅/上榜后1/2/5/10日收益 |
| `ak.stock_lhb_jgmmtj_em(start_date, end_date)` | 日期范围 | 16列：机构买/卖总额/净额/占比 |
| `ak.stock_hsgt_hist_em(symbol="北向资金")` | 无 | 13列：当日净买额/累计净买额/持股市值 |
| `ak.stock_hsgt_individual_em(symbol=code)` | 股票代码 | 9列：持股数/市值/占比/增减持数/资金 |
| `ak.stock_margin_detail_sse(date)` | 日期 | 9列：融资余额/买入额/偿还额/融券 |
| `ak.stock_margin_detail_szse(date)` | 日期 | 8列：融资/融券/总余额 |
| `ak.stock_zt_pool_em(date)` | 日期 | 16列：代码/名称/封板资金/连板数/行业 |
| `ak.macro_china_cpi_yearly()` | 无 | 5列：今值/预测/前值 |
| `ak.macro_china_pmi_yearly()` | 无 | 5列：今值/预测/前值 |
| `ak.macro_china_gdp_yearly()` | 无 | 5列：今值/预测/前值 |
| `ak.macro_china_lpr()` | 无 | 5列：LPR1Y/LPR5Y/短期/长期利率 |
| `ak.fund_etf_spot_em()` | 无 | 37列：含IOPV/折价率/资金流向 |
| `ak.fund_etf_hist_em(symbol, period, start_date, end_date, adjust)` | ETF代码+日期 | 11列：OHLCV+振幅+换手率 |
| `ak.stock_board_industry_name_em()` | 无 | 12列：板块名称/代码/涨跌幅/领涨股 |
| `ak.stock_board_industry_cons_em(symbol)` | 行业名或代码 | 成分股含PE/PB |

---

## 三、DCF模型关键数据约束

| DCF所需数据 | MCP字段 | 可用性 | 替代方案 |
|------------|---------|--------|----------|
| EBIT | `ebit`（income_statement） | ✅ 可用 | - |
| 税率 | `income_tax_expense / ebit` 推算 | ✅ 可用 | - |
| 折旧摊销 | 无直接字段 | ❌ null | `net_cash_flow_from_operations - net_income` 近似 |
| 资本开支 | `capital_expenditure`（cash_flow） | ❌ 全null | `abs(total_cash_outflow_from_investing)` |
| 营运资本变动 | `current_assets` + `current_liabilities` | ✅ 可用 | 两期差值计算 |
| 总股本 | `outstanding_shares`（balance_sheet） | ✅ 可用 | - |
| 净债务 | `total_liabilities - cash_and_equivalents` | ✅ 可用 | - |

### 反向DCF（Reverse DCF）

给定当前市价，反推市场隐含的未来增长率。回答"当前价格已经price in了多少增长？"

```
输入：market_cap, base_fcf, years=5, terminal_growth=3%, wacc=10%, net_debt
输出：隐含增长率（二分法求解）
```

用途：如果隐含增长率远高于历史均值 → 高估；远低于历史均值 → 低估。

### 格雷厄姆数值（Graham Number）

经典安全边际速算公式：

```
Graham Number = sqrt(22.5 × EPS × BVPS)
```

其中 EPS = 每股收益，BVPS = 每股净资产。当前价格低于格雷厄姆数值 → 有安全边际。

**局限**：假设ROE固定15%、PE固定15，对高增长/高杠杆公司不适用，仅作快速筛选参考。

---

## 四、技术指标工具选型

### pandas-ta vs 手写 vs TA-Lib

| 方案 | 优点 | 缺点 |
|------|------|------|
| **pandas-ta** | 纯Python，pip安装即用，KDJ/BOLL/OBV/ATR/MFI全支持 | 性能比TA-Lib慢，维护有间歇 |
| 手写pandas | 零依赖 | 工作量大，容易出错，KDJ/BOLL公式复杂 |
| TA-Lib | 性能最优，行业标准 | 需要先装C库（`brew install ta-lib`），安装麻烦 |

**选择pandas-ta**：唯一新增依赖，pip一行搞定，覆盖所有需要的指标。

### pandas-ta使用注意事项

akshare返回中文列名，pandas-ta需要英文列名：
```python
df.rename(columns={
    "日期": "Date", "开盘": "Open", "收盘": "Close",
    "最高": "High", "最低": "Low", "成交量": "Volume",
}, inplace=True)
df.set_index("Date", inplace=True)
```

---

## 五、风险检测模型

### Beneish M-Score（学术模型）

8变量公式，检测财报操纵：
```
M = -4.84 + 0.92×DSRI + 0.528×GMI + 0.404×AQI + 0.892×SGI
    + 0.115×DEPI - 0.172×SGAI + 4.679×TATA - 0.327×LVGI
```

| 变量 | 公式 | 检测什么 |
|------|------|----------|
| DSRI | (AR_t/Rev_t) / (AR_t-1/Rev_t-1) | 应收账款膨胀（虚增收入） |
| GMI | GM_t-1 / GM_t | 毛利率下滑（操纵动机） |
| AQI | 无形资产占比变化 | 费用资本化 |
| SGI | Rev_t / Rev_t-1 | 增长压力 |
| DEPI | 折旧率变化 | 折旧放缓（虚增利润） |
| SGAI | 管理费用率变化 | 异常效率 |
| TATA | (NetIncome - OCF) / TotalAssets | 盈利质量（应计利润） |
| LVGI | 杠杆率变化 | 杠杆变动 |

**阈值**：M > -1.78 → 疑似财报操纵

**数据来源**：MCP三表数据（连续2期），所有变量均可计算。

### A股特色检查清单

| 检查项 | 公式 | 红灯阈值 | 数据来源 |
|--------|------|----------|----------|
| 应收/营收比 | accounts_receivable / revenue | > 30% | MCP |
| 现金流/净利润 | OCF / net_income | < 0.7 连续2年 | MCP |
| 商誉/净资产 | goodwill / shareholders_equity | > 30% | akshare补（MCP部分null） |
| 资产负债率 | total_liabilities / total_assets | > 70% | MCP |
| 流动比率 | current_assets / current_liabilities | < 1 | MCP |
| 存贷双高 | cash高 + 有息负债高 | 同时高 | MCP |
| 累计FCF | 3年FCF之和 | 为负 | MCP |
| 大股东质押比例 | 质押股数/总股本 | > 80% → 红灯，> 50% → 黄灯 | akshare `ak.stock_greed_hope_em` 或东财接口 |

### Altman Z-Score（破产预警模型）

```
Z = 1.2×X1 + 1.4×X2 + 3.3×X3 + 0.6×X4 + 1.0×X5
```

| 变量 | 公式 | 含义 |
|------|------|------|
| X1 | Working Capital / Total Assets | 流动性 |
| X2 | Retained Earnings / Total Assets | 累积盈利能力 |
| X3 | EBIT / Total Assets | 资产回报效率 |
| X4 | Market Cap / Total Liabilities | 市场对杠杆的容忍度 |
| X5 | Revenue / Total Assets | 资产周转效率 |

**阈值**：Z > 2.99 = 安全区，1.81 < Z < 2.99 = 灰色区，Z < 1.81 = 困境区

**适用**：制造业/工业公司效果好，金融业/房地产慎用（资本结构差异大）。

### Piotroski F-Score（财务健康9分制）

9项二元评分（每项0或1分），覆盖盈利、杠杆、效率三个维度：

| # | 指标 | 得1分条件 |
|---|------|----------|
| 1 | ROA | 当期ROA > 0 |
| 2 | 经营现金流 | 当期OCF > 0 |
| 3 | ROA变化 | 当期ROA > 上期ROA |
| 4 | 盈利质量 | OCF > Net Income（应计利润为负） |
| 5 | 杠杆变化 | 当期长期负债率 < 上期 |
| 6 | 流动性变化 | 当期流动比率 > 上期 |
| 7 | 股票发行 | 当期未增发新股 |
| 8 | 毛利率变化 | 当期毛利率 > 上期 |
| 9 | 资产周转率变化 | 当期周转率 > 上期 |

**解读**：8-9分 = 强买入信号，0-2分 = 强卖出信号，4-5分 = 中性

**优势**：简单、稳健、学术验证充分，适合A股低频价值投资者快速筛选。

### 综合风控输出

三个模型互补：
- **Beneish M-Score**：检测"财报是否造假"（防雷）
- **Altman Z-Score**：检测"公司会不会破产"（防退市）
- **Piotroski F-Score**：检测"财务是否健康"（选优）

汇总为"风控三件套"报告 + 综合雷区评分（0-100）。

---

## 六、市场情绪综合指标模型

### 设计思路

单一情绪指标不可靠（恐贪指数可能滞后，北向资金可能短期扰动），多指标加权合成"市场温度计"更稳健。

### 指标体系（7个维度）

| 维度 | 指标 | 权重 | akshare函数 | 更新频率 |
|------|------|------|------------|----------|
| 恐贪 | 韭圈儿恐贪指数 | 20% | `ak.index_fear_greed_funddb()` | 日频 |
| 杠杆 | 融资余额5日变化率 | 15% | `ak.stock_margin_sse/szse()` | 日频 |
| 外资 | 北向资金5日累计净流入 | 15% | `ak.stock_hsgt_hist_em("北向资金")` | 日频 |
| 资金 | 主力资金净流入占比 | 15% | `ak.stock_market_fund_flow()` | 日频 |
| 热度 | 涨跌停比 + 封板成功率 | 15% | `ak.stock_market_activity_legu()` | 日频 |
| 估值 | 沪深300/创业板PE历史百分位 | 10% | `ak.stock_a_indicator_lg("000300")` | 日频 |
| 散户 | 新基金发行规模（逆向） | 10% | `ak.fund_new_found_em()` | 日频 |

### 各指标标准化方法

- **恐贪指数**：直接0-100，<25=极度恐惧，>75=极度贪婪
- **融资余额**：5日变化率，标准化到0-100（历史分位法）
- **北向资金**：5日累计净流入，标准化到0-100
- **主力资金**：当日主力净流入占成交额比，标准化到0-100
- **涨跌停比**：涨停数/(涨停数+跌停数)，标准化到0-100
- **PE百分位**：当前PE在近10年历史中的百分位，<30%=低估区，>70%=高估区
- **新基金发行**：近4周发行规模，反向标准化（发行冰点=高分=机会）

### 输出

- 综合情绪分（0-100）：0-25=极度恐惧（买入机会），25-50=偏冷，50-75=偏热，75-100=极度贪婪（风险警示）
- 各维度分项得分
- 情绪趋势（近5日走势：升温/降温/持平）
- 历史百分位（当前情绪在近1年中的位置）

### ETF专属增强

- ETF份额变动趋势（当期份额 vs 上期份额，净申购=看多）
- ETF溢折价率（市场价 vs IOPV，溢价=看多，折价=看空）
- 跟踪指数的PE/PB百分位（如创业板ETF→创业板指PE分位）

### 不能用的指标

| 指标 | 原因 |
|------|------|
| 中国VIX (iVIX) | 2018年上交所停发，至今未恢复 |
| 股吧情绪 | 需NLP处理，噪音大，可靠性低 |
| 新增开户数 | 月频公布，滞后1个月，时效性差 |

---

## 七、架构决策

- **数据层**：MCP工具为主（财务报表+行情），akshare直调为辅（A股特色数据+补齐null字段）
- **技术指标**：pandas-ta本地计算（绕过MCP indicators_list bug）
- **估值模型**：纯numpy自研（不引入QuantLib/OpenBB）
- **风险检测**：Beneish M-Score + Altman Z-Score + Piotroski F-Score + A股特色检查
- **情绪指标**：7维加权合成（恐贪+杠杆+外资+资金+热度+估值+散户）
- **新增依赖**：仅 `pandas-ta`

---

## 八、实施计划

### Phase 1: 数据层重建（4个文件）

#### 1.1 `data/fetchers/akshare.py` — 重写

当前：用 `stock_financial_abstract` + 硬编码中文字段名。

改为双通道：
- **主通道**：调MCP工具（`get_financial_metrics`、`get_income_statement`、`get_balance_sheet`、`get_cash_flow`、`get_realtime_data`）
- **补通道**：akshare直调补齐MCP返回null的关键字段

关键改动：
- `get_financial_data(symbol)` → 调MCP，统一report_date为ISO格式
- `get_financial_data_multi_period(symbol, n=5)` → 多期数据供杜邦/DCF
- `get_market_data(symbol)` → 调 `get_realtime_data`
- `get_history(symbol, period=100)` → 调 `get_hist_data`，返回OHLCV
- `get_history_with_indicators(symbol, period=100)` → OHLCV + pandas-ta计算指标
- 删除硬编码 `FIELD_MAPPING`，MCP返回英文字段名
- 行业映射：用 `ak.stock_board_industry_cons_em()` 动态查询

#### 1.2 `data/fetchers/a_share_special.py` — 新建

```python
class AShareSpecialFetcher:
    def get_dragon_tiger(self, symbol, days=30)     # ak.stock_lhb_detail_em
    def get_northbound_flow(self, symbol)            # ak.stock_hsgt_individual_em
    def get_northbound_summary(self)                 # ak.stock_hsgt_hist_em(symbol="北向资金")
    def get_margin_data(self, symbol)                # ak.stock_margin_detail_sse/szse
    def get_price_limit_pool(self, date)             # ak.stock_zt_pool_em
    def get_macro_snapshot(self)                      # CPI/PMI/GDP/LPR
```

#### 1.3 `data/fetchers/etf.py` — 新建

```python
class ETFFetcher:
    def get_etf_realtime(self, symbol)               # ak.fund_etf_spot_em
    def get_etf_hist(self, symbol, period=100)       # ak.fund_etf_hist_em
    def get_etf_basic_info(self, symbol)             # 基本信息
```

#### 1.4 `data/fetchers/hk_share.py` — 新建

港股数据，走akshare（`ak.stock_hk_hist`）或FMP。

### Phase 2: 分析引擎（5个新文件 + 2个重写）

#### 2.1 `dupont.py` — 新建

三因素 + 五因素杜邦分解，5期趋势，ROE质量评级。

#### 2.2 `valuation.py` — 新建

```python
def dcf_2_stage(base_fcf, growth_rate, years, terminal_growth, wacc, net_debt, shares)
    # 两阶段DCF（FCFF，5年预测+永续）

def reverse_dcf(market_cap, base_fcf, years, terminal_growth, wacc, net_debt)
    # 反向DCF：给定当前市价反推隐含增长率

def gordon_growth_model(dividend, required_return, growth_rate)
    # DDM股息折现

def graham_number(eps, growth_rate, aaa_yield)
    # 格雷厄姆数值

def monte_carlo_dcf(base_fcf, growth_mean, growth_std, wacc_mean, wacc_std,
                     years, terminal_growth, net_debt, shares, simulations=10000)
    # 蒙特卡洛模拟，输出P10/P25/P50/P75/P90分布
```

#### 2.3 `risk_screening.py` — 新建

```python
def altman_z(working_capital, retained_earnings, ebit, market_cap,
             total_liabilities, total_assets, revenue)
    # 破产预警：Z>2.99安全，1.81<Z<2.99灰色，Z<1.81困境

def beneish_m(current_vars, prior_vars)
    # 财务操纵检测：M > -1.78 = 可疑

def piotroski_f(current_data, prior_data)
    # 财务健康9分制：盈利(3分)+杠杆(3分)+效率(3分)

def pledge_risk(pledge_ratio)
    # 质押风险评估：>80%红灯，>50%黄灯

def comprehensive_risk_check(financial_data)
    # 综合风险排查：Beneish+Z-Score+Piotroski+8项A股特色检查，输出雷区评分0-100
```

#### 2.4 `sentiment_index.py` — 新建

7维情绪综合指标（恐贪+杠杆+外资+资金+热度+估值+散户），ETF专属增强（份额变动+溢折价+指数PE分位）。

#### 2.5 `technical.py` — 重写

pandas-ta全量指标 + 多指标共振择时信号。

#### 2.6 `comprehensive_score.py` — 重写

6维评分（基本面25%/估值20%/技术面15%/情绪面20%/风控10%/市场温度10%）。情绪面权重从15%提升到20%，新增"市场温度"维度。

### Phase 3: 整合与输出（2个文件）

#### 3.1 `analyzer.py` — 重写

新增4个分析入口：`valuation_analysis`、`timing_analysis`、`risk_check`、`sentiment_analysis`。

#### 3.2 `SKILL.md` — 更新

---

## 九、文件清单

| 操作 | 文件 | 变更内容 |
|------|------|----------|
| 重写 | `data/fetchers/akshare.py` | MCP主通道 + akshare补通道 |
| 新建 | `data/fetchers/a_share_special.py` | 龙虎榜/北向/融资融券/涨跌停/宏观 |
| 新建 | `data/fetchers/etf.py` | ETF数据 |
| 新建 | `data/fetchers/hk_share.py` | 港股数据 |
| 重写 | `technical.py` | pandas-ta + 多指标共振 |
| 新建 | `dupont.py` | 杜邦分析 |
| 新建 | `valuation.py` | DCF + 蒙特卡洛 |
| 新建 | `risk_screening.py` | Beneish M-Score + 风险检查 |
| 新建 | `sentiment_index.py` | 7维情绪综合指标 + ETF专属增强 |
| 重写 | `comprehensive_score.py` | 6维评分（含市场温度） |
| 重写 | `analyzer.py` | 新增4个分析入口（估值/择时/风控/情绪） |
| 更新 | `SKILL.md` | 能力描述 |
| 更新 | `requirements-fmp.txt` | 新增 pandas-ta |

---

## 十、验证方式

1. `python analyzer.py "分析 600519"` — MCP数据获取
2. `python analyzer.py "估值分析 600519"` — DCF + 蒙特卡洛
3. 杜邦分解：茅台应为净利率驱动
4. `python analyzer.py "择时分析 600519"` — 技术指标
5. `python analyzer.py "风险排查 600519"` — Beneish M-Score
6. `python analyzer.py "情绪分析"` — 7维情绪综合指标（不需股票代码，市场级别）
7. `python analyzer.py "分析 159941"` — 纳指ETF（技术面+情绪面+溢折价）
8. `python analyzer.py "分析 159915"` — 创业板ETF（技术面+指数PE分位）
9. null字段补齐验证

---

## 十一、技术栈总结

| 工具 | 用途 | 是否新增 |
|------|------|----------|
| numpy | 蒙特卡洛模拟、数值计算 | 已有 |
| pandas | 财务数据表格处理 | 已有 |
| **pandas-ta** | 技术指标计算（KDJ/BOLL/OBV/ATR/MFI） | **新增** |
| akshare | A股特色数据直调 | 已有 |
| MCP akshare-one-mcp | 标准化财务报表+行情 | 已有 |
| akshare（直调） | A股特色数据+情绪指标+ETF数据 | 已有 |
