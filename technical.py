"""
技术指标分析模块 v2
pandas-ta 全量指标 + 多指标共振择时信号
"""

import pandas as pd
import numpy as np
from typing import Any


class TechnicalAnalyzer:
    """技术指标分析器 v2 - 支持pandas-ta全量指标"""

    def __init__(self, hist_data: pd.DataFrame):
        """
        Args:
            hist_data: 可能是中文列名（akshare原始）或英文列名（pandas-ta处理后）
        """
        self.df = hist_data.copy()
        self._normalize_columns()

    def _normalize_columns(self):
        """统一列名为英文"""
        cn_to_en = {
            "日期": "Date", "开盘": "Open", "收盘": "Close",
            "最高": "High", "最低": "Low", "成交量": "Volume",
            "成交额": "Amount", "振幅": "Amplitude",
            "涨跌幅": "Change_pct", "涨跌额": "Change",
            "换手率": "Turnover",
        }
        self.df.rename(columns=cn_to_en, inplace=True)

        # 确保数值类型
        for col in ["Open", "High", "Low", "Close", "Volume"]:
            if col in self.df.columns:
                self.df[col] = pd.to_numeric(self.df[col], errors="coerce")

    def _get_latest(self, series: pd.Series) -> float:
        """安全获取最新值"""
        val = series.iloc[-1] if len(series) > 0 else np.nan
        return round(float(val), 4) if pd.notna(val) else 0.0

    def _get_prev(self, series: pd.Series) -> float:
        """安全获取前一日值"""
        val = series.iloc[-2] if len(series) > 1 else np.nan
        return round(float(val), 4) if pd.notna(val) else 0.0

    # ─────────────────────────────────────────────
    # 核心指标（pandas-ta 实现）
    # ─────────────────────────────────────────────

    def _ensure_ta_indicators(self):
        """确保pandas-ta指标已计算"""
        if "MACD_12_26_9" in self.df.columns:
            return True  # 已计算

        try:
            import pandas_ta as ta
        except ImportError:
            return False

        df = self.df.copy()
        if "Date" in df.columns:
            df["Date"] = pd.to_datetime(df["Date"])
            df.set_index("Date", inplace=True)

        df.ta.macd(fast=12, slow=26, signal=9, append=True)
        df.ta.rsi(length=14, append=True)
        df.ta.stoch(k=3, d=3, append=True)
        df.ta.bbands(length=20, std=2, append=True)
        df.ta.obv(append=True)
        df.ta.atr(length=14, append=True)
        df.ta.adx(length=14, append=True)
        df.ta.cci(length=20, append=True)
        df.ta.mfi(length=14, append=True)

        df.reset_index(inplace=True)
        self.df = df
        return True

    def calculate_macd(self) -> dict[str, Any]:
        """MACD指标"""
        has_ta = self._ensure_ta_indicators()

        if has_ta and "MACD_12_26_9" in self.df.columns:
            dif = self.df["MACD_12_26_9"]
            dea = self.df["MACDs_12_26_9"]
            hist = self.df["MACDh_12_26_9"]
        else:
            # 手写备用
            close = self.df["Close"]
            ema_fast = close.ewm(span=12, adjust=False).mean()
            ema_slow = close.ewm(span=26, adjust=False).mean()
            dif = ema_fast - ema_slow
            dea = dif.ewm(span=9, adjust=False).mean()
            hist = (dif - dea) * 2

        latest_dif = self._get_latest(dif)
        latest_dea = self._get_latest(dea)
        latest_hist = self._get_latest(hist)
        prev_dif = self._get_prev(dif)
        prev_dea = self._get_prev(dea)

        # 信号判断
        if latest_dif > latest_dea and prev_dif <= prev_dea:
            signal = "golden_cross"
        elif latest_dif < latest_dea and prev_dif >= prev_dea:
            signal = "death_cross"
        elif latest_dif > latest_dea:
            signal = "bullish"
        else:
            signal = "bearish"

        return {
            "dif": latest_dif, "dea": latest_dea,
            "macd_hist": latest_hist, "signal": signal,
        }

    def calculate_rsi(self, period: int = 14) -> dict[str, Any]:
        """RSI指标"""
        has_ta = self._ensure_ta_indicators()

        if has_ta and f"RSI_{period}" in self.df.columns:
            rsi_val = self._get_latest(self.df[f"RSI_{period}"])
        else:
            close = self.df["Close"]
            delta = close.diff()
            gain = delta.where(delta > 0, 0)
            loss = -delta.where(delta < 0, 0)
            avg_gain = gain.rolling(window=period).mean()
            avg_loss = loss.rolling(window=period).mean().replace(0, np.nan)
            rs = avg_gain / avg_loss
            rsi = 100 - (100 / (1 + rs))
            rsi_val = self._get_latest(rsi)

        if rsi_val > 70:
            status = "overbought"
        elif rsi_val < 30:
            status = "oversold"
        elif rsi_val > 50:
            status = "strong"
        else:
            status = "weak"

        return {"rsi": round(rsi_val, 2), "status": status}

    def calculate_kdj(self) -> dict[str, Any]:
        """KDJ随机指标"""
        has_ta = self._ensure_ta_indicators()

        if has_ta and "STOCHk_3_3_3" in self.df.columns:
            k = self._get_latest(self.df["STOCHk_3_3_3"])
            d = self._get_latest(self.df["STOCHd_3_3_3"])
            prev_k = self._get_prev(self.df["STOCHk_3_3_3"])
            prev_d = self._get_prev(self.df["STOCHd_3_3_3"])
        else:
            # 手写备用
            high = self.df["High"]
            low = self.df["Low"]
            close = self.df["Close"]
            low_min = low.rolling(window=9).min()
            high_max = high.rolling(window=9).max()
            rsv = (close - low_min) / (high_max - low_min) * 100
            rsv = rsv.fillna(50)
            k = rsv.ewm(com=2, adjust=False).mean()
            d = k.ewm(com=2, adjust=False).mean()
            k_val = self._get_latest(k)
            d_val = self._get_latest(d)
            prev_k = self._get_prev(k)
            prev_d = self._get_prev(d)
            k, d = k_val, d_val

        j = 3 * k - 2 * d

        if k > d and prev_k <= prev_d:
            signal = "golden_cross"
        elif k < d and prev_k >= prev_d:
            signal = "death_cross"
        elif k > 80:
            signal = "overbought"
        elif k < 20:
            signal = "oversold"
        else:
            signal = "neutral"

        return {"k": round(k, 2), "d": round(d, 2), "j": round(j, 2), "signal": signal}

    def calculate_bollinger(self) -> dict[str, Any]:
        """布林带"""
        has_ta = self._ensure_ta_indicators()

        if has_ta and "BBU_20_2.0" in self.df.columns:
            upper = self._get_latest(self.df["BBU_20_2.0"])
            middle = self._get_latest(self.df["BBM_20_2.0"])
            lower = self._get_latest(self.df["BBL_20_2.0"])
        else:
            close = self.df["Close"]
            middle = self._get_latest(close.rolling(20).mean())
            std = self._get_latest(close.rolling(20).std())
            upper = middle + 2 * std
            lower = middle - 2 * std

        close = self._get_latest(self.df["Close"])
        bandwidth = (upper - lower) / middle * 100 if middle > 0 else 0

        if close >= upper:
            position = "above_upper"
        elif close <= lower:
            position = "below_lower"
        elif close > middle:
            position = "upper_half"
        else:
            position = "lower_half"

        # 带宽收窄判断
        if len(self.df) >= 20:
            bw_series = (self.df["High"].rolling(20).max() - self.df["Low"].rolling(20).min()) / self.df["Close"].rolling(20).mean() * 100
            recent_bw = bw_series.dropna().tail(5).mean()
            older_bw = bw_series.dropna().tail(20).head(15).mean()
            if recent_bw < older_bw * 0.7:
                squeeze = "narrowing"
            elif recent_bw > older_bw * 1.3:
                squeeze = "expanding"
            else:
                squeeze = "stable"
        else:
            squeeze = "unknown"

        return {
            "upper": round(upper, 2), "middle": round(middle, 2),
            "lower": round(lower, 2), "bandwidth": round(bandwidth, 2),
            "position": position, "squeeze": squeeze,
        }

    def calculate_obv(self) -> dict[str, Any]:
        """OBV能量潮"""
        has_ta = self._ensure_ta_indicators()

        if has_ta and "OBV" in self.df.columns:
            obv = self.df["OBV"]
        else:
            close = self.df["Close"]
            volume = self.df["Volume"]
            direction = np.where(close > close.shift(1), 1, np.where(close < close.shift(1), -1, 0))
            obv = (volume * direction).cumsum()

        obv_latest = self._get_latest(obv)
        obv_ma5 = self._get_latest(obv.rolling(5).mean())

        trend = "rising" if obv_latest > obv_ma5 else "falling"

        return {"obv": round(obv_latest, 0), "obv_ma5": round(obv_ma5, 0), "trend": trend}

    def calculate_atr(self, period: int = 14) -> dict[str, Any]:
        """ATR真实波幅"""
        has_ta = self._ensure_ta_indicators()

        if has_ta and f"ATRr_{period}" in self.df.columns:
            atr_val = self._get_latest(self.df[f"ATRr_{period}"])
        else:
            high = self.df["High"]
            low = self.df["Low"]
            close = self.df["Close"]
            tr = pd.concat([
                high - low,
                (high - close.shift(1)).abs(),
                (low - close.shift(1)).abs()
            ], axis=1).max(axis=1)
            atr_val = self._get_latest(tr.rolling(period).mean())

        close = self._get_latest(self.df["Close"])
        atr_pct = (atr_val / close * 100) if close > 0 else 0

        return {"atr": round(atr_val, 2), "atr_pct": round(atr_pct, 2)}

    def calculate_adx(self, period: int = 14) -> dict[str, Any]:
        """ADX趋势强度"""
        has_ta = self._ensure_ta_indicators()

        if has_ta and f"ADX_{period}" in self.df.columns:
            adx = self._get_latest(self.df[f"ADX_{period}"])
            plus_di = self._get_latest(self.df[f"DMP_{period}"])
            minus_di = self._get_latest(self.df[f"DMN_{period}"])
        else:
            adx, plus_di, minus_di = 25, 25, 25  # 默认中性

        if adx > 40:
            strength = "strong_trend"
        elif adx > 25:
            strength = "trending"
        else:
            strength = "ranging"

        direction = "bullish" if plus_di > minus_di else "bearish"

        return {"adx": round(adx, 2), "plus_di": round(plus_di, 2), "minus_di": round(minus_di, 2), "strength": strength, "direction": direction}

    def calculate_cci(self, period: int = 20) -> dict[str, Any]:
        """CCI商品通道指数"""
        has_ta = self._ensure_ta_indicators()

        if has_ta and f"CCI_{period}_0.015" in self.df.columns:
            cci = self._get_latest(self.df[f"CCI_{period}_0.015"])
            if abs(cci) > 500:
                cci = 0
        else:
            cci = 0

        if cci > 100:
            status = "overbought"
        elif cci < -100:
            status = "oversold"
        else:
            status = "neutral"

        return {"cci": round(cci, 2), "status": status}

    def calculate_mfi(self, period: int = 14) -> dict[str, Any]:
        """MFI资金流量指数"""
        has_ta = self._ensure_ta_indicators()

        if has_ta and f"MFI_{period}" in self.df.columns:
            mfi = self._get_latest(self.df[f"MFI_{period}"])
        else:
            mfi = 50

        if mfi > 80:
            status = "overbought"
        elif mfi < 20:
            status = "oversold"
        else:
            status = "neutral"

        return {"mfi": round(mfi, 2), "status": status}

    # ─────────────────────────────────────────────
    # 均线系统
    # ─────────────────────────────────────────────

    def get_ma_system(self) -> dict[str, Any]:
        """均线系统分析"""
        close = self.df["Close"]
        ma5 = self._get_latest(close.rolling(5).mean())
        ma10 = self._get_latest(close.rolling(10).mean())
        ma20 = self._get_latest(close.rolling(20).mean())
        ma60 = self._get_latest(close.rolling(60).mean())

        if ma5 > ma10 > ma20 > ma60 and ma60 > 0:
            trend = "bullish"
        elif ma5 < ma10 < ma20 < ma60 and ma60 > 0:
            trend = "bearish"
        else:
            trend = "mixed"

        return {"ma5": ma5, "ma10": ma10, "ma20": ma20, "ma60": ma60, "trend": trend}

    # ─────────────────────────────────────────────
    # 量价分析
    # ─────────────────────────────────────────────

    def volume_price_analysis(self) -> dict[str, Any]:
        """量价背离检测"""
        close = self.df["Close"]
        volume = self.df["Volume"]

        if len(close) < 10:
            return {"signal": "insufficient_data"}

        # 近5日 vs 前5日
        price_change_5d = (close.iloc[-1] - close.iloc[-6]) / close.iloc[-6] * 100 if close.iloc[-6] > 0 else 0
        vol_change_5d = (volume.tail(5).mean() - volume.iloc[-10:-5].mean()) / volume.iloc[-10:-5].mean() * 100 if volume.iloc[-10:-5].mean() > 0 else 0

        # 量价背离判断
        if price_change_5d > 2 and vol_change_5d < -10:
            signal = "bearish_divergence"  # 价涨量缩
            warning = "上涨动能不足"
        elif price_change_5d < -2 and vol_change_5d > 10:
            signal = "panic_selling"  # 价跌量增
            warning = "恐慌性抛售"
        elif price_change_5d > 2 and vol_change_5d > 10:
            signal = "healthy_rally"  # 价涨量增
            warning = ""
        elif price_change_5d < -2 and vol_change_5d < -10:
            signal = "shrinking_decline"  # 缩量下跌
            warning = "抛压减弱"
        else:
            signal = "neutral"
            warning = ""

        return {
            "price_change_5d": round(price_change_5d, 2),
            "vol_change_5d": round(vol_change_5d, 2),
            "signal": signal,
            "warning": warning,
        }

    # ─────────────────────────────────────────────
    # 综合分析 + 多指标共振
    # ─────────────────────────────────────────────

    def analyze(self) -> dict[str, Any]:
        """综合技术分析 + 多指标共振择时信号"""
        macd = self.calculate_macd()
        rsi = self.calculate_rsi()
        kdj = self.calculate_kdj()
        bollinger = self.calculate_bollinger()
        obv = self.calculate_obv()
        atr = self.calculate_atr()
        adx = self.calculate_adx()
        cci = self.calculate_cci()
        mfi = self.calculate_mfi()
        ma = self.get_ma_system()
        vol_price = self.volume_price_analysis()

        # 多指标共振评分
        buy_signals = 0
        sell_signals = 0
        total_signals = 7

        # MACD
        if macd["signal"] == "golden_cross":
            buy_signals += 1.5
        elif macd["signal"] == "bullish":
            buy_signals += 0.5
        elif macd["signal"] == "death_cross":
            sell_signals += 1.5
        elif macd["signal"] == "bearish":
            sell_signals += 0.5

        # RSI
        if rsi["status"] == "oversold":
            buy_signals += 1
        elif rsi["status"] == "overbought":
            sell_signals += 1

        # KDJ
        if kdj["signal"] in ("golden_cross", "oversold"):
            buy_signals += 1
        elif kdj["signal"] in ("death_cross", "overbought"):
            sell_signals += 1

        # 布林带
        if bollinger["position"] == "below_lower":
            buy_signals += 1
        elif bollinger["position"] == "above_upper":
            sell_signals += 1

        # OBV趋势
        if obv["trend"] == "rising":
            buy_signals += 0.5
        elif obv["trend"] == "falling":
            sell_signals += 0.5

        # 均线趋势
        if ma["trend"] == "bullish":
            buy_signals += 1
        elif ma["trend"] == "bearish":
            sell_signals += 1

        # ADX趋势方向
        if adx["direction"] == "bullish" and adx["strength"] != "ranging":
            buy_signals += 0.5
        elif adx["direction"] == "bearish" and adx["strength"] != "ranging":
            sell_signals += 0.5

        # 综合信号
        net_score = buy_signals - sell_signals
        if net_score >= 3:
            timing_signal = "strong_buy"
            confidence = min(95, 60 + net_score * 5)
        elif net_score >= 1.5:
            timing_signal = "buy"
            confidence = 55 + net_score * 5
        elif net_score <= -3:
            timing_signal = "strong_sell"
            confidence = min(95, 60 + abs(net_score) * 5)
        elif net_score <= -1.5:
            timing_signal = "sell"
            confidence = 55 + abs(net_score) * 5
        else:
            timing_signal = "hold"
            confidence = 50

        return {
            "macd": macd,
            "rsi": rsi,
            "kdj": kdj,
            "bollinger": bollinger,
            "obv": obv,
            "atr": atr,
            "adx": adx,
            "cci": cci,
            "mfi": mfi,
            "ma_system": ma,
            "volume_price": vol_price,
            "timing_signal": timing_signal,
            "confidence": round(confidence, 1),
            "buy_signals": round(buy_signals, 1),
            "sell_signals": round(sell_signals, 1),
        }
