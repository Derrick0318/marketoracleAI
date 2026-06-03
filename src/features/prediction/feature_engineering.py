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
    for window in [5, 10, 20, 50, 100, 200]:
        sma = close.rolling(window).mean()
        ema = close.ewm(span=window, adjust=False).mean()
        features[f"sma_gap_{window}"] = (close / sma) - 1
        features[f"ema_gap_{window}"] = (close / ema) - 1
        features[f"momentum_{window}"] = close.pct_change(window)


def add_volume_features(features: pd.DataFrame, close: pd.Series, volume: pd.Series) -> None:
    features["volume_z20"] = (volume - volume.rolling(20).mean()) / (volume.rolling(20).std() + 1)
    features["volume_ratio_5_20"] = (volume.rolling(5).mean() / (volume.rolling(20).mean() + 1)) - 1
    features["volume_ratio_20_60"] = (volume.rolling(20).mean() / (volume.rolling(60).mean() + 1)) - 1
    signed_volume = (np.sign(close.diff()).fillna(0) * volume).cumsum()
    obv_base = signed_volume.rolling(20).mean().abs() + 1
    features["obv_momentum"] = (signed_volume - signed_volume.rolling(20).mean()) / obv_base


def add_candle_features(features: pd.DataFrame, history: pd.DataFrame) -> None:
    close = history["model_close"]
    open_price = history["open"]
    high = history["high"]
    low = history["low"]
    candle_range = (high - low).replace(0, np.nan)
    body = close - open_price

    features["intraday_return"] = (close / open_price.replace(0, np.nan)) - 1
    features["close_position"] = (close - low) / candle_range
    features["body_pct"] = body / close
    features["upper_wick_pct"] = (high - pd.concat([open_price, close], axis=1).max(axis=1)) / close
    features["lower_wick_pct"] = (pd.concat([open_price, close], axis=1).min(axis=1) - low) / close


def add_volatility_features(features: pd.DataFrame, close: pd.Series, returns: pd.Series, atr: pd.Series) -> None:
    for window in [5, 10, 20, 40, 60]:
        features[f"volatility_{window}"] = returns.rolling(window).std()
        features[f"return_mean_{window}"] = returns.rolling(window).mean()
        features[f"return_skew_{window}"] = returns.rolling(window).skew()

    rolling_max = close.rolling(60).max()
    features["drawdown_60"] = (close / rolling_max) - 1
    features["atr_pct"] = atr / close
    features["atr_trend_14_50"] = (atr / (atr.rolling(50).mean() + 1e-9)) - 1


def add_bollinger_features(features: pd.DataFrame, close: pd.Series) -> None:
    rolling_20 = close.rolling(20)
    middle = rolling_20.mean()
    std = rolling_20.std()
    upper = middle + (2 * std)
    lower = middle - (2 * std)

    features["bb_z20"] = (close - middle) / (std + 1e-9)
    features["bb_width20"] = (upper - lower) / close
    features["bb_position20"] = (close - lower) / ((upper - lower) + 1e-9)


def add_stochastic_features(features: pd.DataFrame, high: pd.Series, low: pd.Series, close: pd.Series) -> None:
    lowest_14 = low.rolling(14).min()
    highest_14 = high.rolling(14).max()
    stochastic_k = 100 * (close - lowest_14) / ((highest_14 - lowest_14) + 1e-9)
    features["stoch_k14"] = stochastic_k
    features["stoch_d3"] = stochastic_k.rolling(3).mean()


def add_lag_features(features: pd.DataFrame, returns: pd.Series) -> None:
    for lag in range(1, 11):
        features[f"return_lag_{lag}"] = returns.shift(lag)


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
    features["return_10"] = close.pct_change(10)
    features["return_20"] = close.pct_change(20)
    features["range_pct"] = (high - low) / close
    features["gap_pct"] = (open_price / close.shift(1)) - 1
    features["overnight_gap_abs"] = features["gap_pct"].abs()

    add_lag_features(features, returns)
    add_candle_features(features, history)
    add_moving_average_features(features, close)
    add_volatility_features(features, close, returns, atr)
    add_bollinger_features(features, close)
    add_stochastic_features(features, high, low, close)

    ema_12 = close.ewm(span=12, adjust=False).mean()
    ema_26 = close.ewm(span=26, adjust=False).mean()
    macd = ema_12 - ema_26
    macd_signal = macd.ewm(span=9, adjust=False).mean()

    features["rsi_14"] = calculate_rsi(close)
    features["macd_pct"] = macd / close
    features["macd_signal_pct"] = macd_signal / close
    features["macd_hist_pct"] = (macd - macd_signal) / close
    add_volume_features(features, close, volume)

    day_of_week = pd.Series(history.index.dayofweek, index=history.index)
    month_of_year = pd.Series(history.index.month, index=history.index)
    features["dow_sin"] = np.sin(2 * np.pi * day_of_week / 7)
    features["dow_cos"] = np.cos(2 * np.pi * day_of_week / 7)
    features["month_sin"] = np.sin(2 * np.pi * month_of_year / 12)
    features["month_cos"] = np.cos(2 * np.pi * month_of_year / 12)

    target_return = (close.shift(-1) / close) - 1
    return features.replace([np.inf, -np.inf], np.nan), target_return, atr
