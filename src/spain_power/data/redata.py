from __future__ import annotations

from datetime import date, timedelta
from pathlib import Path
from typing import Any, Iterable

import pandas as pd

from spain_power.io_utils import build_session, request_json, upsert_time_series


def _series_name(node: dict[str, Any], path: list[str]) -> str:
    attributes = node.get("attributes") or {}
    return str(
        attributes.get("title")
        or attributes.get("name")
        or node.get("type")
        or (path[-1] if path else "value")
    )


def _walk_jsonapi(
    node: Any,
    path: list[str] | None = None,
) -> Iterable[tuple[str, dict[str, Any]]]:
    path = path or []
    if isinstance(node, dict):
        attributes = node.get("attributes")
        current_name = _series_name(node, path)
        current_path = [*path, current_name]

        if isinstance(attributes, dict) and isinstance(attributes.get("values"), list):
            for value in attributes["values"]:
                if isinstance(value, dict):
                    yield current_name, value

        for key in ("content", "included", "children"):
            child = node.get(key)
            if child is not None:
                yield from _walk_jsonapi(child, current_path)

        if isinstance(attributes, dict):
            for key in ("content", "included", "children"):
                child = attributes.get(key)
                if child is not None:
                    yield from _walk_jsonapi(child, current_path)

        if node.get("data") is not None:
            yield from _walk_jsonapi(node["data"], current_path)

    elif isinstance(node, list):
        for item in node:
            yield from _walk_jsonapi(item, path)


def parse_redata_balance(payload: dict[str, Any]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for name, value in _walk_jsonapi(payload):
        timestamp = value.get("datetime") or value.get("datetime_utc") or value.get("date")
        numeric_value = value.get("value")
        if timestamp is None or numeric_value is None:
            continue
        rows.append(
            {
                "timestamp": pd.to_datetime(timestamp, utc=True),
                "series": name.strip(),
                "value": float(numeric_value),
            }
        )

    if not rows:
        raise ValueError("REData response contained no time-series values.")

    long = pd.DataFrame(rows)
    wide = (
        long.pivot_table(
            index="timestamp",
            columns="series",
            values="value",
            aggfunc="last",
        )
        .sort_index()
        .reset_index()
    )
    wide.columns.name = None
    return wide


def _chunks(start: date, end: date, chunk_days: int) -> Iterable[tuple[date, date]]:
    current = start
    while current <= end:
        chunk_end = min(end, current + timedelta(days=chunk_days - 1))
        yield current, chunk_end
        current = chunk_end + timedelta(days=1)


def fetch_redata_balance(start: date, end: date, *, config: dict) -> pd.DataFrame:
    source = config["sources"]["redata"]
    base = source["base_url"].rstrip("/")
    url = f"{base}/{source['category']}/{source['widget']}"
    session = build_session(int(source.get("retry_attempts", 4)))
    frames: list[pd.DataFrame] = []

    for chunk_start, chunk_end in _chunks(
        start,
        end,
        int(source.get("chunk_days", 31)),
    ):
        params = {
            "start_date": f"{chunk_start.isoformat()}T00:00",
            "end_date": f"{chunk_end.isoformat()}T23:59",
            "time_trunc": source.get("time_trunc", "day"),
            "geo_trunc": source.get("geo_trunc", "electric_system"),
            "geo_limit": source.get("geo_limit", "peninsular"),
            "geo_ids": source.get("geo_ids", 8741),
        }
        payload = request_json(
            session,
            url,
            params=params,
            timeout=float(source.get("timeout_seconds", 45)),
        )
        frames.append(parse_redata_balance(payload))

    if not frames:
        raise RuntimeError("No REData frames were returned.")
    return (
        pd.concat(frames, ignore_index=True)
        .drop_duplicates(subset=["timestamp"], keep="last")
        .sort_values("timestamp")
    )


def collect_redata_range(
    start: date,
    end: date,
    *,
    output_path: str | Path,
    config: dict,
) -> pd.DataFrame:
    frame = fetch_redata_balance(start, end, config=config)
    return upsert_time_series(output_path, frame, key_columns=["timestamp"])
