from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Iterable

import pandas as pd
import requests

from spain_power.io_utils import build_session, polite_sleep, request_text, upsert_time_series


def _numeric(value: str) -> bool:
    try:
        float(value.replace(",", "."))
        return True
    except (TypeError, ValueError):
        return False


def _period_index(
    delivery_date: date,
    periods: int,
    timezone: str,
    minutes_per_period: int,
) -> pd.DatetimeIndex:
    start = pd.Timestamp(delivery_date, tz=timezone)
    end = start + pd.DateOffset(days=1)
    expected = pd.date_range(
        start=start,
        end=end,
        freq=f"{minutes_per_period}min",
        inclusive="left",
    )
    if len(expected) == periods:
        return expected

    # Defensive fallback if the provider changes its period convention.
    start_utc = start.tz_convert("UTC")
    fallback = pd.date_range(
        start=start_utc,
        periods=periods,
        freq=f"{minutes_per_period}min",
    )
    return fallback.tz_convert(timezone)


def parse_omie_text(text: str, timezone: str = "Europe/Madrid") -> pd.DataFrame:
    """Parse one OMIE marginalpdbc file.

    Expected data fields:
    year;month;day;period;price_portugal;price_spain;
    """
    rows: list[dict[str, float | int]] = []
    for raw_line in text.splitlines():
        parts = [part.strip() for part in raw_line.split(";")]
        if len(parts) < 6 or not all(_numeric(parts[index]) for index in range(6)):
            continue
        year, month, day_, period = (int(float(parts[index])) for index in range(4))
        rows.append(
            {
                "year": year,
                "month": month,
                "day": day_,
                "period": period,
                "price_portugal_eur_mwh": float(parts[4].replace(",", ".")),
                "price_spain_eur_mwh": float(parts[5].replace(",", ".")),
            }
        )

    if not rows:
        raise ValueError("No OMIE records were found in the supplied text.")

    frame = pd.DataFrame(rows).sort_values("period").reset_index(drop=True)
    delivery_dates = pd.to_datetime(frame[["year", "month", "day"]]).dt.date.unique()
    if len(delivery_dates) != 1:
        raise ValueError("Expected one delivery date per OMIE daily file.")

    periods = len(frame)
    minutes_per_period = 15 if int(frame["period"].max()) > 25 or periods > 25 else 60
    local_index = _period_index(
        delivery_dates[0],
        periods,
        timezone,
        minutes_per_period,
    )

    frame["timestamp_local"] = local_index
    frame["timestamp_utc"] = local_index.tz_convert("UTC")
    frame["delivery_date"] = pd.Timestamp(delivery_dates[0])
    frame["resolution_minutes"] = minutes_per_period
    return frame[
        [
            "delivery_date",
            "period",
            "timestamp_local",
            "timestamp_utc",
            "resolution_minutes",
            "price_spain_eur_mwh",
            "price_portugal_eur_mwh",
        ]
    ]


def download_omie_day(
    delivery_date: date,
    *,
    download_url: str,
    parent: str = "marginalpdbc",
    timezone: str = "Europe/Madrid",
    timeout_seconds: float = 30,
    retry_attempts: int = 4,
    session: requests.Session | None = None,
) -> pd.DataFrame:
    session = session or build_session(retry_attempts)
    filename = f"marginalpdbc_{delivery_date:%Y%m%d}.1"
    text = request_text(
        session,
        download_url,
        params={"parents": parent, "filename": filename},
        timeout=timeout_seconds,
    )
    return parse_omie_text(text, timezone=timezone)


def date_range(start: date, end: date) -> Iterable[date]:
    current = start
    while current <= end:
        yield current
        current += timedelta(days=1)


def collect_omie_range(
    start: date,
    end: date,
    *,
    output_path: str | Path,
    config: dict,
    timezone: str,
) -> pd.DataFrame:
    source = config["sources"]["omie"]
    session = build_session(int(source.get("retry_attempts", 4)))
    frames: list[pd.DataFrame] = []
    missing: list[str] = []

    for delivery_date in date_range(start, end):
        try:
            frames.append(
                download_omie_day(
                    delivery_date,
                    download_url=source["download_url"],
                    parent=source.get("parent", "marginalpdbc"),
                    timezone=timezone,
                    timeout_seconds=float(source.get("timeout_seconds", 30)),
                    retry_attempts=int(source.get("retry_attempts", 4)),
                    session=session,
                )
            )
        except (requests.RequestException, ValueError):
            missing.append(delivery_date.isoformat())
        polite_sleep(float(source.get("delay_seconds", 0.15)))

    if not frames:
        raise RuntimeError(
            "No OMIE files were collected. Check connectivity, dates and provider availability."
        )

    combined = pd.concat(frames, ignore_index=True)
    saved = upsert_time_series(
        output_path,
        combined,
        key_columns=["delivery_date", "period"],
    )
    if missing:
        Path(output_path).with_name("omie_missing_dates.txt").write_text(
            "\n".join(missing) + "\n",
            encoding="utf-8",
        )
    return saved
