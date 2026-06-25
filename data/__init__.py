"""
数据层入口
"""

from .cache import cache, DataCache
from .config import FMP_CONFIG, CACHE_CONFIG
from .fetchers.base import BaseFetcher, FetchError
from .fetchers.fmp import FMPFetcher
from .fetchers.akshare import AKShareFetcher
from .fetchers.a_share_special import AShareSpecialFetcher
from .fetchers.etf import ETFFetcher
from .fetchers.hk_share import HKShareFetcher
from .utils import parse_stock_input

__all__ = [
    'cache',
    'DataCache',
    'FMP_CONFIG',
    'CACHE_CONFIG',
    'BaseFetcher',
    'FetchError',
    'FMPFetcher',
    'AKShareFetcher',
    'AShareSpecialFetcher',
    'ETFFetcher',
    'HKShareFetcher',
    'parse_stock_input',
    'create_fetcher',
]


def create_fetcher(market: str = "us"):
    """
    创建数据获取器（工厂函数）

    Args:
        market: 市场类型 ("us" 美股, "cn" A股)

    Returns:
        对应市场的 Fetcher 实例

    Raises:
        FetchError: 不支持的市场或配置错误
    """
    if market == "us":
        if not FMP_CONFIG.api_key:
            raise FetchError(
                "FMP_API_KEY not configured. "
                "Please set it in .env file or get a free key at: "
                "https://site.financialmodelingprep.com/developer/docs"
            )
        return FMPFetcher(FMP_CONFIG)

    elif market == "cn":
        # AKShare 不需要 API Key
        return AKShareFetcher(cache_instance=cache)

    elif market == "hk":
        return HKShareFetcher()

    else:
        raise FetchError(f"Unsupported market: {market}")
