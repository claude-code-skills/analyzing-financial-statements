---
name: analyzing-financial-statements
description: 财务报表分析技能 - 六维综合分析（基本面/估值/技术面/情绪面/风控/市场温度），支持A股/港股/ETF，含DCF+蒙特卡洛、杜邦分析、Beneish M-Score、Altman Z-Score、Piotroski F-Score
---

# Financial Analyzer v2

六维综合财务分析，覆盖A股/港股/ETF/美股。**默认全量分析，无需选模式。**

## 能力

### 六维分析（默认全部执行）
1. **基本面** — 杜邦分析（三因素+五因素分解，ROE质量评级）
2. **估值** — DCF两阶段+蒙特卡洛10000次+反向DCF+格雷厄姆数值+DDM + **PE/PB历史百分位**（近10年贵/中/便宜，A股百度股市通/美股FMP）
3. **技术面** — pandas-ta全量指标（MACD/RSI/KDJ/布林带/OBV/ATR/ADX/CCI/MFI）+ 多指标共振择时信号
4. **情绪面** — 7维加权合成（恐贪指数/融资杠杆/北向资金/主力资金/涨跌停/估值百分位/散户行为）
5. **风控** — Beneish M-Score（财报操纵检测）+ Altman Z-Score（破产预警）+ Piotroski F-Score（财务健康9分制）+ A股特色8项检查
6. **市场温度** — 综合情绪指标（极度恐惧→极度贪婪）

### 长期价值增强（六维之外，默认执行，长期价值投资者核心）
- **估值历史百分位** — 当前 PE/PB 在近 10 年历史的位置（<30% 便宜、>70% 偏贵）；A股个股走百度股市通，美股 FMP ratios 付费暂缺（降级参考 DCF），港股暂缺
- **持有期回报** — 持有 3/5/10 年的年化收益分布（中位/最坏/最好）+ 不亏概率（前复权价格，避免除权扭曲）
- **回撤体验** — 历史最大回撤 + 恢复时长，判断「拿不拿得住」
- **定投回测** — 月定投持有 3/5/10 年的 XIRR 年化分布 + 不亏概率，以及全周期「定投 vs 满仓」对照；定投用 XIRR（多笔现金流标准），与满仓（单笔几何年化=其XIRR）同口径可比，波动市定投摊低更有效

### 专属功能
- **ETF分析**：溢折价率+IOPV+指数PE百分位+份额变动
- **港股分析**：港股行情+技术指标
- **A股特色**：龙虎榜/北向资金/融资融券/涨跌停/宏观快照

## 使用方式

给股票代码或名字即可，默认跑全部六维：
- `分析 五粮液` / `分析 000858` — A股六维全量分析
- `分析 AAPL` — 美股全量分析
- `分析 159941` — 纳指ETF全量分析
- `分析 510300` — 沪深300 ETF全量分析

特殊：
- `情绪分析` — 7维市场情绪综合指标（不需要股票代码）

## 文件结构

- `run.py` — CLI入口（默认六维全量分析）
- `analyzer.py` — 主分析器
- `dupont.py` — 杜邦分析
- `valuation.py` — DCF+蒙特卡洛+反向DCF+格雷厄姆+DDM
- `technical.py` — 技术分析（pandas-ta）
- `risk_screening.py` — 风控三件套+Beneish+Altman+Piotroski+A股特色
- `sentiment_index.py` — 7维情绪综合指标
- `comprehensive_score.py` — 六维综合评分
- `data/fetchers/akshare.py` — A股数据获取
- `data/fetchers/a_share_special.py` — A股特色数据
- `data/fetchers/etf.py` — ETF数据
- `data/fetchers/hk_share.py` — 港股数据
- `sentiment.py` — 情绪分析
- `news.py` — 新闻分析

## 执行指引（Skill 触发时必须遵循）

当用户触发本 skill 时，**按以下标准流程执行**，禁止手写内联代码替代模块调用。

### 0. 标的识别规则

| 输入 | 判断 | 示例 |
|------|------|------|
| 6位数字，首字母1或5 | ETF | 159941, 510300 |
| 6位数字，首字母0/3/6 | A股 | 000001, 600519 |
| 5位数字 | 港股 | 00700 |
| 纯字母 | 美股 | AAPL, MSFT |

中文名需先查代码（如"五粮液"→"000858"，"茅台"→"600519"）。

### 1. ETF 分析流程

**前置**：ETF需要雪球token（Playwright刷新），token过期时系统python3无法刷新。
先用 `.venv/bin/python3` 刷新token（仅当缓存过期时）：
```bash
.venv/bin/python3 -c "
from playwright.sync_api import sync_playwright
import json, os
from datetime import datetime, timezone, timedelta
CHROMIUM = os.path.expanduser('~/Library/Caches/ms-playwright/chromium-1208/chrome-mac-arm64/Google Chrome for Testing.app/Contents/MacOS/Google Chrome for Testing')
with sync_playwright() as p:
    b = p.chromium.launch(headless=True, executable_path=CHROMIUM)
    pg = b.new_page(); pg.goto('https://xueqiu.com/', timeout=30000, wait_until='domcontentloaded'); pg.wait_for_timeout(5000)
    cookies = b.contexts[0].cookies(); b.close()
token = next((c['value'] for c in cookies if c['name']=='xq_a_token'), None)
if token:
    with open(os.path.expanduser('~/.epm_xueqiu_token.json'), 'w') as f:
        json.dump({'token': token, 'expires_at': (datetime.now(timezone.utc)+timedelta(hours=4)).isoformat()}, f)
    print('Token refreshed')
else:
    print('Failed')
"
```

**主分析**（run.py 默认全量六维，从任意目录调用即可）：
```bash
python3 .claude/skills/analyzing-financial-statements/run.py 159941
```

**补充数据**（ETF情绪面使用EPM获取恐贪指数+美股行情）：
```bash
.venv/bin/python3 .claude/skills/etf-premium-mood/scripts/epm.py SZ159941
```

### 2. A股 分析流程

```bash
python3 .claude/skills/analyzing-financial-statements/run.py 000858
```

### 3. 输出后处理

拿到 `run.py` 的结构化输出后，Claude 负责：
1. 解读技术指标含义（不要照搬数字，要给出择时判断）
2. 结合溢价率/恐贪指数给出操作建议
3. 标注关键价位（支撑/压力/止损）
4. 一句话总结

**A股估值增强规则**（必须遵循）：
- 关注"估值对比"板块中的异常年警告（is_anomalous_year=True 时静态PE可能失真）
- 股息率>4%时必须提及"🛡️ 高股息支撑"
- 情景分析结果中，给出赔率判断（上行空间 vs 下行风险）而非单一"高估/低估"
- 当DCF和TTM PE方向矛盾时（如DCF说高估但TTM PE合理），标注"价值分歧区"
- 操作建议为"左侧关注"时，说明是高股息+异常年导致的估值分歧，非基本面恶化

**长期价值解读规则**（必须遵循 — 长期价值投资者核心，与估值增强并列）：
- **估值历史百分位**：必须解读「估值历史百分位」段——当前 PE/PB 在近 10 年的位置（<30% 便宜、>70% 偏贵），明确回答「现在贵不贵、能不能加仓」；与 DCF 方向矛盾时并列说明，不互相否定
- **持有期回报**：必须解读「持有体验」段——持有 3/5/10 年的最坏年化 + 不亏概率，回答「拿久了大概率赚不赚、最坏亏多少」
- **回撤体验**：结合最大回撤 + 恢复时长，提醒「历史最坏情况 + 多久回来」，判断「拿不拿得住」
- **定投体验**：必须解读「定投体验」段（定投用 XIRR，与满仓同口径可比）——回答「分批进 vs 满仓谁划算、定投最坏亏多少」；全周期「定投 vs 满仓」是单一样本（看叙事），概率看滚动分布
- **美股/港股情绪面**：显「暂不支持」属正常（融资/北向/涨跌停是 A股大盘指标，对美股不适用），不要当缺陷，引导参考估值百分位段
- 一句话总结必须把「估值档位（贵/中/便宜）+ 长期持有胜率」说清——这是长期价值决策的两把尺

### 4. 标准调用顺序

```
用户触发 → 识别标的类型 → [ETF]刷新token → run.py全量六维分析
→ [ETF] epm.py补充恐贪/溢价 → Claude解读+建议 → 输出报告
```

## 依赖

- akshare（已有）
- pandas（已有）
- numpy（已有）
- pandas-ta（`pip install pandas-ta`）
- playwright（ETF溢价需要，在 .venv 中已有）
