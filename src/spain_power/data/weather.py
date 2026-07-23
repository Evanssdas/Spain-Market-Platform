from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from spain_power.io_utils import build_session, request_json, upsert_time_series


def all_locations(config: dict) -> list[dict[str, Any]]:
    output: list[dict[str, Any]] = []
    for group, locations in config["weather_locations"].items():
        for location in locations:
            output.append({**location, "group": group})
    return output


def parse_open_meteo_hourly(
    payload: dict[str, Any],
    *,
    location_name: str,
    group: str,
    weight: float,
) -> pd.DataFrame:
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise ValueError("Open-Meteo response does not contain hourly data.")

    frame = pd.DataFrame({"timestamp_local": pd.to_datetime(hourly["time"])})
    for key, values in hourly.items():
        if key == "time":
            continue
        if len(values) != len(frame):
            raise ValueError(f"Open-Meteo variable length mismatch: {key}")
        frame[key] = values

    timezone = payload.get("timezone", "Europe/Madrid")
    if frame["timestamp_local"].dt.tz is None:
        frame["timestamp_local"] = frame["timestamp_local"].dt.tz_localize(
            timezone,
            ambiguous="infer",
            nonexistent="shift_forward",
        )
    frame["timestamp_utc"] = frame["timestamp_local"].dt.tz_convert("UTC")
    frame["location"] = location_name
    frame["group"] = group
    frame["weight"] = float(weight)
    return frame


def _chunks(start: date, end: date, chunk_days: int) -> Iterable[tuple[date, date]]:
    current = start
    while current <= end:
        chunk_end = min(end, current + timedelta(days=chunk_days - 1))
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def fetch_weather_range(
    start: date,
    end: date,
    *,
    config: dict,
    historical: bool,
) -> pd.DataFrame:
    source = config["sources"]["open_meteo"]
    base_url = (
        source["historical_forecast_url"]
        if historical
        else source["forecast_url"]
    )
    session = build_session(int(source.get("retry_attempts", 4)))
    variables = ",".join(source["hourly_variables"])
    frames: list[pd.DataFrame] = []
    chunk_days = (
        int(source.get("chunk_days", 180))
        if historical
        else max(1, (end - start).days + 1)
    )

    for location in all_locations(config):
        for chunk_start, chunk_end in _chunks(start, end, chunk_days):
            params = {
                "latitude": location["latitude"],
                "longitude": location["longitude"],
                "start_date": chunk_start.isoformat(),
                "end_date": chunk_end.isoformat(),
                "hourly": variables,
                "timezone": source.get("timezone", "Europe/Madrid"),
                "wind_speed_unit": "ms",
            }
            payload = request_json(
                session,
                base_url,
                params=params,
                timeout=float(source.get("timeout_seconds", 45)),
            )
            frames.append(
                parse_open_meteo_hourly(
                    payload,
                    location_name=location["name"],
                    group=location["group"],
                    weight=float(location["weight"]),
                )
            )

    if not frames:
        raise RuntimeError("No weather data were returned.")
    return (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset=["timestamp_utc", "location"], keep="last")
        .sort_values(["timestamp_utc", "location"])
    )


def collect_weather_range(
    start: date,
    end: date,
    *,
    output_path: str | Path,
    config: dict,
    historical: bool,
) -> pd.DataFrame:
    frame = fetch_weather_range(start, end, config=config, historical=historical)
    return upsert_time_series(
        output_path,
        frame,
        key_columns=["timestamp_utc", "location"],
    )
