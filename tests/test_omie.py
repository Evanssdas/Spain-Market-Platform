from pathlib import Path

from spain_power.data.omie import parse_omie_text


def test_parse_omie_file() -> None:
    text = Path("tests/fixtures/omie_sample.1").read_text(encoding="utf-8")
    frame = parse_omie_text(text)
    assert len(frame) == 4
    assert frame["period"].tolist() == [1, 2, 3, 4]
    assert frame.loc[2, "price_spain_eur_mwh"] == 94.10
    assert frame.loc[3, "price_portugal_eur_mwh"] == -2.00
    assert frame["resolution_minutes"].iloc[0] == 60
    assert str(frame["timestamp_utc"].dt.tz) == "UTC"
