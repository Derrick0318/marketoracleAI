from __future__ import annotations

import math
import os
from typing import Any

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import ExtraTreesRegressor, HistGradientBoostingRegressor, RandomForestRegressor
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.pipeline import make_pipeline


def model_blueprints(fast: bool = False) -> list[tuple[str, Any]]:
    if fast:
        return [
            (
                "Fast Gradient Boosting",
                make_pipeline(
                    SimpleImputer(strategy="median"),
                    HistGradientBoostingRegressor(
                        max_iter=80,
                        learning_rate=0.06,
                        max_leaf_nodes=23,
                        l2_regularization=0.08,
                        random_state=42,
                    ),
                ),
            ),
            (
                "Fast Extra Trees",
                make_pipeline(
                    SimpleImputer(strategy="median"),
                    ExtraTreesRegressor(
                        n_estimators=48,
                        max_depth=8,
                        min_samples_leaf=4,
                        random_state=42,
                        n_jobs=1,
                    ),
                ),
            ),
        ]

    return [
        (
            "Histogram Gradient Boosting",
            make_pipeline(
                SimpleImputer(strategy="median"),
                HistGradientBoostingRegressor(
                    max_iter=420,
                    learning_rate=0.045,
                    max_leaf_nodes=31,
                    l2_regularization=0.05,
                    random_state=42,
                ),
            ),
        ),
        (
            "Random Forest",
            make_pipeline(
                SimpleImputer(strategy="median"),
                RandomForestRegressor(
                    n_estimators=260,
                    max_depth=9,
                    min_samples_leaf=4,
                    random_state=42,
                    n_jobs=1,
                ),
            ),
        ),
        (
            "Extra Trees",
            make_pipeline(
                SimpleImputer(strategy="median"),
                ExtraTreesRegressor(
                    n_estimators=320,
                    max_depth=10,
                    min_samples_leaf=3,
                    random_state=42,
                    n_jobs=1,
                ),
            ),
        ),
    ]


def train_and_predict(features: pd.DataFrame, target_return: pd.Series, fast: bool = False) -> dict[str, Any]:
    training = features.copy()
    training["target_return"] = target_return
    training = training.iloc[110:].dropna(subset=["target_return"])
    if len(training) < 120:
        raise ValueError("Not enough clean training rows after feature engineering")

    feature_columns = [column for column in training.columns if column != "target_return"]
    split_at = max(90, min(int(len(training) * 0.78), len(training) - 35))
    train = training.iloc[:split_at]
    validation = training.iloc[split_at:]

    model_results = []
    latest_predictions = []
    validation_predictions = []
    weights = []

    for name, blueprint in model_blueprints(fast=fast):
        validation_model = clone(blueprint)
        validation_model.fit(train[feature_columns], train["target_return"])
        validation_pred = validation_model.predict(validation[feature_columns])
        latest_pred = fit_full_model(blueprint, training, feature_columns, features)
        mae = mean_absolute_error(validation["target_return"], validation_pred)

        weights.append(1 / (mae + 1e-6))
        latest_predictions.append(latest_pred)
        validation_predictions.append(validation_pred)
        model_results.append(build_model_metrics(name, latest_pred, validation, validation_pred, mae))

    weights_array = np.array(weights, dtype=float)
    weights_array = weights_array / weights_array.sum()
    ensemble_latest = float(np.dot(weights_array, np.array(latest_predictions)))
    ensemble_validation = sum(weight * pred for weight, pred in zip(weights_array, validation_predictions))
    agreement = float(np.mean(np.sign(latest_predictions) == np.sign(ensemble_latest)))
    dispersion = float(np.std(latest_predictions))

    return {
        "predicted_return": ensemble_latest,
        "profile": "fast" if fast else "full",
        "model_label": "Fast Gradient + Trees Ensemble" if fast else "Gradient Boosting + Random Forest Ensemble",
        "models": model_results,
        "agreement": agreement,
        "dispersion": dispersion,
        "validation": build_validation_metrics(validation, ensemble_validation),
    }


def fit_full_model(blueprint: Any, training: pd.DataFrame, columns: list[str], features: pd.DataFrame) -> float:
    full_model = clone(blueprint)
    full_model.fit(training[columns], training["target_return"])
    return float(full_model.predict(features[columns].tail(1))[0])


def build_model_metrics(
    name: str,
    latest_pred: float,
    validation: pd.DataFrame,
    validation_pred: np.ndarray,
    mae: float,
) -> dict[str, Any]:
    rmse = math.sqrt(mean_squared_error(validation["target_return"], validation_pred))
    direction_accuracy = float(np.mean(np.sign(validation_pred) == np.sign(validation["target_return"])))
    return {
        "name": name,
        "latest_return_prediction": latest_pred,
        "validation_mae_pct": mae * 100,
        "validation_rmse_pct": rmse * 100,
        "validation_direction_accuracy_pct": direction_accuracy * 100,
    }


def build_validation_metrics(validation: pd.DataFrame, prediction: np.ndarray) -> dict[str, Any]:
    mae = mean_absolute_error(validation["target_return"], prediction)
    rmse = math.sqrt(mean_squared_error(validation["target_return"], prediction))
    direction_accuracy = float(np.mean(np.sign(prediction) == np.sign(validation["target_return"])))
    return {
        "rows": len(validation),
        "mae_pct": mae * 100,
        "rmse_pct": rmse * 100,
        "direction_accuracy_pct": direction_accuracy * 100,
    }
