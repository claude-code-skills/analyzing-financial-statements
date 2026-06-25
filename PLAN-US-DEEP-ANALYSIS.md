# 美股深度分析支持计划

> 为美股添加四维综合评分支持（市场情绪、技术面、消息面）

---

## 背景状态

| 市场 | 基础分析 | 深度分析 |
|------|----------|----------|
| A股 (AKShare) | ✅ | ✅ 完整支持 |
| 美股 (FMP) | ✅ | ❌ 仅支持基本面 |

当前 A股 深度分析已完成：
- 📊 市场情绪：主力资金流向分析
- 📈 技术面：MACD/RSI/均线系统
- 📰 消息面：新闻情绪分析
- 🎯 综合评分：四维加权评分

---

## FMP API 验证 ✅

| API | 端点 | 字段 | 状态 |
|-----|------|------|------|
| **Social Sentiment** | `/api/v4/historical/social-sentiment` | date, sentiment, mentions, positiveRatio, negativeRatio | ✅ 可用 |
| **Stock News** | `/stable/news/stock-latest` | title, publishedDate, url, text | ✅ 可用 |
| **Historical Price** | `/api/v3/historical-price-full/{symbol}` | date, open, close, high, low, volume | ✅ 可用 |

### API 详细信息

#### 1. Social Sentiment (市场情绪)
```http
GET https://financialmodelingprep.com/api/v4/historical/social-sentiment?symbol=AAPL&page=0&apikey=YOUR_KEY
```

响应示例：
```json
[
  {
    "date": "2025-01-14",
    "symbol": "AAPL",
    "sentiment": 0.15,           // -1到1，正数表示正面
    "mentions": 15000,
    "positiveRatio": 0.65,
    "negativeRatio": 0.35,
    "socialScore": 85            // 0-100分数
  }
]
```

#### 2. Stock News (最新资讯)
```http
GET https://financialmodelingprep.com/stable/news/stock-latest?tickers=AAPL&apikey=YOUR_KEY
```

响应示例：
```json
[
  {
    "title": "Apple Announces New Products",
    "publishedDate": "2025-01-14T10:30:00Z",
    "url": "https://...",
    "text": "Apple unveiled...",
    "site": "Bloomberg"
  }
]
```

#### 3. Historical Price (历史行情)
```http
GET https://financialmodelingprep.com/api/v3/historical-price-full/AAPL?timeseries=100&apikey=YOUR_KEY
```

响应示例：
```json
{
  "historical": [
    {
      "date": "2025-01-14",
      "open": 185.50,
      "close": 188.20,
      "high": 189.00,
      "low": 185.00,
      "volume": 50000000
    }
  ]
}
```

---

## 架构设计

### 新增/修改文件

```
analyzing-financial-statements/
├── data/fetchers/
│   └── fmp.py                  # ✏️ 扩展: 新增 3 个方法
├── analyzer.py                  # ✏️ 修改: _get_extended_analysis() 支持美股
├── sentiment.py                 # ✏️ 扩展: 美股社交媒体情绪分析
├── technical.py                 # ✅ 复用: 现有技术分析模块
├── news.py                      # ✏️ 扩展: 美股新闻情绪分析
└── comprehensive_score.py       # ✅ 复用: 现有综合评分系统
```

---

## 实现细节

### Phase 1: FMPFetcher 扩展

**文件**: `data/fetchers/fmp.py`

新增三个方法：

```python
def get_social_sentiment(self, symbol: str, limit: int = 5) -> dict:
    """
    获取社交媒体情绪 (FMP v4 API)

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
            # FMP v4 API: historical/social-sentiment
            data = self._make_request(
                "historical/social-sentiment",
                {"symbol": symbol, "page": "0"}
            )

            if not data or not isinstance(data, list):
                return {"error": "无法获取社交媒体情绪"}

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

        except Exception as e:
            return {"error": f"社交媒体情绪获取失败: {str(e)}"}

    # 缓存时间较短（情绪数据时效性高）
    return self._cached_request(f"{symbol}_social_sentiment", fetch)


def get_news(self, symbol: str, limit: int = 5) -> dict:
    """
    获取最新新闻 (FMP Stable API)

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
            # FMP Stable API: news/stock-latest
            data = self._make_request(
                "news/stock-latest",
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

        except Exception as e:
            return {"error": f"新闻获取失败: {str(e)}"}

    # 新闻缓存时间较短
    return self._cached_request(f"{symbol}_news", fetch)


def get_history(self, symbol: str, period: int = 100) -> dict:
    """
    获取历史行情数据 (FMP v3 API)

    Args:
        symbol: 股票代码
        period: 获取天数

    Returns:
        DataFrame or None
    """
    self._rate_limit()

    try:
        # FMP v3 API: historical-price-full
        data = self._make_request(
            f"historical-price-full/{symbol}",
            {"timeseries": str(period)}
        )

        if not data or "historical" not in data:
            return None

        import pandas as pd

        # 转换为 DataFrame
        df = pd.DataFrame(data["historical"])

        # 标准化列名（与 AKShare 保持一致）
        df = df.rename(columns={
            "date": "日期",
            "open": "开盘",
            "close": "收盘",
            "high": "最高",
            "low": "最低",
            "volume": "成交量"
        })

        # 按日期降序排列
        df = df.sort_values("日期", ascending=False).reset_index(drop=True)

        return df

    except Exception:
        return None
```

---

### Phase 2: SentimentAnalyzer 扩展

**文件**: `sentiment.py`

在 `SentimentAnalyzer` 类中新增美股支持：

```python
def analyze_social_sentiment(self, symbol: str, market: str = "cn") -> dict[str, Any]:
    """
    分析市场情绪 (支持 A股和美股)

    Args:
        symbol: 股票代码
        market: cn=A股, us=美股

    Returns:
        A股: 返回资金流向分析 (原有逻辑)
        美股: 返回社交媒体情绪分析
    """
    if market == "cn":
        return self.analyze_fund_flow(symbol)  # 原有方法

    # 美股社交媒体情绪分析
    social_data = self.fetcher.get_social_sentiment(symbol)

    if "error" in social_data:
        return social_data

    latest = social_data["latest"]
    trend = social_data.get("trend", [])
    mentions_trend = social_data.get("mentions_trend", [])

    # 计算情绪评分
    score = self._calculate_social_score(latest, trend, mentions_trend)

    # 情绪评级
    sentiment = latest.get("sentiment", 0)
    positive_ratio = latest.get("positiveRatio", 0.5)

    if sentiment > 0.2 and positive_ratio > 0.6:
        rating = "强"
    elif sentiment > 0:
        rating = "偏强"
    elif sentiment < -0.2 and positive_ratio < 0.4:
        rating = "弱"
    else:
        rating = "中性"

    return {
        "date": str(latest.get("date", "")),
        "sentiment": sentiment,           # -1到1
        "social_score": latest.get("socialScore", 50),  # 0-100
        "mentions": latest.get("mentions", 0),
        "positive_ratio": positive_ratio,
        "negative_ratio": latest.get("negativeRatio", 0.5),
        "trend_5d": self._get_social_trend_description(trend),
        "sentiment_rating": rating,
        "sentiment_score": score,
        "data_type": "social"  # 区分数据类型
    }

def _calculate_social_score(self, latest: dict, trend: list, mentions_trend: list) -> float:
    """
    美股社交媒体情绪评分 0-100

    算法:
    - 基础分 50
    - sentiment > 0 → +20分
    - positiveRatio > 0.6 → +15分
    - 社交评分高 → 按比例加分
    - 提及量增加 → +10分
    """
    score = 50

    sentiment = latest.get("sentiment", 0)
    positive_ratio = latest.get("positiveRatio", 0.5)
    social_score = latest.get("socialScore", 50)

    # sentiment (-1到1)
    if sentiment > 0:
        score += 20
        score += min(sentiment * 30, 20)  # 最多+20
    else:
        score -= 20
        score += max(sentiment * 30, -20)  # 最多-20

    # positive_ratio (0到1)
    if positive_ratio > 0.6:
        score += 15
    elif positive_ratio < 0.4:
        score -= 15

    # social_score (0到100)
    score += (social_score - 50) * 0.3

    # mentions trend
    if len(mentions_trend) >= 2:
        if mentions_trend[0] > mentions_trend[-1] * 1.5:
            score += 10  # 提及量显著增加

    return max(0, min(100, score))

def _get_social_trend_description(self, trend: list) -> str:
    """获取社交媒体趋势描述"""
    if not trend:
        return "数据不足"

    recent = trend[:5]
    positive = sum(1 for t in recent if t > 0)

    if positive >= 4:
        return "持续正面"
    elif positive >= 3:
        return "正面为主"
    elif positive <= 1:
        return "持续负面"
    else:
        return "震荡"
```

---

### Phase 3: NewsAnalyzer 扩展

**文件**: `news.py`

扩展新闻分析支持美股：

```python
def analyze_news_sentiment(self, news_data: dict, market: str = "cn") -> dict[str, Any]:
    """
    分析新闻情绪 (支持 A股和美股)

    Args:
        news_data: 新闻数据
        market: cn=A股, us=美股
    """
    if "error" in news_data:
        return {"error": news_data["error"]}

    news_list = news_data.get("news", [])

    if not news_list:
        return {
            "score": 70,
            "count": 0,
            "latest": "",
            "sentiment": "neutral"
        }

    # 根据市场选择关键词
    if market == "cn":
        positive_keywords = ["回购", "增持", "利好", "突破", "上涨", "增长", "盈利", "分红"]
        negative_keywords = ["减持", "利空", "下跌", "下滑", "亏损", "风险", "调查", "诉讼"]
    else:  # us
        positive_keywords = [
            "buy", "upgrade", "beat", "growth", "profit", "dividend",
            "surge", "rally", "bullish", "strong", "record", "expansion"
        ]
        negative_keywords = [
            "sell", "downgrade", "miss", "loss", "decline", "drop",
            "plunge", "bearish", "weak", "layoff", "lawsuit", "investigation"
        ]

    positive_count = 0
    negative_count = 0

    latest_news = news_list[0]["title"] if news_list else ""

    for news in news_list:
        title = news.get("title", "").lower()
        text = news.get("text", "").lower()

        content = title + " " + text

        for keyword in positive_keywords:
            if keyword.lower() in content:
                positive_count += 1
        for keyword in negative_keywords:
            if keyword.lower() in content:
                negative_count += 1

    # 计算情绪评分
    base_score = 70
    score = base_score + positive_count * 5 - negative_count * 10
    score = max(0, min(100, score))

    # 判断情绪
    if score >= 80:
        sentiment = "positive"
    elif score <= 50:
        sentiment = "negative"
    else:
        sentiment = "neutral"

    return {
        "score": round(score),
        "count": len(news_list),
        "latest": latest_news,
        "sentiment": sentiment,
        "positive_count": positive_count,
        "negative_count": negative_count
    }
```

---

### Phase 4: Analyzer 主分析器集成

**文件**: `analyzer.py`

修改 `_get_extended_analysis()` 方法支持美股：

```python
def _get_extended_analysis(self, symbol: str, market: str, fetcher, base_result: dict) -> dict[str, Any]:
    """
    获取扩展分析数据

    支持 A股和美股
    """
    extended = {}

    # 1. 市场情绪 (根据市场选择分析方式)
    sentiment_analyzer = SentimentAnalyzer(fetcher)
    extended["sentiment"] = sentiment_analyzer.analyze_social_sentiment(symbol, market)

    # 2. 技术面 (复用现有逻辑，两种市场通用)
    hist_data = fetcher.get_history(symbol)
    if hist_data is not None and not hist_data.empty:
        technical_analyzer = TechnicalAnalyzer(hist_data)
        extended["technical"] = technical_analyzer.analyze()
    else:
        extended["technical"] = {"error": "无法获取历史数据"}

    # 3. 新闻 (根据市场选择分析方式)
    news_fetcher = NewsFetcher(fetcher)
    news_data = news_fetcher.get_latest_news(symbol)
    extended["news"] = news_fetcher.analyze_news_sentiment(news_data, market)

    # 4. 综合评分
    scorer = ComprehensiveScorer()
    extended["comprehensive"] = scorer.calculate_overall_score({
        "fundamental": base_result,
        "sentiment": extended["sentiment"],
        "technical": extended["technical"],
        "news": extended["news"]
    })

    return extended
```

修改 `analyze()` 方法中的条件判断：

```python
# 原来: if full_analysis and market == "cn":
# 改为: if full_analysis:
if full_analysis:
    try:
        result.update(self._get_extended_analysis(symbol, market, fetcher, result))
    except Exception as e:
        result["extended_error"] = f"扩展分析失败: {str(e)}"
```

---

### Phase 5: 报告格式化扩展

**文件**: `analyzer.py`

更新格式化方法以支持美股数据：

```python
def _format_sentiment(self, sentiment: dict, market: str = "cn") -> list[str]:
    """格式化情绪面数据 (支持 A股和美股)"""
    lines = ["", "## 📊 市场情绪", "-" * 30]

    if "error" in sentiment:
        lines.append(f"⚠️ {sentiment['error']}")
        return lines

    data_type = sentiment.get("data_type", "fund_flow")

    if data_type == "social" and market == "us":
        # 美股社交媒体情绪
        lines.extend([
            "",
            f"**情绪指数**: {sentiment.get('sentiment', 0):.2f} (-1到1)",
            f"**社交评分**: {sentiment.get('social_score', 0)}/100",
            f"**提及量**: {sentiment.get('mentions', 0):,}",
            f"**正面占比**: {sentiment.get('positive_ratio', 0):.1%}",
            f"**情绪评级**: {sentiment.get('sentiment_rating', '')}",
            f"**情绪评分**: {sentiment.get('sentiment_score', 0)}/100",
            "",
            f"**5日趋势**: {sentiment.get('trend_5d', '')}",
        ])
    else:
        # A股资金流向 (原有逻辑)
        lines.extend([
            "",
            f"**主力净流入**: {sentiment.get('main_net_inflow', 0)/1e8:.2f}亿元",
            f"**净流入占比**: {sentiment.get('main_net_inflow_ratio', 0):.2f}%",
            f"**情绪评级**: {sentiment.get('sentiment_rating', '')}",
            f"**情绪评分**: {sentiment.get('sentiment_score', 0)}/100",
        ])

    return lines
```

更新 `format_report()` 方法传递市场参数：

```python
if "sentiment" in analysis_result:
    lines.extend(self._format_sentiment(analysis_result["sentiment"], analysis_result.get("market")))
```

---

## 依赖更新

无需新增依赖，现有的 `requests`, `pandas`, `numpy` 已足够。

---

## 测试计划

### 单元测试

```python
# 1. FMP 社交情绪测试
fetcher = FMPFetcher(FMP_CONFIG)
result = fetcher.get_social_sentiment("AAPL")
assert "latest" in result
assert "trend" in result
assert result["latest"]["sentiment"] >= -1 and result["latest"]["sentiment"] <= 1

# 2. FMP 新闻测试
result = fetcher.get_news("AAPL")
assert "news" in result
assert len(result["news"]) > 0

# 3. FMP 历史数据测试
df = fetcher.get_history("AAPL", 100)
assert df is not None
assert "收盘" in df.columns
```

### 集成测试

```bash
# 美股深度分析
/analyzing-financial-statements 深度分析 AAPL

# 预期输出包含:
# ✅ 市场情绪 (社交媒体情绪)
# ✅ 技术面 (MACD/RSI/均线)
# ✅ 最新资讯 (新闻情绪)
# ✅ 综合评分 (四维评分 + 操作建议)
```

### 对比测试

| 功能 | A股 (600519) | 美股 (AAPL) |
|------|-------------|-------------|
| 基本面分析 | ✅ | ✅ |
| 市场情绪 | ✅ 资金流向 | ✅ 社交情绪 |
| 技术面 | ✅ | ✅ |
| 消息面 | ✅ 中文新闻 | ✅ 英文新闻 |
| 综合评分 | ✅ | ✅ |

---

## 实现优先级

| 阶段 | 优先级 | 内容 | 预计工作量 |
|------|--------|------|------------|
| 1 | P0 | FMPFetcher 扩展 (3个新方法) | 高 |
| 2 | P0 | SentimentAnalyzer 扩展 (美股支持) | 中 |
| 3 | P1 | NewsAnalyzer 扩展 (美股支持) | 低 |
| 4 | P1 | Analyzer 集成 (移除市场限制) | 中 |
| 5 | P1 | 报告格式化扩展 | 中 |
| 6 | P2 | 测试与验证 | 中 |

---

## 风险与缓解

| 风险 | 缓解措施 | 状态 |
|------|----------|------|
| FMP API 配额限制 | 复用现有缓存机制 | 已规划 |
| 社交情绪数据可用性 | API 验证已通过 | ✅ 已解决 |
| 新闻关键词准确性 | 使用双向关键词库 | 已规划 |
| 数据格式差异 | 统一为标准格式 | 已规划 |

---

## 完成标准

- [ ] 美股支持完整四维分析
- [ ] 报告格式中美股/A股清晰区分
- [ ] 综合评分对美股适用
- [ ] 通过 AAPL 端到端测试
- [ ] SKILL.md 更新美股深度分析说明

---

## 后续优化

- [ ] 美股行业基准细化 (科技/金融/医疗等)
- [ ] 多股票对比分析
- [ ] 历史评分趋势图
