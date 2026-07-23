from __future__ import annotations

import argparse
from datetime import date, timedelta

import pandas as pd

from spain_power.config import load_config
from spain_power.grading import grade_available_forecasts
from spain_power.pipeline import (
    collect_history,
    daily_forecast,
    daily_grade,
    forecast,
    process_all,
    train,
)
from spain_power.reporting import write_grading_summary, write_risk_report


def parse_date(value: str) -> date:
    try:
        return date.fromisoformat(value)
    except ValueError as exc:
        raise argparse.ArgumentTypeError(
            "Dates must use YYYY-MM-DD."
        ) from exc


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        prog="spain-power",
        description="Spain power-market forecasting and risk platform",
    )
    parser.add_argument("--config", default="config.yaml")
    subparsers = parser.add_subparsers(dest="command", required=True)

    collect = subparsers.add_parser("collect-history")
    collect.add_argument("--start", type=parse_date, default=None)
    collect.add_argument("--end", type=parse_date, default=None)

    subparsers.add_parser("process")
    subparsers.add_parser("train")

    forecast_parser = subparsers.add_parser("forecast")
    forecast_parser.add_argument("--target-date", type=parse_date, default=None)

    subparsers.add_parser("grade")
    subparsers.add_parser("risk-report")
    subparsers.add_parser("daily-forecast")
    subparsers.add_parser("daily-grade")
    return parser


def main() -> None:
    parser = build_parser()
    args = parser.parse_args()
    config = load_config(args.config)

    if args.command == "collect-history":
        start = args.start or date.fromisoformat(
            config["project"]["data_start"]
        )
        end = args.end or date.today() - timedelta(days=1)
        collect_history(start, end, config)
        print(f"Collected and processed history from {start} to {end}.")
    elif args.command == "process":
        frame = process_all(config)
        print(f"Processed {len(frame)} daily model rows.")
    elif args.command == "train":
        bundle = train(config)
        print(f"Trained model version {bundle['model_version']}.")
    elif args.command == "forecast":
        target = args.target_date or (
            pd.Timestamp.now(
                tz=config["project"]["timezone"]
            ).date()
            + timedelta(days=1)
        )
        prediction = forecast(target, config)
        print(
            f"Forecast {prediction['forecast_id']} created for {target}: "
            f"€{prediction['forecast_peak_price_eur_mwh']:.2f}/MWh peak."
        )
    elif args.command == "grade":
        grades = grade_available_forecasts(config)
        write_grading_summary(config)
        print(f"Stored {len(grades)} graded forecasts.")
    elif args.command == "risk-report":
        path = write_risk_report(config)
        print(f"Wrote {path}.")
    elif args.command == "daily-forecast":
        prediction = daily_forecast(config)
        print(f"Daily forecast created: {prediction['forecast_id']}.")
    elif args.command == "daily-grade":
        grades = daily_grade(config)
        print(f"Daily grading complete: {len(grades)} total grades.")
    else:
        parser.error(f"Unknown command: {args.command}")


if __name__ == "__main__":
    main()
