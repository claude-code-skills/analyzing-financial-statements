"""Tests for data/cache module."""

import sys
import os
import json
import tempfile
import time
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.cache import DataCache
from data.config import CacheConfig


class TestDataCache:
    def test_disabled_cache_returns_none(self):
        config = CacheConfig(enabled=False, ttl_hours=1, cache_dir=tempfile.mkdtemp())
        cache = DataCache(config)
        cache.set("test_key", {"data": "value"})
        assert cache.get("test_key") is None

    def test_enabled_cache_round_trip(self):
        config = CacheConfig(enabled=True, ttl_hours=1, cache_dir=tempfile.mkdtemp())
        cache = DataCache(config)
        cache.set("test_key", {"hello": "world"})
        result = cache.get("test_key")
        assert result == {"hello": "world"}

    def test_cache_expiry(self):
        config = CacheConfig(enabled=True, ttl_hours=0, cache_dir=tempfile.mkdtemp())
        cache = DataCache(config)
        cache.set("test_key", {"data": "old"})
        # ttl_hours=0 means immediately expired
        time.sleep(0.1)
        assert cache.get("test_key") is None

    def test_cache_key_sanitization(self):
        config = CacheConfig(enabled=True, ttl_hours=1, cache_dir=tempfile.mkdtemp())
        cache = DataCache(config)
        cache.set("path/with/slashes", {"val": 1})
        assert cache.get("path/with/slashes") == {"val": 1}

    def test_nonexistent_key(self):
        config = CacheConfig(enabled=True, ttl_hours=1, cache_dir=tempfile.mkdtemp())
        cache = DataCache(config)
        assert cache.get("nonexistent") is None

    def test_corrupted_cache_file(self):
        config = CacheConfig(enabled=True, ttl_hours=1, cache_dir=tempfile.mkdtemp())
        cache = DataCache(config)
        # Write invalid JSON directly
        cache_path = cache._get_cache_path("bad_key")
        with open(cache_path, "w") as f:
            f.write("not valid json{{{")
        assert cache.get("bad_key") is None
