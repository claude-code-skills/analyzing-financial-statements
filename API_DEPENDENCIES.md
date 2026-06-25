# API Dependencies

This document lists all third-party APIs and data sources used by `analyzing-financial-statements`.

## Data Sources by Market

### A-Share (China) - AKShare (Free)

**Financial Statements:**
- `stock_financial_report_sina` - Income statement, balance sheet, cash flow (Sina source)

**Market Data:**
- `stock_zh_a_daily` - Daily prices (163 source, forward-adjusted)
- `stock_zh_a_hist` - Historical prices (East Money source)
- `stock_bid_ask_em` - Level 2 quotes (East Money)

**Valuation:**
- `stock_zh_valuation_baidu` - PE/PB history (Baidu Stock Market)

**Sentiment Indicators:**
- `index_fear_greed_funddb` - Fear & Greed Index (Jucaiyuan/FundDB)
- `stock_margin_sse` - Margin balance (Shanghai Stock Exchange)
- `stock_hsgt_hist_em` - Northbound capital flows (East Money)
- `stock_market_fund_flow` - Main fund flows (East Money)
- `stock_zt_pool_em` - Limit up/down pool (East Money)
- `stock_a_indicator_lg` - CSI 300 valuation indicators (East Money)
- `fund_new_found_em` - New fund issuances (East Money)

**Other:**
- `stock_individual_info_em` - Company info (East Money)
- `stock_board_industry_name_em` - Industry classification (East Money)
- `stock_board_industry_cons_em` - Industry constituents (East Money)
- `stock_fhps_detail_em` - Dividend history (East Money)
- `stock_news_em` - News feed (East Money)
- `stock_individual_fund_flow` - Individual stock fund flows (East Money)

---

### US Stocks - FMP + AKShare

**FMP API** (requires `FMP_API_KEY`, free tier: 250 requests/day):
- `income-statement` - Income statement
- `balance-sheet-statement` - Balance sheet
- `cash-flow-statement` - Cash flow statement
- `quote` - Real-time quotes
- `ratios` - **Historical PE/PB ratios (FREE, not paid)**
- `ratios-ttm` - TTM valuation metrics
- `financial-growth` - Growth rates

**AKShare US** (Free):
- `stock_us_hist` - Historical prices (East Money US encoding: 105/106.XXX)

---

### ETF Data - Multi-Source Fallback

**Primary (Xueqiu):**
- `https://stock.xueqiu.com/v5/stock/quote.json` - Real-time + IOPV + premium rate
  - Requires `xq_a_token` (auto-refreshed via Playwright, cached 4 hours)

**Secondary (East Money):**
- `fund_etf_spot_em` - Real-time quotes (East Money)
- `fund_etf_hist_em` - Historical prices (East Money, fails for long start_date)

**Fallback (Sina):**
- `fund_etf_hist_sina` - Full history (non-adjusted, 159941 → 2659 rows)

**Index Valuation:**
- `stock_a_indicator_lg` - Index PE percentile (CSI 300)

---

### Hong Kong Stocks - Tencent Finance

- `http://qt.gtimg.cn/` - Real-time quotes (Tencent Finance)

---

## Authentication Requirements

| Data Source | Authentication | Rate Limit | Free Tier |
|-------------|----------------|------------|-----------|
| **AKShare** | None | 0.5s/request | Unlimited |
| **FMP** | `FMP_API_KEY` | 0.3s/request, retry 3x | 250/day (free) |
| **Xueqiu** | `xq_a_token` (auto-refresh) | 4-hour cache | Unlimited |
| **Tencent** | None | No explicit limit | Unlimited |

---

## Fallback Strategy

**ETF Premium Data:** Xueqiu → East Money → Sina (3-tier)

**ETF Long-term Prices:** East Money qfq → East Money non-adjusted → Sina full history (avoids long start_date boundary)

**US Long-term Prices:** East Money qfq → East Money non-adjusted → non-adjusted full history (AKShare free)

---

## Key Limitations

1. **FMP ratios:** Free but limited (250/day, sufficient for personal use)
2. **Xueqiu token:** Expires every 4 hours, auto-refreshed via Playwright
3. **US historical prices:** East Money long range may fail, but AKShare fallback available
4. **HK valuation percentile:** Not available (user explicitly not needed)

---

## Python Dependencies

See `requirements.txt` for full list:
- `akshare` - A-share/US/ETF data crawler
- `pandas` - Data processing
- `pandas-ta` - Technical indicators (MACD/RSI/KDJ/Bollinger Bands)
- `numpy` - Numerical computation
- `playwright` - Xueqiu token refresh
- `requests` - HTTP requests (FMP/Tencent/Xueqiu)

---

## API Key Setup

### FMP (Optional)

For US stock analysis, get a free API key at:
https://site.financialmodelingprep.com/developer/docs

Free tier: 250 requests/day (sufficient for personal use)

```bash
# Set in environment or .env file
export FMP_API_KEY=your_key_here
```

### Xueqiu (Automatic)

No manual setup needed. Token is automatically refreshed via Playwright and cached to `~/.epm_xueqiu_token.json`.

---

## Summary

**Core data sources are free or have sufficient free tiers. No paywall restrictions for personal use.**

- A-shares: AKShare (free, unlimited)
- US stocks: FMP free tier (250/day) + AKShare fallback
- ETFs: Xueqiu (free, auto-auth) + Sina fallback
- Hong Kong: Tencent (free)
