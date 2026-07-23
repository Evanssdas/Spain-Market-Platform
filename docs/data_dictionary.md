# Data Dictionary

## OMIE period data

| Column | Meaning |
|---|---|
| `delivery_date` | Spanish market delivery date |
| `period` | OMIE period number |
| `timestamp_local` | Timezone-aware Europe/Madrid timestamp |
| `timestamp_utc` | UTC timestamp |
| `resolution_minutes` | 60 for older hourly data; 15 for current files |
| `price_spain_eur_mwh` | Spanish day-ahead price |
| `price_portugal_eur_mwh` | Portuguese day-ahead price |

## Daily system targets

| Column | Meaning |
|---|---|
| `demand_mw` | Daily maximum peninsular demand |
| `wind_mw` | Daily mean wind generation |
| `solar_mw` | Daily mean photovoltaic plus solar-thermal generation |
| `nuclear_mw` | Daily mean nuclear generation |
| `hydro_mw` | Daily mean hydro generation |

## Forecast records

Forecasts are append-only. Actual grading is stored separately.

| Column | Meaning |
|---|---|
| `forecast_id` | Stable hash of the prediction |
| `issued_at_utc` | Issue timestamp |
| `target_date` | Delivery date |
| `issue_timing` | `pre_auction` or `post_auction` |
| `model_version` | Trained bundle version |
