from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any

import pandas as pd

from spain_power.data.omie import collect_omie_range
from spain_power.data.redata import collect_redata_range
from spain_power.data.weather import collect_weather_range, fetch_weather_range
from spain_power.features import (
    aggregate_omie_daily,
    aggregate_redata_daily,
    aggregate_weather_daily,
    build_model_frame,
)
from spain_power.forecasting import append_forecast, create_forecast
from spain_power.grading import grade_available_forecasts
from spain_power.io_utils import read_table, write_table
from spain_power.modeling import save_bundle, train_all_models
from spain_power.reporting import (
    write_grading_summary,
    write_latest_forecast,
    write_model_performance,
    write_risk_report,
)


def process_all(config: dict) -> pd.DataFrame:
    raw = Path(config["paths"]["raw_dir"])
    processed = Path(config["paths"]["processed_dir"])

    prices = aggregate_omie_daily(read_table(raw / "omie_prices.parquet"))
    system = aggregate_redata_daily(
        read_table(raw / "redata_balance.parquet"),
        config,
    )
    weather = aggregate_weather_daily(
        read_table(raw / "weather_historical.parquet"),
        config["project"]["timezone"],
    )
    model_frame = build_model_frame(system, prices, weather)

    write_table(prices, processed / "prices_daily.parquet")
    write_table(system, processed / "system_daily.parquet")
    write_table(weather, processed / "weather_daily.parquet")
    write_table(model_frame, processed / "model_frame.parquet")

    write_table(prices, processed / "prices_daily.csv")
    write_table(system, processed / "system_daily.csv")
    write_table(weather, processed / "weather_daily.csv")
    return model_frame


def collect_history(start: date, end: date, config: dict) -> pd.DataFrame:
    raw = Path(config["paths"]["raw_dir"])
    timezone = config["project"]["timezone"]
    collect_omie_range(
        start,
        end,
        output_path=raw / "omie_prices.parquet",
        config=config,
        timezone=timezone,
    )
    collect_redata_range(
        start,
        end,
        output_path=raw / "redata_balance.parquet",
        config=config,
    )
    collect_weather_range(
        start,
        end,
        output_path=raw / "weather_historical.parquet",
        config=config,
        historical=True,
    )
    return process_all(config)


def train(config: dict) -> dict[str, Any]:
    frame = read_table(
        Path(config["paths"]["processed_dir"]) / "model_frame.parquet"
    )
    bundle = train_all_models(frame, config)
    save_bundle(bundle, config)
    write_model_performance(bundle, config)
    return bundle


def forecast(target_date: date, config: dict) -> dict[str, Any]:
    weather = fetch_weather_range(
        target_date,
        target_date,
        config=config,
        historical=False,
    )
    prediction = create_forecast(
        target_date,
        forecast_weather=weather,
        config=config,
    )
    append_forecast(prediction, config)
    write_latest_forecast(prediction, config)
    write_risk_report(config, prediction)
    return prediction


def refresh_actuals(start: date, end: date, config: dict) -> None:
    raw = Path(config["paths"]["raw_dir"])
    collect_omie_range(
        start,
        end,
        output_path=raw / "omie_prices.parquet",
        config=config,
        timezone=config["project"]["timezone"],
    )
    collect_redata_range(
        start,
        end,
        output_path=raw / "redata_balance.parquet",
        config=config,
    )
    collect_weather_range(
        start,
        end,
        output_path=raw / "weather_historical.parquet",
        config=config,
        historical=True,
    )
    process_all(config)


def daily_forecast(config: dict) -> dict[str, Any]:
    today = pd.Timestamp.now(tz=config["project"]["timezone"]).date()
    refresh_actuals(today - timedelta(days=10), today, config)
    return forecast(today + timedelta(days=1), config)


def daily_grade(config: dict) -> pd.DataFrame:
    today = pd.Timestamp.now(tz=config["project"]["timezone"]).date()
    refresh_actuals(
        today - timedelta(days=10),
        today - timedelta(days=1),
        config,
    )
    grades = grade_available_forecasts(config)
    write_grading_summary(config)
    write_risk_report(config)
    return grades
