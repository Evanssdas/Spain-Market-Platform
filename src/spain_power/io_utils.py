from __future__ import annotations

import hashlib
import json
import time
from pathlib import Path
from typing import Any

import pandas as pd
import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry


def build_session(retry_attempts: int = 4) -> requests.Session:
    retry = Retry(
        total=retry_attempts,
        connect=retry_attempts,
        read=retry_attempts,
        status=retry_attempts,
        backoff_factor=0.7,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=frozenset({"GET"}),
        raise_on_status=False,
    )
    session = requests.Session()
    adapter = HTTPAdapter(max_retries=retry)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    session.headers.update(
        {
            "User-Agent": "Spain-Power-Market-Platform/0.1",
            "Accept": "application/json",
            "Content-Type": "application/json",
        }
    )
    return session


def request_json(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = 45,
) -> dict[str, Any]:
    response = session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    payload = response.json()
    if not isinstance(payload, dict):
        raise ValueError(f"Expected a JSON object from {response.url}")
    return payload


def request_text(
    session: requests.Session,
    url: str,
    *,
    params: dict[str, Any] | None = None,
    timeout: float = 30,
) -> str:
    response = session.get(url, params=params, timeout=timeout)
    response.raise_for_status()
    return response.text


def write_table(frame: pd.DataFrame, path: str | Path) -> None:
    output = Path(path)
    output.parent.mkdir(parents=True, exist_ok=True)
    if output.suffix.lower() == ".parquet":
        frame.to_parquet(output, index=False)
    elif output.suffix.lower() == ".csv":
        frame.to_csv(output, index=False)
    else:
        raise ValueError(f"Unsupported table format: {output.suffix}")


def read_table(path: str | Path) -> pd.DataFrame:
    source = Path(path)
    if not source.exists():
        raise FileNotFoundError(source)
    if source.suffix.lower() == ".parquet":
        return pd.read_parquet(source)
    if source.suffix.lower() == ".csv":
        return pd.read_csv(source)
    raise ValueError(f"Unsupported table format: {source.suffix}")


def upsert_time_series(
    existing_path: str | Path,
    new_frame: pd.DataFrame,
    *,
    key_columns: list[str],
) -> pd.DataFrame:
    path = Path(existing_path)
    if path.exists():
        existing = read_table(path)
        combined = pd.concat([existing, new_frame], ignore_index=True)
    else:
        combined = new_frame.copy()
    combined = combined.drop_duplicates(subset=key_columns, keep="last")
    combined = combined.sort_values(key_columns).reset_index(drop=True)
    write_table(combined, path)
    return combined


def stable_row_hash(values: dict[str, Any]) -> str:
    serialised = json.dumps(values, sort_keys=True, default=str, separators=(",", ":"))
    return hashlib.sha256(serialised.encode("utf-8")).hexdigest()[:16]


def polite_sleep(seconds: float) -> None:
    if seconds > 0:
        time.sleep(seconds)
