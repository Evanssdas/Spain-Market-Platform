from __future__ import annotations

from datetime import date, datetime, time, timezone
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from spain_power.features import aggregate_weather_daily, build_model_frame
from spain_power.io_utils import read_table, stable_row_hash
from spain_power.modeling import load_bundle, make_price_features


def prepare_forecast_frame(
    target_date: date,
    *,
    forecast_weather: pd.DataFrame,
    config: dict,
) -> pd.DataFrame:
    processed = Path(config["paths"]["processed_dir"])
    system = read_table(processed / "system_daily.parquet")
    prices = read_table(processed / "prices_daily.parquet")
    historical_weather = read_table(processed / "weather_daily.parquet")

    target_weather = aggregate_weather_daily(
        forecast_weather,
        timezone=config["project"]["timezone"],
    )
    target_timestamp = pd.Timestamp(target_date)
    target_weather = target_weather.loc[
        pd.to_datetime(target_weather["delivery_date"]) == target_timestamp
    ]
    if target_weather.empty:
        raise ValueError(f"No weather forecast was returned for {target_date}.")

    historical_weather = historical_weather.loc[
        pd.to_datetime(historical_weather["delivery_date"]) != target_timestamp
    ]
    combined_weather = pd.concat(
        [historical_weather, target_weather],
        ignore_index=True,
    )
    return build_model_frame(system, prices, combined_weather)


def classify_issue_timing(
    issue_timestamp_utc: datetime,
    target_date: date,
    config: dict,
) -> str:
    timezone_name = config["project"]["timezone"]
    local_issue = pd.Timestamp(issue_timestamp_utc).tz_convert(timezone_name)
    cutoff_hour, cutoff_minute = map(
        int,
        config["project"]["forecast_issue_cutoff_local"].split(":"),
    )
    prior_day = target_date - pd.Timedelta(days=1)
    cutoff = pd.Timestamp.combine(
        pd.Timestamp(prior_day).date(),
        time(cutoff_hour, cutoff_minute),
    ).tz_localize(timezone_name)
    return "pre_auction" if local_issue <= cutoff else "post_auction"


def create_forecast(
    target_date: date,
    *,
    forecast_weather: pd.DataFrame,
    config: dict,
) -> dict[str, Any]:
    bundle = load_bundle(config)
    frame = prepare_forecast_frame(
        target_date,
        forecast_weather=forecast_weather,
        config=config,
    )
    row = frame.loc[
        pd.to_datetime(frame["delivery_date"]).dt.date == target_date
    ]
    if len(row) != 1:
        raise ValueError(
            f"Expected one model row for {target_date}; received {len(row)}."
        )

    base = row[bundle["base_features"]]
    all_missing = [
        column
        for column in bundle["base_features"]
        if base[column].isna().all()
    ]
    if all_missing:
        raise ValueError(
            "Forecast row has unavailable features. Refresh actual history first. "
            f"Missing examples: {all_missing[:8]}"
        )

    component_predictions: dict[str, float] = {}
    for component, model in bundle["component_models"].items():
        component_predictions[component] = max(
            0.0,
            float(model.predict(base)[0]),
        )

    component_series = {
        key: pd.Series([value], index=row.index)
        for key, value in component_predictions.items()
    }
    price_features = make_price_features(
        row,
        component_series,
        bundle["base_features"],
    ).reindex(columns=bundle["price_features"])
    transformed_price = float(bundle["price_model"].predict(price_features)[0])
    price_peak = float(np.sinh(transformed_price))

    issued_at = datetime.now(timezone.utc)
    prediction: dict[str, Any] = {
        "issued_at_utc": issued_at.isoformat(),
        "target_date": target_date.isoformat(),
        "issue_timing": classify_issue_timing(
            issued_at,
            target_date,
            config,
        ),
        "model_version": bundle["model_version"],
        "forecast_demand_mwh": component_predictions["demand"],
        "forecast_wind_mwh": component_predictions["wind"],
        "forecast_solar_mwh": component_predictions["solar"],
        "forecast_nuclear_mwh": component_predictions["nuclear"],
        "forecast_hydro_mwh": component_predictions["hydro"],
        "forecast_variable_residual_mwh": (
            component_predictions["demand"]
            - component_predictions["wind"]
            - component_predictions["solar"]
        ),
        "forecast_firm_residual_mwh": (
            component_predictions["demand"]
            - component_predictions["wind"]
            - component_predictions["solar"]
            - component_predictions["nuclear"]
        ),
        "forecast_peak_price_eur_mwh": price_peak,
        "training_end": bundle["training_end"],
    }
    prediction["forecast_id"] = stable_row_hash(prediction)
    return prediction


def append_forecast(prediction: dict[str, Any], config: dict) -> Path:
    path = Path(config["paths"]["logs_dir"]) / "forecast_log.csv"
    path.parent.mkdir(parents=True, exist_ok=True)

    if path.exists():
        existing = pd.read_csv(path)
        duplicate = (
            existing["target_date"].astype(str).eq(str(prediction["target_date"]))
            & existing["model_version"].astype(str).eq(
                str(prediction["model_version"])
            )
        )
        if duplicate.any():
            return path
        combined = pd.concat(
            [existing, pd.DataFrame([prediction])],
            ignore_index=True,
        )
    else:
        combined = pd.DataFrame([prediction])

    combined.to_csv(path, index=False)
    return path
