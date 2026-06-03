from __future__ import annotations

import math
import os
from typing import Any

os.environ.setdefault("LOKY_MAX_CPU_COUNT", "4")

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.ensemble import (
    ExtraTreesClassifier,
    ExtraTreesRegressor,
    HistGradientBoostingClassifier,
    HistGradientBoostingRegressor,
    RandomForestClassifier,
    RandomForestRegressor,
)
from sklearn.impute import SimpleImputer
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit
from sklearn.pipeline import make_pipeline


def model_blueprints(fast: bool = False) -> list[tuple[str, Any]]:
    if fast:
        return [
            (
                "Fast Gradient Boosting",
                make_pipeline(
                    SimpleImputer(strategy="median"),
                    HistGradientBoostingRegressor(
                        max_iter=95,
                        learning_rate=0.055,
                        max_leaf_nodes=21,
                        l2_regularization=0.1,
                        random_state=42,
                    ),
                ),
            ),
            (
                "Fast Extra Trees",
                make_pipeline(
                    SimpleImputer(strategy="median"),
                    ExtraTreesRegressor(
                        n_estimators=64,
                        max_depth=8,
                        min_samples_leaf=5,
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
                    max_iter=360,
                    learning_rate=0.042,
                    max_leaf_nodes=31,
                    l2_regularization=0.07,
                    random_state=42,
                ),
            ),
        ),
        (
            "Random Forest",
            make_pipeline(
                SimpleImputer(strategy="median"),
                RandomForestRegressor(
                    n_estimators=220,
                    max_depth=10,
                    min_samples_leaf=5,
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ),
        (
            "Extra Trees",
            make_pipeline(
                SimpleImputer(strategy="median"),
                ExtraTreesRegressor(
                    n_estimators=260,
                    max_depth=11,
                    min_samples_leaf=4,
                    random_state=42,
                    n_jobs=-1,
                ),
            ),
        ),
    ]


def classifier_blueprints(fast: bool = False) -> list[tuple[str, Any]]:
    if fast:
        return [
            (
                "Fast Direction Gradient Boosting",
                make_pipeline(
                    SimpleImputer(strategy="median"),
                    HistGradientBoostingClassifier(
                        max_iter=90,
                        learning_rate=0.055,
                        max_leaf_nodes=19,
                        l2_regularization=0.1,
                        random_state=7,
                    ),
                ),
            ),
            (
                "Fast Direction Extra Trees",
                make_pipeline(
                    SimpleImputer(strategy="median"),
                    ExtraTreesClassifier(
                        n_estimators=72,
                        max_depth=8,
                        min_samples_leaf=6,
                        random_state=7,
                        n_jobs=1,
                    ),
                ),
            ),
        ]

    return [
        (
            "Direction Gradient Boosting",
            make_pipeline(
                SimpleImputer(strategy="median"),
                HistGradientBoostingClassifier(
                    max_iter=300,
                    learning_rate=0.04,
                    max_leaf_nodes=27,
                    l2_regularization=0.08,
                    random_state=7,
                ),
            ),
        ),
        (
            "Direction Random Forest",
            make_pipeline(
                SimpleImputer(strategy="median"),
                RandomForestClassifier(
                    n_estimators=220,
                    max_depth=9,
                    min_samples_leaf=6,
                    random_state=7,
                    n_jobs=-1,
                ),
            ),
        ),
        (
            "Direction Extra Trees",
            make_pipeline(
                SimpleImputer(strategy="median"),
                ExtraTreesClassifier(
                    n_estimators=260,
                    max_depth=10,
                    min_samples_leaf=5,
                    random_state=7,
                    n_jobs=-1,
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
    training["target_direction"] = (training["target_return"] > 0).astype(int)
    split_at = max(90, min(int(len(training) * 0.78), len(training) - 35))
    train = training.iloc[:split_at]
    validation = training.iloc[split_at:]

    regressors = model_blueprints(fast=fast)
    classifiers = classifier_blueprints(fast=fast)
    model_results = []
    direction_model_results = []
    latest_predictions = []
    validation_predictions = []
    regression_weights = []
    latest_probabilities = []
    validation_probabilities = []
    classifier_weights = []

    for name, blueprint in regressors:
        validation_model = clone(blueprint)
        validation_model.fit(train[feature_columns], train["target_return"])
        validation_pred = validation_model.predict(validation[feature_columns])
        latest_pred = fit_full_model(blueprint, training, feature_columns, features)
        mae = mean_absolute_error(validation["target_return"], validation_pred)

        regression_weights.append(1 / (mae + 1e-6))
        latest_predictions.append(latest_pred)
        validation_predictions.append(validation_pred)
        model_results.append(build_model_metrics(name, latest_pred, validation, validation_pred, mae))

    for name, blueprint in classifiers:
        if train["target_direction"].nunique() < 2:
            fallback_probability = float(train["target_direction"].mean())
            validation_proba = np.full(len(validation), fallback_probability, dtype=float)
            latest_proba = float(training["target_direction"].mean())
        else:
            validation_model = clone(blueprint)
            validation_model.fit(train[feature_columns], train["target_direction"])
            validation_proba = probability_up(validation_model, validation[feature_columns])
            latest_proba = fit_full_classifier(blueprint, training, feature_columns, features)
        accuracy = direction_accuracy(validation["target_direction"], validation_proba)

        classifier_weights.append(max(0.01, accuracy - 0.47))
        latest_probabilities.append(latest_proba)
        validation_probabilities.append(validation_proba)
        direction_model_results.append(build_classifier_metrics(name, latest_proba, validation, validation_proba))

    regression_weight_array = normalized_weights(regression_weights)
    classifier_weight_array = normalized_weights(classifier_weights)
    regression_latest = float(np.dot(regression_weight_array, np.array(latest_predictions)))
    regression_validation = sum(weight * pred for weight, pred in zip(regression_weight_array, validation_predictions))
    probability_up_latest = float(np.dot(classifier_weight_array, np.array(latest_probabilities)))
    probability_up_validation = sum(weight * pred for weight, pred in zip(classifier_weight_array, validation_probabilities))
    ensemble_latest = apply_direction_filter(
        regression_return=regression_latest,
        probability_up=probability_up_latest,
        validation_mae=float(mean_absolute_error(validation["target_return"], regression_validation)),
    )
    agreement = float(np.mean(np.sign(latest_predictions) == np.sign(regression_latest)))
    dispersion = float(np.std(latest_predictions))
    rolling_validation = build_rolling_validation_summary(training, feature_columns, fast=fast)

    return {
        "predicted_return": ensemble_latest,
        "raw_regression_return": regression_latest,
        "direction_probability_up": probability_up_latest,
        "direction_probability_down": 1 - probability_up_latest,
        "profile": "fast" if fast else "full",
        "model_label": "Fast Accuracy Ensemble" if fast else "Accuracy Ensemble: Regression + Direction Classifier",
        "models": model_results,
        "direction_models": direction_model_results,
        "agreement": agreement,
        "dispersion": dispersion,
        "validation": build_validation_metrics(
            validation=validation,
            regression_prediction=regression_validation,
            direction_probability=probability_up_validation,
            rolling_validation=rolling_validation,
        ),
    }


def normalized_weights(weights: list[float]) -> np.ndarray:
    weights_array = np.array(weights, dtype=float)
    if not np.isfinite(weights_array).all() or weights_array.sum() <= 0:
        return np.ones(len(weights), dtype=float) / max(1, len(weights))
    return weights_array / weights_array.sum()


def apply_direction_filter(regression_return: float, probability_up: float, validation_mae: float) -> float:
    edge = probability_up - 0.5
    if abs(edge) < 0.025:
        return regression_return * 0.75

    regression_up = regression_return >= 0
    classifier_up = edge >= 0
    if regression_up != classifier_up:
        return regression_return * 0.38

    adjusted = regression_return * (1 + min(0.28, abs(edge) * 0.65))
    if abs(adjusted) < validation_mae * 0.25 and abs(edge) >= 0.12:
        adjusted += math.copysign(validation_mae * 0.25, edge)
    return adjusted


def fit_full_model(blueprint: Any, training: pd.DataFrame, columns: list[str], features: pd.DataFrame) -> float:
    full_model = clone(blueprint)
    full_model.fit(training[columns], training["target_return"])
    return float(full_model.predict(features[columns].tail(1))[0])


def fit_full_classifier(blueprint: Any, training: pd.DataFrame, columns: list[str], features: pd.DataFrame) -> float:
    if training["target_direction"].nunique() < 2:
        return float(training["target_direction"].mean())
    full_model = clone(blueprint)
    full_model.fit(training[columns], training["target_direction"])
    return float(probability_up(full_model, features[columns].tail(1))[0])


def probability_up(model: Any, frame: pd.DataFrame) -> np.ndarray:
    probability = model.predict_proba(frame)
    classes = getattr(model, "classes_", np.array([0, 1]))
    if 1 in classes:
        return probability[:, list(classes).index(1)]
    return np.zeros(len(frame), dtype=float)


def build_model_metrics(
    name: str,
    latest_pred: float,
    validation: pd.DataFrame,
    validation_pred: np.ndarray,
    mae: float,
) -> dict[str, Any]:
    rmse = math.sqrt(mean_squared_error(validation["target_return"], validation_pred))
    direction = (validation_pred >= 0).astype(int)
    direction_accuracy_value = float(np.mean(direction == validation["target_direction"]))
    return {
        "name": name,
        "latest_return_prediction": latest_pred,
        "validation_mae_pct": mae * 100,
        "validation_rmse_pct": rmse * 100,
        "validation_direction_accuracy_pct": direction_accuracy_value * 100,
    }


def build_classifier_metrics(
    name: str,
    latest_proba: float,
    validation: pd.DataFrame,
    validation_proba: np.ndarray,
) -> dict[str, Any]:
    return {
        "name": name,
        "latest_probability_up_pct": latest_proba * 100,
        "validation_direction_accuracy_pct": direction_accuracy(validation["target_direction"], validation_proba) * 100,
        "validation_high_confidence_accuracy_pct": high_confidence_accuracy(validation["target_direction"], validation_proba)["accuracy"] * 100,
        "validation_high_confidence_count": high_confidence_accuracy(validation["target_direction"], validation_proba)["count"],
    }


def direction_accuracy(actual_direction: pd.Series, probability: np.ndarray) -> float:
    predicted_direction = (probability >= 0.5).astype(int)
    return float(np.mean(predicted_direction == actual_direction.to_numpy()))


def high_confidence_accuracy(actual_direction: pd.Series, probability: np.ndarray, threshold: float = 0.58) -> dict[str, Any]:
    confidence = np.maximum(probability, 1 - probability)
    mask = confidence >= threshold
    if not mask.any():
        return {"accuracy": 0.0, "count": 0}
    predicted_direction = (probability[mask] >= 0.5).astype(int)
    actual = actual_direction.to_numpy()[mask]
    return {"accuracy": float(np.mean(predicted_direction == actual)), "count": int(mask.sum())}


def build_validation_metrics(
    validation: pd.DataFrame,
    regression_prediction: np.ndarray,
    direction_probability: np.ndarray,
    rolling_validation: dict[str, Any] | None = None,
) -> dict[str, Any]:
    mae = mean_absolute_error(validation["target_return"], regression_prediction)
    rmse = math.sqrt(mean_squared_error(validation["target_return"], regression_prediction))
    regression_direction = (regression_prediction >= 0).astype(int)
    direction_prediction = (direction_probability >= 0.5).astype(int)
    high_confidence = high_confidence_accuracy(validation["target_direction"], direction_probability)
    rolling = rolling_validation or {}
    return {
        "rows": len(validation),
        "mae_pct": mae * 100,
        "rmse_pct": rmse * 100,
        "direction_accuracy_pct": float(np.mean(regression_direction == validation["target_direction"])) * 100,
        "classifier_direction_accuracy_pct": float(np.mean(direction_prediction == validation["target_direction"])) * 100,
        "high_confidence_direction_accuracy_pct": high_confidence["accuracy"] * 100,
        "high_confidence_count": high_confidence["count"],
        "rolling_mae_pct": rolling.get("mae_pct"),
        "rolling_direction_accuracy_pct": rolling.get("direction_accuracy_pct"),
        "rolling_classifier_accuracy_pct": rolling.get("classifier_direction_accuracy_pct"),
    }


def build_rolling_validation_summary(training: pd.DataFrame, columns: list[str], fast: bool) -> dict[str, Any]:
    try:
        if fast:
            return {}
        n_splits = 2
        test_size = max(25, min(60, len(training) // (n_splits + 2)))
        splitter = TimeSeriesSplit(n_splits=n_splits, test_size=test_size)
        regressor = model_blueprints(fast=True)[0][1]
        classifier = classifier_blueprints(fast=True)[0][1]
        regression_actual = []
        regression_predicted = []
        direction_actual = []
        direction_predicted = []
        classifier_predicted = []

        for train_index, test_index in splitter.split(training):
            train = training.iloc[train_index]
            test = training.iloc[test_index]
            reg_model = clone(regressor)
            reg_model.fit(train[columns], train["target_return"])
            reg_pred = reg_model.predict(test[columns])
            if train["target_direction"].nunique() < 2:
                cls_prob = np.full(len(test), float(train["target_direction"].mean()), dtype=float)
            else:
                cls_model = clone(classifier)
                cls_model.fit(train[columns], train["target_direction"])
                cls_prob = probability_up(cls_model, test[columns])

            regression_actual.extend(test["target_return"].to_numpy())
            regression_predicted.extend(reg_pred)
            direction_actual.extend(test["target_direction"].to_numpy())
            direction_predicted.extend((reg_pred >= 0).astype(int))
            classifier_predicted.extend((cls_prob >= 0.5).astype(int))

        return {
            "mae_pct": mean_absolute_error(regression_actual, regression_predicted) * 100,
            "direction_accuracy_pct": float(np.mean(np.array(direction_predicted) == np.array(direction_actual))) * 100,
            "classifier_direction_accuracy_pct": float(np.mean(np.array(classifier_predicted) == np.array(direction_actual))) * 100,
        }
    except Exception:
        return {}
