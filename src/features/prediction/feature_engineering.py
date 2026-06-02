from __future__ import annotations

import numpy as np
import pandas as pd


def calculate_rsi(close: pd.Series, window: int = 14) -> pd.Series:
    delta = close.diff()
    gain = delta.clip(lower=0).ewm(alpha=1 / window, adjust=False).mean()
    loss = (-delta.clip(upper=0)).ewm(alpha=1 / window, adjust=False).mean()
    relative_strength = gain / (loss + 1e-9)
    return 100 - (100 / (1 + relative_strength))


def calculate_atr(history: pd.DataFrame, window: int = 14) -> pd.Series:
    high = history["high"]
    low = history["low"]
    close = history["model_close"]
    true_range = pd.concat(
        [
            high - low,
            (high - close.shift()).abs(),
            (low - close.shift()).abs(),
        ],
        axis=1,
    ).max(axis=1)
    return true_range.rolling(window).mean()


def add_moving_average_features(features: pd.DataFrame, close: pd.Series) -> None:
    for window in [5, 10, 20, 50, 100]:
        sma = close.rolling(window).mean()
        ema = close.ewm(span=window, adjust=False).mean()
        features[f"sma_gap_{window}"] = (close / sma) - 1
        features[f"ema_gap_{window}"] = (close / ema) - 1
        features[f"momentum_{window}"] = close.pct_change(window)


def add_volume_features(features: pd.DataFrame, close: pd.Series, volume: pd.Series) -> None:
    features["volume_z20"] = (volume - volume.rolling(20).mean()) / (volume.rolling(20).std() + 1)
    signed_volume = (np.sign(close.diff()).fillna(0) * volume).cumsum()
    obv_base = signed_volume.rolling(20).mean().abs() + 1
    features["obv_momentum"] = (signed_volume - signed_volume.rolling(20).mean()) / obv_base


def build_feature_frame(history: pd.DataFrame) -> tuple[pd.DataFrame, pd.Series, pd.Series]:
    close = history["model_close"]
    high = history["high"]
    low = history["low"]
    open_price = history["open"]
    volume = history["volume"].fillna(0)
    returns = close.pct_change()
    atr = calculate_atr(history)

    features = pd.DataFrame(index=history.index)
    features["return_1"] = returns
    features["return_2"] = close.pct_change(2)
    features["return_5"] = close.pct_change(5)
    features["range_pct"] = (high - low) / close
    features["gap_pct"] = (open_price / close.shift(1)) - 1

    add_moving_average_features(features, close)
    for window in [5, 10, 20]:
        features[f"volatility_{window}"] = returns.rolling(window).std()

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    macd_signal = macd.ewm(span=9, adjust=False).mean()

    features["rsi_14"] = calculate_rsi(close)
    features["macd_pct"] = macd / close
    features["macd_signal_pct"] = macd_signal / close
    features["macd_hist_pct"] = (macd - macd_signal) / close
    features["atr_pct"] = atr / close
    add_volume_features(features, close, volume)

    day_of_week = pd.Series(history.index.dayofweek, index=history.index)
    features["dow_sin"] = np.sin(2 * np.pi * day_of_week / 7)
    features["dow_cos"] = np.cos(2 * np.pi * day_of_week / 7)

    target_return = (close.shift(-1) / close) - 1
    return features.replace([np.inf, -np.inf], np.nan), target_return, atr
