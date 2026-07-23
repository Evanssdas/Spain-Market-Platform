from __future__ import annotations

from typing import Iterable

try:
    import holidays
except ModuleNotFoundError:  # Allows lightweight parsing/tests before dependencies are installed.
    holidays = None

import numpy as np
import pandas as pd


def _find_column(columns: Iterable[str], aliases: list[str]) -> str | None:
    normalised = {str(column).strip().casefold(): column for column in columns}
    for alias in aliases:
        match = normalised.get(alias.strip().casefold())
        if match is not None:
            return str(match)
    return None


def aggregate_omie_daily(prices: pd.DataFrame) -> pd.DataFrame:
    frame = prices.copy()
    frame["delivery_date"] = pd.to_datetime(frame["delivery_date"]).dt.normalize()
    daily = (
        frame.groupby("delivery_date", as_index=False)
        .agg(
            price_peak_eur_mwh=("price_spain_eur_mwh", "max"),
            price_average_eur_mwh=("price_spain_eur_mwh", "mean"),
            price_minimum_eur_mwh=("price_spain_eur_mwh", "min"),
            portugal_peak_eur_mwh=("price_portugal_eur_mwh", "max"),
            periods=("period", "count"),
        )
    )
    negative = (
        frame.assign(is_negative=frame["price_spain_eur_mwh"] < 0)
        .groupby("delivery_date", as_index=False)["is_negative"]
        .sum()
        .rename(columns={"is_negative": "negative_price_periods"})
    )
    daily = daily.merge(negative, on="delivery_date", how="left")
    daily["spain_portugal_peak_spread"] = (
        daily["price_peak_eur_mwh"] - daily["portugal_peak_eur_mwh"]
    )
    return daily


def aggregate_redata_daily(balance: pd.DataFrame, config: dict) -> pd.DataFrame:
    frame = balance.copy()
    frame["timestamp"] = pd.to_datetime(frame["timestamp"], utc=True)
    timezone = config["project"]["timezone"]
    frame["delivery_date"] = (
        frame["timestamp"]
        .dt.tz_convert(timezone)
        .dt.tz_localize(None)
        .dt.normalize()
    )

    aliases = config["columns"]["redata_aliases"]
    selected = {
        canonical: _find_column(frame.columns, alias_list)
        for canonical, alias_list in aliases.items()
    }
    output = pd.DataFrame({"delivery_date": sorted(frame["delivery_date"].unique())})

    for canonical, source_column in selected.items():
        if source_column is None:
            output[canonical] = np.nan
            continue
        grouped = frame.groupby("delivery_date")[source_column]
        values = grouped.max() if canonical == "demand_mw" else grouped.mean()
        output = output.merge(values.rename(canonical), on="delivery_date", how="left")

    output["solar_mw"] = output[["solar_pv_mw", "solar_thermal_mw"]].sum(
        axis=1,
        min_count=1,
    )
    return output


def _weighted_group_daily(group_frame: pd.DataFrame, group: str) -> pd.DataFrame:
    frame = group_frame.copy()
    weights = (
        frame[["location", "weight"]]
        .drop_duplicates()
        .set_index("location")["weight"]
    )
    weights = weights / weights.sum()

    daily_location = (
        frame.groupby(["delivery_date", "location"], as_index=False)
        .agg(
            temperature_mean=("temperature_2m", "mean"),
            temperature_max=("temperature_2m", "max"),
            temperature_min=("temperature_2m", "min"),
            cloud_mean=("cloud_cover", "mean"),
            precipitation_sum=("precipitation", "sum"),
            shortwave_sum=("shortwave_radiation", "sum"),
            dni_sum=("direct_normal_irradiance", "sum"),
            wind_mean=("wind_speed_100m", "mean"),
            wind_max=("wind_speed_100m", "max"),
            wind_cubed_mean=(
                "wind_speed_100m",
                lambda series: float(np.nanmean(np.power(series, 3))),
            ),
        )
    )
    daily_location["weight"] = daily_location["location"].map(weights)

    feature_names = [
        "temperature_mean",
        "temperature_max",
        "temperature_min",
        "cloud_mean",
        "precipitation_sum",
        "shortwave_sum",
        "dni_sum",
        "wind_mean",
        "wind_max",
        "wind_cubed_mean",
    ]
    for feature in feature_names:
        daily_location[f"weighted_{feature}"] = (
            daily_location[feature] * daily_location["weight"]
        )

    weighted = (
        daily_location.groupby("delivery_date")[
            [f"weighted_{feature}" for feature in feature_names]
        ]
        .sum(min_count=1)
        .reset_index()
        .rename(
            columns={
                f"weighted_{feature}": f"wx_{group}_{feature}"
                for feature in feature_names
            }
        )
    )

    if group == "wind":
        dispersion = (
            daily_location.groupby("delivery_date")["wind_mean"]
            .std()
            .rename("wx_wind_site_dispersion")
            .reset_index()
        )
        weighted = weighted.merge(dispersion, on="delivery_date", how="left")
    return weighted


def aggregate_weather_daily(weather: pd.DataFrame, timezone: str) -> pd.DataFrame:
    frame = weather.copy()
    frame["timestamp_local"] = pd.to_datetime(
        frame["timestamp_local"],
        utc=True,
    ).dt.tz_convert(timezone)
    frame["delivery_date"] = (
        frame["timestamp_local"].dt.tz_localize(None).dt.normalize()
    )

    grouped = [
        _weighted_group_daily(subset, str(group))
        for group, subset in frame.groupby("group")
    ]
    if not grouped:
        raise ValueError("No weather groups were available.")

    output = grouped[0]
    for group_frame in grouped[1:]:
        output = output.merge(group_frame, on="delivery_date", how="outer")

    if "wx_demand_temperature_mean" in output:
        output["wx_demand_hdd"] = np.maximum(
            18.0 - output["wx_demand_temperature_mean"],
            0,
        )
        output["wx_demand_cdd"] = np.maximum(
            output["wx_demand_temperature_mean"] - 22.0,
            0,
        )

    if "wx_hydro_precipitation_sum" in output:
        output = output.sort_values("delivery_date")
        output["wx_hydro_precip_roll7"] = (
            output["wx_hydro_precipitation_sum"]
            .rolling(7, min_periods=1)
            .sum()
        )
        output["wx_hydro_precip_roll30"] = (
            output["wx_hydro_precipitation_sum"]
            .rolling(30, min_periods=1)
            .sum()
        )
    return output.sort_values("delivery_date").reset_index(drop=True)


def add_calendar_features(frame: pd.DataFrame) -> pd.DataFrame:
    output = frame.copy()
    dates = pd.to_datetime(output["delivery_date"])
    if holidays is not None:
        spanish_holidays = holidays.Spain(
            years=sorted(dates.dt.year.dropna().unique().tolist())
        )
    else:
        spanish_holidays = set()
    output["cal_day_of_week"] = dates.dt.dayofweek
    output["cal_month"] = dates.dt.month
    output["cal_day_of_year"] = dates.dt.dayofyear
    output["cal_is_weekend"] = (dates.dt.dayofweek >= 5).astype(int)
    output["cal_is_holiday"] = dates.dt.date.map(
        lambda value: int(value in spanish_holidays)
    )
    output["cal_sin_day_of_year"] = np.sin(
        2 * np.pi * output["cal_day_of_year"] / 365.25
    )
    output["cal_cos_day_of_year"] = np.cos(
        2 * np.pi * output["cal_day_of_year"] / 365.25
    )
    return output


def build_model_frame(
    system_daily: pd.DataFrame,
    prices_daily: pd.DataFrame,
    weather_daily: pd.DataFrame,
) -> pd.DataFrame:
    frame = weather_daily.merge(system_daily, on="delivery_date", how="outer")
    frame = frame.merge(prices_daily, on="delivery_date", how="outer")
    frame = frame.sort_values("delivery_date").reset_index(drop=True)
    frame = add_calendar_features(frame)

    targets = {
        "demand": "demand_mw",
        "wind": "wind_mw",
        "solar": "solar_mw",
        "nuclear": "nuclear_mw",
        "hydro": "hydro_mw",
        "price": "price_peak_eur_mwh",
    }
    for name, source in targets.items():
        if source not in frame.columns:
            frame[source] = np.nan
        frame[f"target_{source}"] = frame[source]
        frame[f"lag_{name}_1"] = frame[source].shift(1)
        frame[f"lag_{name}_2"] = frame[source].shift(2)
        frame[f"lag_{name}_7"] = frame[source].shift(7)
        frame[f"roll_{name}_7"] = (
            frame[source].shift(1).rolling(7, min_periods=3).mean()
        )
        frame[f"roll_{name}_28"] = (
            frame[source].shift(1).rolling(28, min_periods=7).mean()
        )

    frame["roll_price_change_vol30"] = (
        frame["price_peak_eur_mwh"]
        .diff()
        .shift(1)
        .rolling(30, min_periods=10)
        .std()
    )
    spread = (
        frame["spain_portugal_peak_spread"]
        if "spain_portugal_peak_spread" in frame
        else pd.Series(index=frame.index, dtype=float)
    )
    frame["lag_spain_portugal_spread_1"] = spread.shift(1)
    return frame


def base_feature_columns(frame: pd.DataFrame) -> list[str]:
    prefixes = ("wx_", "cal_", "lag_", "roll_")
    return [
        column
        for column in frame.columns
        if column.startswith(prefixes)
        and pd.api.types.is_numeric_dtype(frame[column])
    ]
