# FMP API 升级方案 v3.0

> 适配最新的 FMP Stable API

---

## 问题分析

| 项目 | 旧版 | 新版 |
|------|------|------|
| Base URL | `/api/v3/` | `/stable/` |
| 代理支持 | 无 | 需绕过系统代理 |
| API Key | ✅ 有效 | ✅ 有效（需新URL） |

---

## 修改方案

### 修改 1: data/config.py

```python
# 修改前
base_url="https://financialmodelingprep.com/api/v3",

# 修改后
base_url="https://financialmodelingprep.com/stable",
```

### 修改 2: data/fetchers/base.py

在 `_make_request` 方法中添加 `proxies={"http": None, "https": None}` 绕过代理：

```python
response = requests.get(
    url,
    params=params,
    timeout=self.config.timeout,
    proxies={"http": None, "https": None},  # 新增
)
```

### 修改 3: data/fetchers/fmp.py

更新端点格式（移除多余的 `{symbol}` 格式化）：

```python
# 原来的格式化方式已经是正确的，保持不变
data = self._make_request(f"income-statement?symbol={symbol}", {})
```

---

## 测试验证

```bash
# 测试新 URL 是否返回数据
curl --noproxy "*" \
  "https://financialmodelingprep.com/stable/quote?symbol=AAPL&apikey=YOUR_KEY"

# 预期返回包含 price, marketCap 等字段的 JSON
```

---

## 文件修改清单

| 文件 | 修改内容 |
|------|----------|
| `data/config.py` | 更新 base_url |
| `data/fetchers/base.py` | 添加 proxies 参数 |
| `.env` | API Key 已配置，无需修改 |

---

## 待确认

- [ ] 是否需要修改缓存目录（目前缓存在 `.cache/financial_data/`）
- [ ] 是否需要添加更多 API 端点（如 `/search-name`, `/profile`）

---

**等待 Review 👀**
