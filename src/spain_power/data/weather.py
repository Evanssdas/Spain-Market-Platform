from __future__ import annotations

import time
from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd
import requests

from spain_power.io_utils import build_session, upsert_time_series


API_TIMEZONE = "GMT"


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
    """Parse Open-Meteo data using an unambiguous UTC/GMT time axis."""
    hourly = payload.get("hourly")
    if not isinstance(hourly, dict) or "time" not in hourly:
        raise ValueError("Open-Meteo response does not contain hourly data.")

    timestamps = pd.to_datetime(hourly["time"], errors="raise")
    frame = pd.DataFrame({"timestamp_local": timestamps})
    for key, values in hourly.items():
        if key == "time":
            continue
        if len(values) != len(frame):
            raise ValueError(f"Open-Meteo variable length mismatch: {key}")
        frame[key] = values

    payload_timezone = str(payload.get("timezone", API_TIMEZONE))
    if frame["timestamp_local"].dt.tz is None:
        if payload_timezone.upper() in {"GMT", "UTC"}:
            frame["timestamp_local"] = frame["timestamp_local"].dt.tz_localize("UTC")
        else:
            frame["timestamp_local"] = frame["timestamp_local"].dt.tz_localize(
                payload_timezone,
                ambiguous="NaT",
                nonexistent="shift_forward",
            )
            frame = frame.loc[frame["timestamp_local"].notna()].copy()

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


def _request_payload(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any],
    timeout: float,
    attempts: int,
) -> dict[str, Any] | list[dict[str, Any]]:
    last_error: Exception | None = None
    for attempt in range(1, attempts + 1):
        try:
            response = session.get(url, params=params, timeout=timeout)
            response.raise_for_status()
            payload = response.json()
            if not isinstance(payload, (dict, list)):
                raise ValueError("Open-Meteo returned an unexpected JSON structure.")
            return payload
        except (requests.RequestException, ValueError) as exc:
            last_error = exc
            if attempt == attempts:
                break
            wait_seconds = min(30, 2 ** attempt)
            print(
                f"Open-Meteo request failed for {params['start_date']} to "
                f"{params['end_date']} (attempt {attempt}/{attempts}); "
                f"retrying in {wait_seconds}s: {exc}"
            )
            time.sleep(wait_seconds)
    raise RuntimeError(
        f"Open-Meteo failed after {attempts} attempts for "
        f"{params['start_date']} to {params['end_date']}: {last_error}"
    )


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
    retry_attempts = max(6, int(source.get("retry_attempts", 4)))
    session = build_session(retry_attempts)
    variables = ",".join(source["hourly_variables"])
    frames: list[pd.DataFrame] = []
    locations = all_locations(config)

    # Smaller historical chunks are much less likely to time out. All locations
    # are sent in one request, reducing hundreds of calls to only a few chunks.
    configured_chunk = int(source.get("chunk_days", 180))
    chunk_days = min(configured_chunk, 60) if historical else max(1, (end - start).days + 1)
    timeout = max(120.0, float(source.get("timeout_seconds", 45)))

    latitudes = ",".join(str(location["latitude"]) for location in locations)
    longitudes = ",".join(str(location["longitude"]) for location in locations)

    for chunk_start, chunk_end in _chunks(start, end, chunk_days):
        params = {
            "latitude": latitudes,
            "longitude": longitudes,
            "start_date": chunk_start.isoformat(),
            "end_date": chunk_end.isoformat(),
            "hourly": variables,
            "timezone": API_TIMEZONE,
            "wind_speed_unit": "ms",
        }
        payload = _request_payload(
            session,
            base_url,
            params=params,
            timeout=timeout,
            attempts=retry_attempts,
        )

        payloads = payload if isinstance(payload, list) else [payload]
        if len(payloads) != len(locations):
            raise ValueError(
                "Open-Meteo returned a different number of locations than requested: "
                f"requested {len(locations)}, received {len(payloads)}."
            )

        for location, location_payload in zip(locations, payloads):
            frames.append(
                parse_open_meteo_hourly(
                    location_payload,
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
