# analyzing-financial-statements

六维综合财务分析，覆盖A股/港股/ETF/美股。**默认全量分析，无需选模式。**

Six-dimensional comprehensive financial analysis for A-shares, Hong Kong stocks, ETFs, and US stocks. **Full analysis by default, no mode selection needed.**

[![License: MIT](https://img.shields.io/badge/License-MIT-yellow.svg)](https://opensource.org/licenses/MIT)
[![Python 3.8+](https://img.shields.io/badge/python-3.8+-blue.svg)](https://www.python.org/downloads/)

---

## ✨ 功能特性 | Features

### 六维分析 | Six-Dimensional Analysis

1. **基本面 | Fundamental** — 杜邦分析（三因素+五因素分解，ROE质量评级）
   - DuPont analysis (3-factor + 5-factor breakdown, ROE quality rating)

2. **估值 | Valuation** — DCF两阶段+蒙特卡洛10000次+反向DCF+格雷厄姆数值+DDM + PE/PB历史百分位
   - Two-stage DCF + Monte Carlo (10,000 simulations) + Reverse DCF + Graham Number + DDM + PE/PB historical percentiles

3. **技术面 | Technical** — pandas-ta全量指标（MACD/RSI/KDJ/布林带/OBV/ATR/ADX/CCI/MFI）+ 多指标共振择时信号
   - Full pandas-ta indicators (MACD/RSI/KDJ/Bollinger/OBV/ATR/ADX/CCI/MFI) + multi-indicator timing signals

4. **情绪面 | Sentiment** — 7维加权合成（恐贪指数/融资杠杆/北向资金/主力资金/涨跌停/估值百分位/散户行为）
   - 7-dimensional weighted synthesis (Fear & Greed/Margin/Northbound/Main Fund/Limit Up/Valuation/Retail)

5. **风控 | Risk Control** — Beneish M-Score（财报操纵检测）+ Altman Z-Score（破产预警）+ Piotroski F-Score（财务健康9分制）+ A股特色8项检查
   - Beneish M-Score (earnings manipulation) + Altman Z-Score (bankruptcy prediction) + Piotroski F-Score (financial health 9-point) + A-share specific 8-item check

6. **市场温度 | Market Temperature** — 综合情绪指标（极度恐惧→极度贪婪）
   - Composite sentiment indicator (Extreme Fear → Extreme Greed)

### 长期价值增强 | Long-Term Value Enhancement

- **估值历史百分位 | Valuation Percentile** — 当前 PE/PB 在近10年历史的位置（<30% 便宜、>70% 偏贵）；A股个股走百度股市通，美股 FMP ratios 免费，港股暂缺
- **持有期回报 | Holding Period Returns** — 持有3/5/10年的年化收益分布（中位/最坏/最好）+ 不亏概率（前复权价格，避免除权扭曲）
- **回撤体验 | Drawdown Analysis** — 历史最大回撤 + 恢复时长，判断「拿不拿得住」
- **定投回测 | DCA Backtesting** — 月定投持有3/5/10年的 XIRR 年化分布 + 不亏概率，以及全周期「定投 vs 满仓」对照；定投用 XIRR（多笔现金流标准），与满仓（单笔几何年化=其XIRR）同口径可比

---

## 📦 安装 | Installation

```bash
pip install -r requirements.txt
```

### 可选 | Optional

For US stock analysis, get a free FMP API key (250 requests/day):
[https://site.financialmodelingprep.com/developer/docs](https://site.financialmodelingprep.com/developer/docs)

```bash
export FMP_API_KEY=your_key_here
```

## 🚀 使用 | Usage

### 基本用法 | Basic Usage

```bash
# A股六维全量分析 | A-share full analysis
python3 run.py 600519          # 茅台 | Kweichow Moutai

# 美股全量分析 | US stock full analysis
python3 run.py AAPL            # Apple Inc.

# ETF全量分析 | ETF full analysis
python3 run.py 159941          # 纳指ETF广发 | NASDAQ ETF

# 港股分析 | Hong Kong stock analysis
python3 run.py 00700           # 腾讯 | Tencent
```

### 专项模式 | Specific Modes

```bash
# 仅估值 | Valuation only
python3 run.py --valuation 600519

# 仅择时 | Timing only
python3 run.py --timing 600519

# 仅风控 | Risk check only
python3 run.py --risk 600519

# JSON输出 | JSON output
python3 run.py --json 600519
```

---

---

## 标的识别规则

| 输入 | 判断 | 示例 |
| :--- | :--- | :--- |
| 6位数字，首字母1或5 | ETF | 159941, 510300 |
| 6位数字，首字母0/3/6 | A股 | 000001, 600519 |
| 5位数字 | 港股 | 00700 |
| 纯字母 | 美股 | AAPL, MSFT |

---

## 🌐 数据源 | Data Sources

### A股（A股）

- **财报**: AKShare (新浪源) - 免费
- **行情**: 163/东财 - 免费
- **估值**: 百度股市通 - 免费
- **情绪**: 短圈儿/东财 - 免费

### 美股

- **财报**: FMP (免费 250次/天)
- **行情**: AKShare (东财美股编码) - 免费
- **估值**: FMP ratios (免费)

### ETF

- **主通道**: 雪球 (Playwright自动刷新token)
- **次通道**: 东财 - 免费
- **兜底**: 新浪 - 免费

### 港股

- **行情**: 腾讯财经 - 免费

详见 [API_DEPENDENCIES.md](API_DEPENDENCIES.md)

## 📊 示例输出 | Example Output

详见 [EXAMPLES.md](EXAMPLES.md) 查看完整示例：
- A股示例（600519 茅台）
- 美股示例（AAPL）
- ETF 示例（159941 纳指ETF）
- 港股示例（00700 腾讯）

---

## 🛠️ 技术架构 | Architecture

```text
run.py (CLI入口)
  ↓
analyzer.py (主分析器)
  ↓
  ├─ 数据获取层 (data/fetchers/)
  │   ├─ akshare.py (A股)
  │   ├─ fmp.py (美股)
  │   ├─ etf.py (ETF)
  │   └─ hk_share.py (港股)
  │
  ├─ 分析模块层
  │   ├─ dupont.py (杜邦分析)
  │   ├─ valuation.py (估值)
  │   ├─ technical.py (技术面)
  │   ├─ risk_screening.py (风控)
  │   ├─ sentiment_index.py (情绪面)
  │   ├─ holdings.py (持有期回报)
  │   └─ dca.py (定投回测)
  │
  └─ 综合评分层
      └─ comprehensive_score.py (六维加权合成)
```

## 🔬 核心算法 | Core Algorithms

### XIRR (定投年化)
- 使用二分法求解多笔现金流的内部收益率
- 与满仓几何年化同口径可比
- 已修正系统性低估问题（旧版错误约50%）

### DCF (现金流折现)
- 两阶段增长模型 + 蒙特卡洛10000次模拟
- 反向DCF推导隐含增长率
- 安全边际计算

### 杜邦分析
- 三因素分解：ROE = 净利率 × 资产周转率 × 权益乘数
- 五因素分解：加入税负系数 + 利息负担
- ROE质量评级（0-8分）

---

## 📋 文件结构 | File Structure

```text
analyzing-financial-statements/
├── run.py                          # CLI入口
├── analyzer.py                     # 主分析器
├── SKILL.md                        # Skill文档
├── README.md                       # 本文档
├── requirements.txt                # Python依赖
├── API_DEPENDENCIES.md            # 外部API清单
├── EXAMPLES.md                     # 示例输出
├── dupont.py                       # 杜邦分析
├── valuation.py                     # 估值模块
├── technical.py                     # 技术分析
├── risk_screening.py              # 风控模块
├── sentiment_index.py             # 情绪分析
├── holdings.py                     # 持有期回报
├── dca.py                          # 定投回测
├── comprehensive_score.py          # 综合评分
├── calculate_ratios.py            # 财务比率计算
└── data/
    ├── fetchers/
    │   ├── akshare.py             # A股数据
    │   ├── fmp.py                 # 美股数据
    │   ├── etf.py                 # ETF数据
    │   └── hk_share.py            # 港股数据
    └── ...
```

## 🧪 测试 | Tests

```bash
cd tests
pytest test_*.py
```

## 📝 更新日志 | Changelog

### v2.0 (2026-06-23)
- ✅ 修复ROE/ROA：使用归母净利润+平均归母权益
- ✅ 修复速动比率：减预付账款
- ✅ 修复PEG：3年净利润CAGR自算
- ✅ 修复sentiment美股降级：返回None并自动排除维度
- ✅ 修复XIRR：定投年化修正（系统性低估50%）
- ✅ 新增美股长期收盘价：akshare免费源
- ✅ 新增美股估值百分位：FMP ratios免费
- ✅ 新增定投vs满仓对照：XIRR同口径可比

### v1.0
- 初始版本

## 📄 许可证 | License

MIT License

## 🤝 贡献 | Contributing

欢迎提交 Issue 和 Pull Request！

## 📮 联系 | Contact

- GitHub Issues: [claude-code-skills/analyzing-financial-statements](https://github.com/claude-code-skills/analyzing-financial-statements/issues)

---

**免责声明 | Disclaimer**: 本工具仅供学习参考，不构成投资建议。
**For educational purposes only, not investment advice.**

## 常见问题

**Q: 为什么缓存已禁用？**

A: 为保证每次分析使用最新数据，缓存默认禁用。如需启用，修改 `data/config.py` 中 `CacheConfig.enabled = True`。

**Q: 美股分析报错 "FMP_API_KEY not configured"？**

A: 需要在 `.env` 文件中配置 FMP API Key。免费套餐 250次/天。

**Q: ETF 分析需要什么前置条件？**

A: ETF 溢价数据需要雪球 token。首次分析时会自动通过 Playwright 刷新 token。

**Q: 深度分析和基础分析有什么区别？**

A: 现在没有区别。默认就是全量六维分析，不需要说"深度分析"关键词。直接给股票代码即可。
