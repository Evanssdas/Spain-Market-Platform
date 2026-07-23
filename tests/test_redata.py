import json
from pathlib import Path

from spain_power.data.redata import parse_redata_balance


def test_parse_redata_nested_jsonapi() -> None:
    payload = json.loads(
        Path("tests/fixtures/redata_sample.json").read_text(encoding="utf-8")
    )
    frame = parse_redata_balance(payload)
    assert len(frame) == 2
    assert "Wind" in frame.columns
    assert "Demand at busbars" in frame.columns
    assert frame["Demand at busbars"].max() == 26000
