"""
数据获取器基类
"""

import time
from abc import ABC, abstractmethod
from typing import Any

import requests

from ..cache import cache
from ..config import APIConfig


class FetchError(Exception):
    """数据获取失败异常"""
    def __init__(self, message: str, source: str = ""):
        self.message = message
        self.source = source
        super().__init__(f"[{source}] {message}")


class BaseFetcher(ABC):
    """数据获取器基类"""

    def __init__(self, config: APIConfig):
        self.config = config
        self._last_request_time = 0

    def _make_request(self, endpoint: str, params: dict) -> Any:
        """发起 API 请求（带重试和速率限制）"""
        self._rate_limit()

        params = params.copy()
        params["apikey"] = self.config.api_key

        url = f"{self.config.base_url}/{endpoint}"

        for attempt in range(self.config.max_retries):
            try:
                response = requests.get(
                    url,
                    params=params,
                    timeout=self.config.timeout,
                    proxies={"http": None, "https": None},
                )
                response.raise_for_status()

                data = response.json()

                if isinstance(data, dict) and "Error Message" in data:
                    raise FetchError(data["Error Message"], self.__class__.__name__)

                return data

            except requests.RequestException as e:
                if attempt == self.config.max_retries - 1:
                    raise FetchError(f"请求失败: {str(e)}", self.__class__.__name__)

                wait_time = (2 ** attempt) * self.config.rate_limit_delay
                time.sleep(wait_time)

    def _rate_limit(self):
        """简单的速率限制"""
        now = time.time()
        elapsed = now - self._last_request_time

        if elapsed < self.config.rate_limit_delay:
            time.sleep(self.config.rate_limit_delay - elapsed)

        self._last_request_time = time.time()

    def _cached_request(self, cache_key: str, fetch_func) -> dict:
        """带缓存的请求"""
        cached = cache.get(cache_key)
        if cached is not None:
            return cached

        data = fetch_func()
        cache.set(cache_key, data)

        return data

    @abstractmethod
    def get_financial_data(self, symbol: str) -> dict:
        """获取财务数据"""
        pass

    @abstractmethod
    def get_market_data(self, symbol: str) -> dict:
        """获取市场数据"""
        pass
