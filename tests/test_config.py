"""Tests for data/config module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.config import APIConfig, CacheConfig, FMP_CONFIG, CACHE_CONFIG


class TestAPIConfig:
    def test_default_values(self):
        config = APIConfig(base_url="https://example.com")
        assert config.base_url == "https://example.com"
        assert config.api_key is None
        assert config.timeout == 10
        assert config.max_retries == 3
        assert config.rate_limit_delay == 1.0

    def test_custom_values(self):
        config = APIConfig(
            base_url="https://api.test.com",
            api_key="test_key",
            timeout=30,
            max_retries=5,
            rate_limit_delay=2.0,
        )
        assert config.api_key == "test_key"
        assert config.timeout == 30


class TestCacheConfig:
    def test_default_disabled(self):
        config = CacheConfig()
        assert config.enabled is False
        assert config.ttl_hours == 0

    def test_cache_dir(self):
        assert ".cache" in CACHE_CONFIG.cache_dir


class TestFMPConfig:
    def test_base_url(self):
        assert "financialmodelingprep.com" in FMP_CONFIG.base_url
