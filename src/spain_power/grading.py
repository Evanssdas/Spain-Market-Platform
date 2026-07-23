from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd

from spain_power.io_utils import read_table


def grade_available_forecasts(config: dict) -> pd.DataFrame:
    logs_dir = Path(config["paths"]["logs_dir"])
    forecast_path = logs_dir / "forecast_log.csv"
    grades_path = logs_dir / "forecast_grades.csv"
    if not forecast_path.exists():
        return pd.DataFrame()

    forecasts = pd.read_csv(forecast_path)
    processed = Path(config["paths"]["processed_dir"])
    system = read_table(processed / "system_daily.parquet")
    prices = read_table(processed / "prices_daily.parquet")

    actuals = system.merge(prices, on="delivery_date", how="inner")
    actuals["target_date"] = (
        pd.to_datetime(actuals["delivery_date"]).dt.date.astype(str)
    )
    merged = forecasts.merge(actuals, on="target_date", how="left")
    merged = merged.loc[merged["price_peak_eur_mwh"].notna()].copy()
    if merged.empty:
        return pd.DataFrame()

    grade = pd.DataFrame(
        {
            "forecast_id": merged["forecast_id"],
            "target_date": merged["target_date"],
            "graded_at_utc": pd.Timestamp.now(tz="UTC").isoformat(),
            "actual_demand_mw": merged["demand_mw"],
            "actual_wind_mw": merged["wind_mw"],
            "actual_solar_mw": merged["solar_mw"],
            "actual_nuclear_mw": merged["nuclear_mw"],
            "actual_hydro_mw": merged["hydro_mw"],
            "actual_peak_price_eur_mwh": merged["price_peak_eur_mwh"],
            "demand_error_mw": (
                merged["forecast_demand_mw"] - merged["demand_mw"]
            ),
            "wind_error_mw": (
                merged["forecast_wind_mw"] - merged["wind_mw"]
            ),
            "solar_error_mw": (
                merged["forecast_solar_mw"] - merged["solar_mw"]
            ),
            "nuclear_error_mw": (
                merged["forecast_nuclear_mw"] - merged["nuclear_mw"]
            ),
            "hydro_error_mw": (
                merged["forecast_hydro_mw"] - merged["hydro_mw"]
            ),
            "price_error_eur_mwh": (
                merged["forecast_peak_price_eur_mwh"]
                - merged["price_peak_eur_mwh"]
            ),
            "price_absolute_error_eur_mwh": np.abs(
                merged["forecast_peak_price_eur_mwh"]
                - merged["price_peak_eur_mwh"]
            ),
        }
    )

    if grades_path.exists():
        grade = pd.concat(
            [pd.read_csv(grades_path), grade],
            ignore_index=True,
        )
    grade = (
        grade.drop_duplicates(subset=["forecast_id"], keep="last")
        .sort_values(["target_date", "forecast_id"])
        .reset_index(drop=True)
    )
    grade.to_csv(grades_path, index=False)
    return grade
