# Spain Power Market Platform

A reproducible, component-based forecasting and risk platform for the Spanish electricity market.

The model follows the same broad logic as the France platform:

1. Forecast demand, wind, solar, nuclear and hydro.
2. Build residual-demand features.
3. Predict the next-day Spanish day-ahead peak price with LightGBM.
4. Use an `arcsinh` price transform so negative prices remain possible.
5. Log forecasts before delivery and grade them against OMIE and Red Eléctrica outturns.
6. Produce model-performance and illustrative risk reports.

## Official data sources

- **OMIE**: Spanish and Portuguese day-ahead market prices.
- **Red Eléctrica REData API**: peninsular demand, generation and cross-border balance.
- **Open-Meteo**: historical forecasts for training and live forecasts for next-day operation.

## Important modelling position

This is a reduced-form market model, not a plant-by-plant dispatch stack. Predicted residual demand represents system tightness. Hydro remains a separate price feature because reservoir hydro is partly dispatchable.

The first price target is the **next-day maximum Spanish day-ahead price**. The collector retains the complete period-level OMIE series so the project can later be expanded to all quarter-hourly prices.

## Quick start

Create and activate a Python environment, then run:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
pip install -e .
pytest
```

Collect history:

```bash
python -m spain_power collect-history --start 2023-01-01 --end 2026-07-22
```

Train:

```bash
python -m spain_power train
```

Forecast a target day:

```bash
python -m spain_power forecast --target-date 2026-07-24
```

Grade forecasts:

```bash
python -m spain_power grade
```

## Generated outputs

```text
data/raw/omie_prices.parquet
data/raw/redata_balance.parquet
data/raw/weather_historical.parquet
data/processed/prices_daily.parquet
data/processed/system_daily.parquet
data/processed/weather_daily.parquet
data/processed/model_frame.parquet
models/spain_power_bundle.joblib
models/model_metadata.json
logs/forecast_log.csv
logs/forecast_grades.csv
reports/latest_forecast.md
reports/model_performance.md
reports/risk_report.md
```

## Forecast architecture

The component models use:

- Multi-location temperature, wind and radiation forecasts
- Heating and cooling degree days
- Spanish calendar variables
- One-day and seven-day lags
- Rolling statistics
- Accumulated precipitation for hydro

The price model receives time-series out-of-fold component forecasts, residual demand, price lags, recent volatility and weather/calendar features.

The price target is transformed with:

```python
transformed_price = np.arcsinh(price)
price = np.sinh(transformed_prediction)
```

## Leakage control

The price model is trained on out-of-fold component predictions rather than same-day actual generation. Evaluation uses a chronological holdout and persistence benchmarks.

## Forecast-vintage limitation

The V1 historical weather collector uses Open-Meteo's Historical Forecast API. This is a stitched operational-forecast series, not a perfect reconstruction of one fixed day-ahead issue time. A stricter research version should use Previous Runs or Single Runs and preserve exact forecast vintages.

## GitHub Actions

- `ci.yml` runs tests.
- `daily_forecast.yml` creates tomorrow's forecast.
- `daily_grade.yml` refreshes actuals and grades eligible forecasts.

Run the historical collection and training locally before enabling the scheduled workflows. Commit the generated model and compact processed tables so GitHub Actions has a bootstrapped state.

## Interview description

> I built a Spain power-market platform that forecasts demand, wind, solar, nuclear and hydro, converts those forecasts into residual-demand features and predicts the next-day Spanish peak price using a two-stage LightGBM framework. I used an arcsinh target transformation because Iberian prices can be negative. The platform logs forecasts before delivery, grades them against OMIE and Red Eléctrica outturns and produces an illustrative VaR and stress report.

## Licence

MIT. Provider data remain subject to their original terms and attribution requirements.
