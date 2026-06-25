"""
本地缓存管理
避免频繁调用 API
"""

import json
import os
import time
from pathlib import Path
from typing import Any, Optional

from .config import CacheConfig, CACHE_CONFIG


class DataCache:
    """本地文件缓存"""

    def __init__(self, config: CacheConfig | None = None):
        self.config = config if config is not None else CACHE_CONFIG
        self.cache_dir = Path(self.config.cache_dir)
        self.cache_dir.mkdir(parents=True, exist_ok=True)

    def _get_cache_path(self, key: str) -> Path:
        """获取缓存文件路径"""
        safe_key = key.replace("/", "_").replace("\\", "_")
        return self.cache_dir / f"{safe_key}.json"

    def get(self, key: str) -> Optional[dict]:
        """从缓存获取数据"""
        if not self.config.enabled:
            return None

        cache_path = self._get_cache_path(key)

        if not cache_path.exists():
            return None

        try:
            with open(cache_path, "r", encoding="utf-8") as f:
                data = json.load(f)

            cached_time = data.get("_cached_at", 0)
            ttl_seconds = self.config.ttl_hours * 3600

            if time.time() - cached_time > ttl_seconds:
                # 惰性清理：过期后删除文件
                cache_path.unlink(missing_ok=True)
                return None

            return data.get("data")
        except (json.JSONDecodeError, KeyError, IOError):
            return None

    def set(self, key: str, value: dict) -> None:
        """写入缓存"""
        if not self.config.enabled:
            return

        cache_path = self._get_cache_path(key)

        cache_data = {
            "_cached_at": time.time(),
            "data": value,
        }

        try:
            with open(cache_path, "w", encoding="utf-8") as f:
                json.dump(cache_data, f, ensure_ascii=False, indent=2)
        except IOError:
            pass


# 全局缓存实例
cache = DataCache()
