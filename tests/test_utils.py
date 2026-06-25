"""Tests for data/utils module."""

import sys
import os
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from data.utils import parse_stock_input, format_currency


class TestParseStockInput:
    def test_us_stock_uppercase(self):
        result = parse_stock_input("AAPL")
        assert result["symbol"] == "AAPL"
        assert result["market"] == "us"

    def test_cn_stock_6digit(self):
        result = parse_stock_input("600519")
        assert result["symbol"] == "600519"
        assert result["market"] == "cn"

    def test_cn_stock_0digit(self):
        result = parse_stock_input("000858")
        assert result["symbol"] == "000858"
        assert result["market"] == "cn"

    def test_cn_stock_3digit(self):
        result = parse_stock_input("300015")
        assert result["symbol"] == "300015"
        assert result["market"] == "cn"

    def test_hk_stock_5digit(self):
        result = parse_stock_input("00700")
        assert result["symbol"] == "00700"
        assert result["market"] == "hk"

    def test_chinese_name_maotai(self):
        result = parse_stock_input("贵州茅台")
        assert result["symbol"] == "600519"
        assert result["market"] == "cn"

    def test_chinese_name_wuliangye(self):
        result = parse_stock_input("五粮液")
        assert result["symbol"] == "000858"
        assert result["market"] == "cn"

    def test_chinese_name_tesla(self):
        result = parse_stock_input("特斯拉")
        assert result["symbol"] == "TSLA"
        assert result["market"] == "us"

    def test_chinese_name_tencent(self):
        result = parse_stock_input("腾讯")
        assert result["symbol"] == "00700"
        assert result["market"] == "hk"

    def test_mixed_input(self):
        result = parse_stock_input("分析苹果公司 AAPL")
        assert result["symbol"] == "AAPL"
        assert result["market"] == "us"

    def test_empty_input(self):
        result = parse_stock_input("")
        assert result["symbol"] == ""
        assert result["market"] == "unknown"

    def test_unknown_input(self):
        result = parse_stock_input("随机文字")
        assert result["market"] == "unknown"

    def test_gibberish_uppercase_parsed_as_us(self):
        """Uppercase letters match as US stock code (parser cannot validate)."""
        result = parse_stock_input("随机文字xyz")
        assert result["symbol"] == "XYZ"
        assert result["market"] == "us"

    def test_short_name(self):
        result = parse_stock_input("茅台")
        assert result["symbol"] == "600519"

    def test_apple_english(self):
        result = parse_stock_input("Apple")
        assert result["symbol"] == "AAPL"
        assert result["market"] == "us"


class TestFormatCurrency:
    def test_billions(self):
        assert format_currency(1.5e9) == "1.50B USD"

    def test_millions(self):
        assert format_currency(5e6) == "5.00M USD"

    def test_thousands(self):
        assert format_currency(50000) == "50,000.00 USD"

    def test_custom_currency(self):
        assert format_currency(1e9, "CNY") == "1.00B CNY"

    def test_negative(self):
        assert format_currency(-2e9) == "-2.00B USD"
