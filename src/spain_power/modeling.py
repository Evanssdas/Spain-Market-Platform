from __future__ import annotations

import json
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import joblib
import numpy as np
import pandas as pd
from lightgbm import LGBMRegressor
from sklearn.metrics import mean_absolute_error, mean_squared_error
from sklearn.model_selection import TimeSeriesSplit

from spain_power.features import base_feature_columns


@dataclass
class Evaluation:
    mae: float
    rmse: float
    persistence_mae: float
    improvement_vs_persistence_pct: float

    def as_dict(self) -> dict[str, float]:
        return {
            "mae": self.mae,
            "rmse": self.rmse,
            "persistence_mae": self.persistence_mae,
            "improvement_vs_persistence_pct": self.improvement_vs_persistence_pct,
        }


def _new_model(config: dict) -> LGBMRegressor:
    params = dict(config["models"]["lightgbm"])
    params["random_state"] = int(config["project"].get("random_seed", 42))
    params["n_jobs"] = -1
    return LGBMRegressor(**params)


def _evaluation(
    actual: pd.Series,
    predicted: np.ndarray,
    persistence: pd.Series,
) -> Evaluation:
    predicted_series = pd.Series(predicted, index=actual.index)
    mask = actual.notna() & persistence.notna() & predicted_series.notna()
    if not mask.any():
        return Evaluation(np.nan, np.nan, np.nan, np.nan)

    actual_values = actual.loc[mask].to_numpy(dtype=float)
    predicted_values = predicted_series.loc[mask].to_numpy(dtype=float)
    persistence_values = persistence.loc[mask].to_numpy(dtype=float)
    mae = float(mean_absolute_error(actual_values, predicted_values))
    rmse = float(mean_squared_error(actual_values, predicted_values) ** 0.5)
    persistence_mae = float(mean_absolute_error(actual_values, persistence_values))
    improvement = (
        100.0 * (persistence_mae - mae) / persistence_mae
        if persistence_mae > 0
        else np.nan
    )
    return Evaluation(mae, rmse, persistence_mae, float(improvement))


def _time_series_oof(
    frame: pd.DataFrame,
    features: list[str],
    target: str,
    config: dict,
) -> pd.Series:
    valid_data = frame.loc[frame[target].notna()].copy()
    output = pd.Series(index=frame.index, dtype=float)
    requested = int(config["models"].get("time_series_splits", 5))
    splits = min(requested, max(2, len(valid_data) // 60))
    if len(valid_data) < 90 or splits < 2:
        return output

    splitter = TimeSeriesSplit(n_splits=splits)
    for train_positions, validation_positions in splitter.split(valid_data):
        train_index = valid_data.index[train_positions]
        validation_index = valid_data.index[validation_positions]
        model = _new_model(config)
        model.fit(
            frame.loc[train_index, features],
            frame.loc[train_index, target],
        )
        output.loc[validation_index] = model.predict(
            frame.loc[validation_index, features]
        )
    return output


def make_price_features(
    frame: pd.DataFrame,
    component_predictions: dict[str, pd.Series | np.ndarray],
    base_features: list[str],
) -> pd.DataFrame:
    output = frame[base_features].copy()
    for component, predictions in component_predictions.items():
        if isinstance(predictions, pd.Series):
            values = predictions.reindex(frame.index).to_numpy(dtype=float)
        else:
            values = np.asarray(predictions, dtype=float)
        output[f"pred_{component}_mwh"] = values

    output["pred_variable_residual_mwh"] = (
        output["pred_demand_mwh"]
        - output["pred_wind_mwh"]
        - output["pred_solar_mwh"]
    )
    output["pred_firm_residual_mwh"] = (
        output["pred_variable_residual_mwh"] - output["pred_nuclear_mwh"]
    )
    output["pred_hydro_adjusted_residual_mwh"] = (
        output["pred_firm_residual_mwh"] - output["pred_hydro_mwh"]
    )
    return output


def train_all_models(frame: pd.DataFrame, config: dict) -> dict[str, Any]:
    frame = frame.sort_values("delivery_date").reset_index(drop=True)
    minimum_rows = int(config["models"].get("minimum_training_rows", 180))
    if len(frame) < minimum_rows:
        raise ValueError(
            f"Only {len(frame)} daily rows are available; at least {minimum_rows} are required."
        )

    features = base_feature_columns(frame)
    component_targets: dict[str, str] = config["models"]["component_targets"]
    price_target = config["models"]["price_target"]
    usable_price_indices = frame.index[frame[price_target].notna()]

    if len(usable_price_indices) < minimum_rows:
        raise ValueError("Not enough rows contain price outturns for training.")

    holdout_size = max(
        30,
        int(len(usable_price_indices) * float(config["models"]["holdout_fraction"])),
    )
    holdout_start_index = int(usable_price_indices[-holdout_size])
    train_mask = frame.index < holdout_start_index
    holdout_mask = frame.index >= holdout_start_index

    metrics: dict[str, dict[str, float]] = {}
    holdout_predictions: dict[str, pd.Series] = {}

    for component, target in component_targets.items():
        valid_train = train_mask & frame[target].notna()
        valid_holdout = holdout_mask & frame[target].notna()
        model = _new_model(config)
        model.fit(frame.loc[valid_train, features], frame.loc[valid_train, target])

        prediction = pd.Series(index=frame.index, dtype=float)
        prediction.loc[valid_holdout] = model.predict(
            frame.loc[valid_holdout, features]
        )
        holdout_predictions[component] = prediction

        holdout_index = frame.index[valid_holdout]
        metrics[component] = _evaluation(
            frame.loc[holdout_index, target],
            prediction.loc[holdout_index].to_numpy(),
            frame.loc[holdout_index, f"lag_{component}_2"],
        ).as_dict()

    # Price evaluation: train with time-series out-of-fold component forecasts.
    train_frame = frame.loc[train_mask].copy()
    train_oof: dict[str, pd.Series] = {}
    for component, target in component_targets.items():
        train_oof[component] = _time_series_oof(
            train_frame,
            features,
            target,
            config,
        )

    price_train_features = make_price_features(train_frame, train_oof, features)
    valid_price_train = (
        train_frame[price_target].notna()
        & price_train_features.notna().all(axis=1)
    )
    price_model_evaluation = _new_model(config)
    price_model_evaluation.fit(
        price_train_features.loc[valid_price_train],
        np.arcsinh(train_frame.loc[valid_price_train, price_target]),
    )

    holdout_frame = frame.loc[holdout_mask].copy()
    holdout_components = {
        component: series.loc[holdout_frame.index]
        for component, series in holdout_predictions.items()
    }
    price_holdout_features = make_price_features(
        holdout_frame,
        holdout_components,
        features,
    )
    valid_price_holdout = (
        holdout_frame[price_target].notna()
        & price_holdout_features.notna().all(axis=1)
    )
    price_prediction = pd.Series(index=holdout_frame.index, dtype=float)
    price_prediction.loc[valid_price_holdout] = np.sinh(
        price_model_evaluation.predict(
            price_holdout_features.loc[valid_price_holdout]
        )
    )
    valid_holdout_index = holdout_frame.index[valid_price_holdout]
    metrics["price_peak"] = _evaluation(
        holdout_frame.loc[valid_holdout_index, price_target],
        price_prediction.loc[valid_holdout_index].to_numpy(),
        holdout_frame.loc[valid_holdout_index, "lag_price_1"],
    ).as_dict()

    # Final models use all available history.
    final_component_models: dict[str, LGBMRegressor] = {}
    full_oof: dict[str, pd.Series] = {}
    for component, target in component_targets.items():
        valid = frame[target].notna()
        model = _new_model(config)
        model.fit(frame.loc[valid, features], frame.loc[valid, target])
        final_component_models[component] = model
        full_oof[component] = _time_series_oof(
            frame,
            features,
            target,
            config,
        )

    final_price_features = make_price_features(frame, full_oof, features)
    valid_final_price = (
        frame[price_target].notna()
        & final_price_features.notna().all(axis=1)
    )
    final_price_model = _new_model(config)
    final_price_model.fit(
        final_price_features.loc[valid_final_price],
        np.arcsinh(frame.loc[valid_final_price, price_target]),
    )

    model_version = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    return {
        "model_version": model_version,
        "trained_at_utc": datetime.now(timezone.utc).isoformat(),
        "training_start": str(pd.to_datetime(frame["delivery_date"]).min().date()),
        "training_end": str(
            pd.to_datetime(
                frame.loc[frame[price_target].notna(), "delivery_date"]
            ).max().date()
        ),
        "holdout_start": str(
            pd.to_datetime(frame.loc[holdout_start_index, "delivery_date"]).date()
        ),
        "base_features": features,
        "price_features": list(final_price_features.columns),
        "component_targets": component_targets,
        "price_target": price_target,
        "component_models": final_component_models,
        "price_model": final_price_model,
        "metrics": metrics,
    }


def save_bundle(bundle: dict[str, Any], config: dict) -> tuple[Path, Path]:
    models_dir = Path(config["paths"]["models_dir"])
    models_dir.mkdir(parents=True, exist_ok=True)
    bundle_path = models_dir / "spain_power_bundle.joblib"
    metadata_path = models_dir / "model_metadata.json"
    joblib.dump(bundle, bundle_path)

    metadata = {
        key: value
        for key, value in bundle.items()
        if key not in {"component_models", "price_model"}
    }
    metadata_path.write_text(
        json.dumps(metadata, indent=2, default=str),
        encoding="utf-8",
    )
    return bundle_path, metadata_path


def load_bundle(config: dict) -> dict[str, Any]:
    path = Path(config["paths"]["models_dir"]) / "spain_power_bundle.joblib"
    if not path.exists():
        raise FileNotFoundError(
            f"Model bundle not found at {path}. Run `python -m spain_power train`."
        )
    return joblib.load(path)
