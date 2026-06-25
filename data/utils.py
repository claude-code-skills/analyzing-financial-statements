"""
工具函数
"""

import re
from typing import Optional


# 常用 A股 股票名称映射
COMMON_STOCK_NAMES = {
    # 白酒
    "贵州茅台": "600519",
    "茅台": "600519",  # 简称
    "五粮液": "000858",
    "泸州老窖": "000568",
    "剑南春": "600559",

    # 金融
    "平安银行": "000001",
    "招商银行": "600036",
    "工商银行": "601398",
    "建设银行": "601939",
    "中国银行": "601988",
    "农业银行": "601288",
    "中国平安": "601318",
    "中信证券": "600030",

    # 新能源汽车
    "比亚迪": "002594",
    "理想汽车": "LI",  # 美股上市
    "蔚来": "NIO",    # 美股上市
    "小鹏汽车": "XPEV", # 美股上市

    # 科技
    "苹果": "AAPL",
    "Apple": "AAPL",
    "特斯拉": "TSLA",
    "Tesla": "TSLA",
    "腾讯": "00700",   # 港股
    "阿里巴巴": "BABA", # 美股上市
    "百度": "BIDU",    # 美股上市
    "京东": "JD",      # 美股上市
    "网易": "NTES",    # 美股上市
    "美团": "03690",   # 港股

    # 医药
    "恒瑞医药": "600276",
    "药明康德": "603259",
    "爱尔眼科": "300015",

    # 消费
    "美的集团": "000333",
    "格力电器": "000651",
    "海尔智家": "600690",
    "伊利股份": "600887",

    # 其他
    "中国石油": "601857",
    "中国移动": "600941",
    "长江电力": "600900",
}


def parse_stock_input(user_input: str) -> dict[str, str]:
    """
    解析用户输入，提取股票代码和市场

    支持的格式:
    - "AAPL" (美股)
    - "苹果公司 AAPL"
    - "分析特斯拉 TSLA"
    - "600519" (A股)
    - "贵州茅台" (常用股票名称)

    Returns:
        {"symbol": str, "market": str}
        market: "us" (美股), "cn" (A股), "unknown"
    """
    # 先尝试匹配常用股票名称
    for stock_name, code in COMMON_STOCK_NAMES.items():
        if stock_name in user_input:
            symbol = code
            # 判断市场
            if len(symbol) == 5 and symbol.isdigit():
                market = "hk"
            elif symbol.isdigit():
                market = "cn"
            else:
                market = "us"
            return {"symbol": symbol, "market": market}

    # 提取股票代码 (1-5个大写字母、5-6位数字)
    # 支持 5 位数字（港股）和 6 位数字（A股）
    # 不使用 \b word boundary，因为中文字符会导致边界匹配异常
    match = re.search(r'(?<![A-Z0-9])([A-Z]{1,5}|\d{5,6})(?![A-Z0-9])', user_input.upper())
    if not match:
        return {"symbol": "", "market": "unknown"}

    symbol = match.group(1)

    # 判断市场
    if len(symbol) == 5 and symbol.isdigit():
        market = "hk"
    elif symbol.isdigit():
        market = "cn"
    else:
        market = "us"

    return {"symbol": symbol, "market": market}


def format_currency(value: float, currency: str = "USD") -> str:
    """格式化货币显示"""
    if abs(value) >= 1e9:
        return f"{value/1e9:.2f}B {currency}"
    elif abs(value) >= 1e6:
        return f"{value/1e6:.2f}M {currency}"
    else:
        return f"{value:,.2f} {currency}"
