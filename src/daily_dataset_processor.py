"""Daily-to-weekly-to-monthly roll-up processor for the provided processed datasets.

This module intentionally works only with the already-processed datasets that
were supplied in the workspace context. The data pipeline follows the user's
requested hierarchy:

- raw daily observations are cleaned and normalized
- daily records are aggregated into weekly summaries
- weekly summaries are then aggregated into monthly observations

The final modeling dataset therefore contains monthly observations only, with
weekly behavior preserved as an intermediate signal.
"""

from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
EXISTING_MONTHLY_INPUT = PROJECT_ROOT / "output" / "processed" / "bank-of-botswana-exchange-rates_processed.csv"
DAILY_INPUT = PROJECT_ROOT / "data" / "processed" / "01_baltic_dry_index_daily_processed.csv"

MONTHLY_COLUMNS = (
    "mean",
    "median",
    "min",
    "max",
    "range",
    "std",
    "variance",
    "first",
    "last",
    "pct_change",
    "count",
)


def _coerce_datetime_column(frame: pd.DataFrame, column: str = "Date") -> pd.DataFrame:
    """Convert the date column to a timezone-naive pandas datetime."""

    copied = frame.copy()
    if column not in copied.columns:
        raise KeyError(f"Expected '{column}' column in the dataset.")

    copied[column] = pd.to_datetime(copied[column], errors="coerce")
    copied = copied.dropna(subset=[column]).copy()
    return copied.sort_values(column).reset_index(drop=True)


def _stat_summary(series: pd.Series) -> dict[str, float | int]:
    """Return a compact weekly or monthly statistics description for one numeric series."""

    values = series.dropna()
    if values.empty:
        return {name: np.nan for name in MONTHLY_COLUMNS}

    mean_value = float(values.mean())
    median_value = float(values.median())
    min_value = float(values.min())
    max_value = float(values.max())
    range_value = float(max_value - min_value)
    std_value = float(values.std(ddof=0))
    variance_value = float(values.var(ddof=0))
    first_value = float(values.iloc[0])
    last_value = float(values.iloc[-1])
    pct_change_value = 0.0 if first_value == 0 else float((last_value - first_value) / first_value)

    return {
        "mean": mean_value,
        "median": median_value,
        "min": min_value,
        "max": max_value,
        "range": range_value,
        "std": std_value,
        "variance": variance_value,
        "first": first_value,
        "last": last_value,
        "pct_change": pct_change_value,
        "count": int(values.count()),
    }


def summarize_daily_to_weekly(dataset: pd.DataFrame, date_column: str = "Date") -> pd.DataFrame:
    """Aggregate daily observations into one weekly summary row per Monday-start week."""

    cleaned = _coerce_datetime_column(dataset, date_column)
    numeric_columns = [
        column for column in cleaned.columns if column != date_column and pd.api.types.is_numeric_dtype(cleaned[column])
    ]
    if not numeric_columns:
        raise ValueError("No numeric columns were found to summarize.")

    cleaned = cleaned.copy()
    cleaned[date_column] = pd.to_datetime(cleaned[date_column], errors="coerce")
    cleaned["week_start"] = cleaned[date_column] - pd.to_timedelta(cleaned[date_column].dt.dayofweek, unit="D")
    cleaned["week_start"] = cleaned["week_start"].dt.normalize()

    weekly_groups = cleaned.groupby("week_start", sort=True)
    weekly_rows: list[dict[str, Any]] = []

    for week_start, frame in weekly_groups:
        row: dict[str, Any] = {date_column: week_start}
        for column in numeric_columns:
            stats = _stat_summary(frame[column])
            for suffix, value in stats.items():
                row[f"{column}_{suffix}"] = value
        weekly_rows.append(row)

    if not weekly_rows:
        return pd.DataFrame(columns=[date_column])

    weekly_summary = pd.DataFrame(weekly_rows).sort_values(date_column).reset_index(drop=True)
    return weekly_summary


def summarize_weekly_to_monthly(weekly_dataset: pd.DataFrame, date_column: str = "Date") -> pd.DataFrame:
    """Aggregate weekly summary rows into one monthly row per month.

    This function intentionally uses the weekly summary dataset as its source of
    truth, rather than the original daily observations.
    """

    cleaned = _coerce_datetime_column(weekly_dataset, date_column)
    metric_columns = [
        column for column in cleaned.columns if column != date_column and pd.api.types.is_numeric_dtype(cleaned[column])
    ]
    if not metric_columns:
        raise ValueError("No weekly summary columns were found to aggregate.")

    month_groups = cleaned.groupby(cleaned[date_column].dt.to_period("M"), sort=True)
    monthly_rows: list[dict[str, Any]] = []

    metric_prefixes = sorted({column.rsplit("_", 1)[0] for column in metric_columns})

    for month_period, frame in month_groups:
        row: dict[str, Any] = {date_column: month_period.to_timestamp()}
        for prefix in metric_prefixes:
            series_map: dict[str, pd.Series] = {}
            for metric in MONTHLY_COLUMNS:
                column_name = f"{prefix}_{metric}"
                if column_name in frame.columns:
                    series_map[metric] = frame[column_name]

            if not series_map:
                continue

            for metric, series in series_map.items():
                if metric in {"mean", "median", "range", "std", "variance", "pct_change"}:
                    row[f"{prefix}_{metric}"] = float(series.mean())
                elif metric == "count":
                    row[f"{prefix}_{metric}"] = int(series.sum())
                elif metric == "min":
                    row[f"{prefix}_{metric}"] = float(series.min())
                elif metric == "max":
                    row[f"{prefix}_{metric}"] = float(series.max())
                elif metric == "first":
                    row[f"{prefix}_{metric}"] = float(series.iloc[0])
                elif metric == "last":
                    row[f"{prefix}_{metric}"] = float(series.iloc[-1])

        monthly_rows.append(row)

    if not monthly_rows:
        return pd.DataFrame(columns=[date_column])

    monthly_summary = pd.DataFrame(monthly_rows).sort_values(date_column).reset_index(drop=True)
    return monthly_summary


def summarize_daily_to_monthly(dataset: pd.DataFrame, date_column: str = "Date") -> pd.DataFrame:
    """Aggregate the daily dataset into a monthly table via the weekly intermediate layer."""

    weekly_summary = summarize_daily_to_weekly(dataset, date_column=date_column)
    return summarize_weekly_to_monthly(weekly_summary, date_column=date_column)


def normalize_existing_monthly_dataset(dataset: pd.DataFrame, date_column: str = "Date") -> pd.DataFrame:
    """Ensure the supplied monthly exchange-rate dataset has a clean schema."""

    cleaned = _coerce_datetime_column(dataset, date_column)
    numeric_columns = [
        column for column in cleaned.columns if column != date_column and pd.api.types.is_numeric_dtype(cleaned[column])
    ]
    if not numeric_columns:
        raise ValueError("The monthly dataset does not contain numeric summary columns.")

    cleaned = cleaned.drop_duplicates(subset=[date_column]).sort_values(date_column).reset_index(drop=True)
    return cleaned


def process_and_write_outputs(
    daily_input_path: Path = DAILY_INPUT,
    monthly_input_path: Path = EXISTING_MONTHLY_INPUT,
    output_dir: Path = DATA_PROCESSED_DIR,
) -> dict[str, Path]:
    """Run the dedicated weekly-first processing workflow and write the final outputs."""

    output_dir.mkdir(parents=True, exist_ok=True)

    daily_frame = pd.read_csv(daily_input_path)
    weekly_summary = summarize_daily_to_weekly(daily_frame)
    weekly_output_path = output_dir / "01_baltic_dry_index_weekly_processed.csv"
    weekly_summary.to_csv(weekly_output_path, index=False)

    monthly_summary = summarize_weekly_to_monthly(weekly_summary)
    monthly_output_path = output_dir / "01_baltic_dry_index_monthly_processed.csv"
    monthly_summary.to_csv(monthly_output_path, index=False)

    monthly_frame = pd.read_csv(monthly_input_path)
    normalized_monthly = normalize_existing_monthly_dataset(monthly_frame)
    monthly_exchange_output_path = output_dir / "bank-of-botswana-exchange-rates_processed.csv"
    normalized_monthly.to_csv(monthly_exchange_output_path, index=False)

    return {
        "weekly_summary": weekly_output_path,
        "monthly_summary": monthly_output_path,
        "monthly_exchange_rates": monthly_exchange_output_path,
    }


def main() -> None:
    """Convenience entrypoint for the daily dataset fix-up workflow."""

    outputs = process_and_write_outputs()
    for label, path in outputs.items():
        frame = pd.read_csv(path)
        print(f"{label}: {path} | rows={len(frame)} | columns={len(frame.columns)}")


if __name__ == "__main__":
    main()
