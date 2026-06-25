# Skill 升级计划：analyzing-financial-statements

## Context

当前 Skill 存在6个核心缺陷：数据不新鲜（硬编码中文字段）、行业对比无意义（只映射15只股票）、技术分析太弱（只有MACD/RSI/MA）、没有A股特色数据、没有估值模型、没有财务异常检测。用户需要：DCF+蒙特卡洛、杜邦分析、择时技术面、极端风险排查。全部自写纯函数，不引入新依赖。

## 改动概览

### 新建4个文件

1. **`valuation.py`** (~150行) — DCF估值模块
   - `dcf_2_stage(base_fcf, growth_rate, years, terminal_growth, wacc, net_debt, shares)` → 两阶段DCF
   - `reverse_dcf(market_cap, base_fcf, years, terminal_growth, wacc, net_debt)` → 反推隐含增长率
   - `gordon_growth_model(dividend, required_return, growth_rate)` → DDM股息折现
   - `graham_number(eps, growth_rate, aaa_yield)` → 格雷厄姆数值
   - `monte_carlo_dcf(base_fcf, growth_mean, growth_std, wacc_mean, wacc_std, years, terminal_growth, net_debt, shares, simulations=10000)` → numpy蒙特卡洛模拟，输出公允价值分布的P10/P25/P50/P75/P90

2. **`dupont.py`** (~60行) — 杜邦分解
   - `dupont_3(net_income, revenue, total_assets, equity)` → 三因子 (NPM × AT × EM)
   - `dupont_5(net_income, ebt, ebit, revenue, total_assets, equity)` → 五因子 (Tax × Interest × OPM × AT × EM)
   - `interpret_dupont(result)` → 解读哪个因子驱动ROE变化

3. **`risk.py`** (~180行) — 风控模型
   - `altman_z(working_capital, retained_earnings, ebit, market_cap, total_liabilities, total_assets, revenue)` → 破产预警 (安全/灰色/困境)
   - `beneish_m(current/prior period的8个财务变量)` → 财务操纵检测 (> -1.78 = 可疑)
   - `piotroski_f(current/prior period的财务数据)` → 财务健康 (0-9分)
   - `pledge_risk(pledge_ratio)` → 质押风险评估
   - `comprehensive_risk_check(...)` → 综合风险排查报告

4. **`ashare_data.py`** (~200行) — A股特色数据获取
   - `get_industry(symbol)` → 用 `stock_board_industry_name_em` + `stock_board_industry_cons_em` 动态查找行业
   - `get_northbound_flow(symbol)` → 北向资金持股变动
   - `get_margin_data(symbol)` → 融资融券余额
   - `get_pledge_data(symbol)` → 股票质押比例
   - `get_block_trade(symbol)` → 大宗交易折价情况
   - `get_limit_pool(date)` → 涨跌停池（判断市场情绪）

### 修改5个文件

5. **`data/fetchers/akshare.py`** — 数据层升级
   - 扩展 `FIELD_MAPPING`：增加营运资本、留存收益、资本支出、EBT等字段
   - 增加多期数据获取 `get_multi_period_data(symbol, periods=2)` 供Piotroski/Beneish用
   - 增加 `get_capex(symbol)` 从现金流量表取资本支出

6. **`technical.py`** — 技术分析增强（~120行新增）
   - 新增 `calculate_kdj(n=9, m1=3, m2=3)` → KDJ随机指标
   - 新增 `calculate_bollinger(period=20, std_dev=2)` → 布林带 + 收窄/扩张判断
   - 新增 `volume_price_analysis()` → 量价背离检测（价涨量缩/价跌量增等异常）
   - 新增 `calculate_atr(period=14)` → 真实波幅
   - 修改 `analyze()` 汇总所有指标

7. **`analyzer.py`** — 主分析器集成
   - 删除硬编码的 `CN_INDUSTRY_MAPPING` 和 `us_industry_map`
   - `_auto_detect_industry()` 改用 `ashare_data.get_industry(symbol)` 动态检测
   - `_get_extended_analysis()` 增加：
     - 估值分析（DCF + 蒙特卡洛 + 戈登模型 + 格雷厄姆）
     - 杜邦分析
     - 风险排查（Altman Z + Beneish M + Piotroski F + 质押风险）
     - A股特色数据（北向/融资融券/大宗交易）
   - `format_report()` 增加新模块的报告格式化

8. **`calculate_ratios.py`** — 补充指标
   - 增加 `calculate_fcf()` → FCF = 经营现金流 - 资本支出
   - 增加 `fcf_yield()` → FCF收益率
   - 增加 `owner_earnings()` → 所有者盈余

9. **`SKILL.md`** — 更新文档反映新能力

### 不动的文件

- `comprehensive_score.py` — 权重体系不变，但会被 analyzer 调用时传入更丰富的数据
- `sentiment.py` — 不变
- `news.py` — 不变
- `data/cache.py` / `data/config.py` — 不变
- `data/fetchers/fmp.py` — 美股部分不变
- `interpret_ratios.py` — 行业基准暂时保留，动态行业检测在 analyzer 层解决

## 数据流

```
akshare.py (扩展字段+多期数据)
    ├── 基础财务数据 → calculate_ratios.py (补充FCF等)
    ├── 市场数据     → valuation.py (DCF/DDM/格雷厄姆/蒙特卡洛)
    ├── 多期数据     → risk.py (Altman/Beneish/Piotroski)
    │                → dupont.py (杜邦分解)
    ├── 历史行情     → technical.py (KDJ/布林带/量价/ATR)
    └── 行业/特色数据 → ashare_data.py (北向/融资融券/质押/大宗交易)

analyzer.py 汇总所有模块 → comprehensive_score.py 综合评分 → format_report()
```

## 依赖

不引入新依赖。仅使用：akshare, pandas, numpy（均已安装）。

## 验证方式

1. 运行 `python3 analyzer.py` 内置测试用例，验证基础分析流程
2. 用真实A股代码（如 600519 贵州茅台）测试 `深度分析 600519`，检查：
   - DCF估值是否合理（对比当前市价）
   - 杜邦分解各因子是否正确
   - 技术指标（KDJ/布林带）是否输出
   - 风险评分（Altman Z/Beneish M/Piotroski F）是否在预期范围
   - A股特色数据（北向/融资融券/质押）是否正常获取
3. 用美股代码测试不回归
