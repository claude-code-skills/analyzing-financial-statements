"""
配置管理
集中管理所有配置项
"""

import os
from dataclasses import dataclass
from typing import Optional

from dotenv import load_dotenv

# skill 目录绝对路径（不受 CWD 影响）
_SKILL_DIR = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))

load_dotenv(os.path.join(_SKILL_DIR, ".env"))


@dataclass
class APIConfig:
    """API 配置"""
    base_url: str
    api_key: Optional[str] = None
    timeout: int = 10
    max_retries: int = 3
    rate_limit_delay: float = 1.0


@dataclass
class CacheConfig:
    """缓存配置"""
    enabled: bool = False
    ttl_hours: int = 0
    cache_dir: str = os.path.join(_SKILL_DIR, ".cache", "financial_data")


# 数据源配置
FMP_CONFIG = APIConfig(
    base_url="https://financialmodelingprep.com/stable",
    api_key=os.getenv("FMP_API_KEY"),
)

# 缓存配置
CACHE_CONFIG = CacheConfig()
