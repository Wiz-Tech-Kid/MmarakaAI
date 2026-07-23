"""Feature engineering for the MmarakaAI food inflation pipeline.

Stage 1 creates lag features from the merged modeling dataset. Lag features are
strictly historical: for a row at month ``t``, ``*_lag1`` contains month
``t - 1``, ``*_lag2`` contains month ``t - 2``, and so on. The target column is
preserved but is not lagged in this first implementation.

Stage 2 creates month-over-month percentage-change features from the original
merged variables only. It never uses Stage 1 lag columns as inputs.

Stage 3 creates rolling trend and volatility features from selected economic
predictors, excluding agriculture and livestock because their month-to-month
values are annual production figures expanded to months.

Stage 4 creates deterministic calendar features from ``Date`` only.

Stage 5 creates first-difference trend features from the same non-agricultural
economic predictors used for Stage 3.

Stage 6 creates a deliberately small set of economically meaningful
interactions from selected original predictors.

The final feature matrix preserves one copy of the merged modeling dataset and
left-joins only the newly engineered columns from Stages 1 through 6.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
import logging
import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

try:
    from .config import PROJECT_ROOT
except ImportError:  # pragma: no cover - supports running this file directly.
    from config import PROJECT_ROOT


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


MERGED_MODELING_DATASET = PROJECT_ROOT / "data" / "merged" / "merged_modeling_dataset.csv"
FEATURE_DATA_DIR = PROJECT_ROOT / "data" / "features"
STAGE1_LAG_FEATURES_PATH = FEATURE_DATA_DIR / "stage1_lag_features.csv"
STAGE2_PERCENTAGE_CHANGE_FEATURES_PATH = FEATURE_DATA_DIR / "stage2_percentage_change_features.csv"
STAGE3_ROLLING_STATISTICS_PATH = FEATURE_DATA_DIR / "stage3_rolling_statistics.csv"
STAGE4_SEASONAL_FEATURES_PATH = FEATURE_DATA_DIR / "stage4_seasonal_features.csv"
STAGE5_TREND_FEATURES_PATH = FEATURE_DATA_DIR / "stage5_trend_features.csv"
STAGE6_INTERACTION_FEATURES_PATH = FEATURE_DATA_DIR / "stage6_interaction_features.csv"
FINAL_FEATURE_MATRIX_PATH = FEATURE_DATA_DIR / "mmarakai_feature_matrix.csv"

DEFAULT_DATE_COLUMN = "Date"
DEFAULT_TARGET_COLUMN = "food_price_inflation"
STAGE1_LAG_PERIODS = (1, 2, 3, 6, 12)
STAGE3_ROLLING_WINDOWS = (3, 6, 12)
SEASONAL_FEATURE_COLUMNS = ("Month", "Quarter", "Year", "Month_sin", "Month_cos")
DEFAULT_FINAL_STAGE_PATHS = (
    ("stage1", STAGE1_LAG_FEATURES_PATH),
    ("stage2", STAGE2_PERCENTAGE_CHANGE_FEATURES_PATH),
    ("stage3", STAGE3_ROLLING_STATISTICS_PATH),
    ("stage4", STAGE4_SEASONAL_FEATURES_PATH),
    ("stage5", STAGE5_TREND_FEATURES_PATH),
    ("stage6", STAGE6_INTERACTION_FEATURES_PATH),
)

GLOBAL_FOOD_COLUMNS = {
    "Global_Food_Price_Index",
    "Global_Meat_Index",
    "Global_Dairy_Index",
    "Global_Cereals_Index",
    "Global_Oils_Index",
    "Global_Sugar_Index",
}
EXCHANGE_RATE_PREFIXES = ("EUR_", "GBP_", "USD_", "SDR_", "YEN_", "ZAR_")
CPI_AND_INFLATION_COLUMNS = {
    "food_index",
    "general_index",
    "headline_cpi",
    "imported_tradeables_inflation",
    "food_inflation",
    "core_inflation",
    "Annual Inflation, Rural Village",
    "Annual Inflation, Urban Village",
    "Food_and_Non_Alcoholic_Beverages_Index",
    "Imported Tradeables Index",
    "Inflation (%)",
    "Core Monthly Inflation (Excluding Administered Prices) (percentage)",
    "Consumer Price Index (Trimmed Mean) (September 2016 = 100)",
    "Core Monthly Inflation Rate (Trimmed Mean) (percentage)",
}
IMPORT_COLUMNS = {"Imports_Food_Beverages_Tobacco", "Imports_Fuel"}
CROP_TOKENS = ("Sorghum", "Maize", "Millet", "Pulses", "Sunflower", "Groundnuts")
LIVESTOCK_COLUMNS = {"Cattle_Number", "Goats_Number", "Sheep_Number", "Chicken_Number", "Pigs_Number"}
OVERALL_CPI_COLUMN = "general_index"

TabularDataset = pd.DataFrame
FeatureMatrix = pd.DataFrame
TargetVector = pd.Series


@dataclass(frozen=True, slots=True)
class LagFeatureSummary:
    """Summary of a completed lag-feature engineering run."""

    input_path: Path
    output_path: Path
    rows: int
    original_columns: int
    final_columns: int
    target_column: str
    date_column: str
    predictor_count: int
    lag_periods: tuple[int, ...]
    lag_feature_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "rows": self.rows,
            "original_columns": self.original_columns,
            "final_columns": self.final_columns,
            "target_column": self.target_column,
            "date_column": self.date_column,
            "predictor_count": self.predictor_count,
            "lag_periods": list(self.lag_periods),
            "lag_feature_count": self.lag_feature_count,
        }


@dataclass(frozen=True, slots=True)
class PercentageChangeFeatureSummary:
    """Summary of a completed percentage-change feature run."""

    input_path: Path
    output_path: Path
    rows: int
    original_columns: int
    final_columns: int
    target_column: str
    date_column: str
    predictor_count: int
    percentage_change_feature_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "rows": self.rows,
            "original_columns": self.original_columns,
            "final_columns": self.final_columns,
            "target_column": self.target_column,
            "date_column": self.date_column,
            "predictor_count": self.predictor_count,
            "percentage_change_feature_count": self.percentage_change_feature_count,
        }


@dataclass(frozen=True, slots=True)
class RollingFeatureSummary:
    """Summary of a completed rolling-statistics feature run."""

    input_path: Path
    output_path: Path
    rows: int
    original_columns: int
    final_columns: int
    target_column: str
    date_column: str
    predictor_count: int
    windows: tuple[int, ...]
    rolling_feature_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "rows": self.rows,
            "original_columns": self.original_columns,
            "final_columns": self.final_columns,
            "target_column": self.target_column,
            "date_column": self.date_column,
            "predictor_count": self.predictor_count,
            "windows": list(self.windows),
            "rolling_feature_count": self.rolling_feature_count,
        }


@dataclass(frozen=True, slots=True)
class SeasonalFeatureSummary:
    """Summary of a completed seasonal-feature run."""

    input_path: Path
    output_path: Path
    rows: int
    original_columns: int
    final_columns: int
    date_column: str
    seasonal_feature_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "rows": self.rows,
            "original_columns": self.original_columns,
            "final_columns": self.final_columns,
            "date_column": self.date_column,
            "seasonal_feature_count": self.seasonal_feature_count,
        }


@dataclass(frozen=True, slots=True)
class TrendFeatureSummary:
    """Summary of a completed trend-feature run."""

    input_path: Path
    output_path: Path
    rows: int
    original_columns: int
    final_columns: int
    target_column: str
    date_column: str
    predictor_count: int
    trend_feature_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "rows": self.rows,
            "original_columns": self.original_columns,
            "final_columns": self.final_columns,
            "target_column": self.target_column,
            "date_column": self.date_column,
            "predictor_count": self.predictor_count,
            "trend_feature_count": self.trend_feature_count,
        }


@dataclass(frozen=True, slots=True)
class InteractionFeatureSummary:
    """Summary of a completed interaction-feature run."""

    input_path: Path
    output_path: Path
    rows: int
    original_columns: int
    final_columns: int
    target_column: str
    date_column: str
    interaction_pair_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "rows": self.rows,
            "original_columns": self.original_columns,
            "final_columns": self.final_columns,
            "target_column": self.target_column,
            "date_column": self.date_column,
            "interaction_pair_count": self.interaction_pair_count,
        }


@dataclass(frozen=True, slots=True)
class FinalFeatureMatrixSummary:
    """Summary of the assembled all-stage feature matrix."""

    input_path: Path
    output_path: Path
    rows: int
    original_columns: int
    final_columns: int
    date_column: str
    stage_feature_counts: tuple[tuple[str, int], ...]
    engineered_feature_count: int

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "rows": self.rows,
            "original_columns": self.original_columns,
            "final_columns": self.final_columns,
            "date_column": self.date_column,
            "stage_feature_counts": dict(self.stage_feature_counts),
            "engineered_feature_count": self.engineered_feature_count,
        }


def _ensure_dataframe(dataset: TabularDataset, step_name: str) -> None:
    if dataset is None or not isinstance(dataset, pd.DataFrame):
        raise ValueError(f"{step_name} requires a pandas DataFrame.")


def _normalize_column_key(column_name: str) -> str:
    text = str(column_name or "").strip().lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _is_lag_feature(column_name: str) -> bool:
    return re.search(r"_lag\d+$", str(column_name)) is not None


def _is_engineered_feature(column_name: str, all_columns: Sequence[str]) -> bool:
    column_set = set(all_columns)
    text = str(column_name)
    if _is_lag_feature(text):
        return True

    if "*x*" in text:
        return True

    pct_suffix = "_pct_change"
    if text.endswith(pct_suffix) and text[: -len(pct_suffix)] in column_set:
        return True

    window_match = re.search(r"_(?:roll|std)(?:3|6|12)$", text)
    if window_match and text[: window_match.start()] in column_set:
        return True

    trend_suffix = "_trend"
    if text.endswith(trend_suffix) and text[: -len(trend_suffix)] in column_set:
        return True

    return False


def _is_pi_column(column_name: str) -> bool:
    return re.fullmatch(r"PI\d+", str(column_name)) is not None


def resolve_column_name(dataset: pd.DataFrame, requested_column: str) -> str:
    """Resolve a human label or exact name to a real dataframe column."""

    if requested_column in dataset.columns:
        return requested_column

    requested_key = _normalize_column_key(requested_column)
    column_lookup = {_normalize_column_key(column): column for column in dataset.columns}
    if requested_key in column_lookup:
        return column_lookup[requested_key]

    raise KeyError(f"Column {requested_column!r} was not found in the dataset.")


def validate_lag_periods(lags: Sequence[int]) -> tuple[int, ...]:
    """Validate lag periods while preserving their specified order."""

    if not lags:
        raise ValueError("At least one lag period must be provided.")

    validated: list[int] = []
    seen: set[int] = set()
    for lag in lags:
        lag_int = int(lag)
        if lag_int <= 0:
            raise ValueError("Lag periods must be positive integers.")
        if lag_int in seen:
            raise ValueError(f"Duplicate lag period: {lag_int}")
        validated.append(lag_int)
        seen.add(lag_int)
    return tuple(validated)


def validate_rolling_windows(windows: Sequence[int]) -> tuple[int, ...]:
    """Validate rolling windows while preserving their specified order."""

    if not windows:
        raise ValueError("At least one rolling window must be provided.")

    validated: list[int] = []
    seen: set[int] = set()
    for window in windows:
        window_int = int(window)
        if window_int <= 1:
            raise ValueError("Rolling windows must be integers greater than 1.")
        if window_int in seen:
            raise ValueError(f"Duplicate rolling window: {window_int}")
        validated.append(window_int)
        seen.add(window_int)
    return tuple(validated)


def select_numeric_predictor_columns(
    dataset: pd.DataFrame,
    *,
    target_column: str = DEFAULT_TARGET_COLUMN,
    date_column: str = DEFAULT_DATE_COLUMN,
) -> list[str]:
    """Return numeric predictors eligible for Stage 1 lag generation."""

    _ensure_dataframe(dataset, "select_numeric_predictor_columns")
    resolved_target = resolve_column_name(dataset, target_column)
    resolved_date = resolve_column_name(dataset, date_column)
    excluded_columns = {resolved_date, resolved_target}
    return [
        column
        for column in dataset.columns
        if column not in excluded_columns and pd.api.types.is_numeric_dtype(dataset[column])
    ]


def _sort_by_date_preserving_values(dataset: pd.DataFrame, date_column: str) -> pd.DataFrame:
    sorted_dataset = dataset.copy()
    parsed_dates = pd.to_datetime(sorted_dataset[date_column], errors="coerce")
    if parsed_dates.isna().any():
        raise ValueError(f"{date_column!r} contains unparseable dates.")
    return (
        sorted_dataset.assign(__parsed_feature_date=parsed_dates)
        .sort_values("__parsed_feature_date", kind="mergesort")
        .drop(columns="__parsed_feature_date")
        .reset_index(drop=True)
    )


def select_percentage_change_predictor_columns(
    dataset: pd.DataFrame,
    *,
    target_column: str = DEFAULT_TARGET_COLUMN,
    date_column: str = DEFAULT_DATE_COLUMN,
) -> list[str]:
    """Return original numeric predictors selected for Stage 2 pct changes."""

    _ensure_dataframe(dataset, "select_percentage_change_predictor_columns")
    resolved_target = resolve_column_name(dataset, target_column)
    resolved_date = resolve_column_name(dataset, date_column)
    excluded_columns = {resolved_date, resolved_target}

    selected_columns: list[str] = []
    for column in dataset.columns:
        if column in excluded_columns or _is_engineered_feature(column, dataset.columns):
            continue
        if not pd.api.types.is_numeric_dtype(dataset[column]):
            continue

        is_selected = (
            column.startswith("BDI_")
            or "Brent" in column
            or column in GLOBAL_FOOD_COLUMNS
            or column.startswith(EXCHANGE_RATE_PREFIXES)
            or _normalize_column_key(column) == "policy_rate"
            or _is_pi_column(column)
            or column in CPI_AND_INFLATION_COLUMNS
            or column in IMPORT_COLUMNS
            or any(token in column for token in CROP_TOKENS)
            or column in LIVESTOCK_COLUMNS
        )
        if is_selected:
            selected_columns.append(column)

    return selected_columns


def select_rolling_statistic_predictor_columns(
    dataset: pd.DataFrame,
    *,
    target_column: str = DEFAULT_TARGET_COLUMN,
    date_column: str = DEFAULT_DATE_COLUMN,
) -> list[str]:
    """Return original numeric predictors selected for Stage 3 rolling stats."""

    _ensure_dataframe(dataset, "select_rolling_statistic_predictor_columns")
    resolved_target = resolve_column_name(dataset, target_column)
    resolved_date = resolve_column_name(dataset, date_column)
    excluded_columns = {resolved_date, resolved_target}

    selected_columns: list[str] = []
    for column in dataset.columns:
        if column in excluded_columns or _is_engineered_feature(column, dataset.columns):
            continue
        if not pd.api.types.is_numeric_dtype(dataset[column]):
            continue

        is_selected = (
            column.startswith("BDI_")
            or "Brent" in column
            or column in GLOBAL_FOOD_COLUMNS
            or column.startswith(EXCHANGE_RATE_PREFIXES)
            or _normalize_column_key(column) == "policy_rate"
            or _is_pi_column(column)
            or column in CPI_AND_INFLATION_COLUMNS
            or column in IMPORT_COLUMNS
        )
        if is_selected:
            selected_columns.append(column)

    return selected_columns


def select_trend_predictor_columns(
    dataset: pd.DataFrame,
    *,
    target_column: str = DEFAULT_TARGET_COLUMN,
    date_column: str = DEFAULT_DATE_COLUMN,
) -> list[str]:
    """Return original numeric predictors selected for Stage 5 trends."""

    return select_rolling_statistic_predictor_columns(
        dataset,
        target_column=target_column,
        date_column=date_column,
    )


def select_exchange_rate_columns(dataset: pd.DataFrame) -> list[str]:
    """Return original exchange-rate columns in dataset order."""

    _ensure_dataframe(dataset, "select_exchange_rate_columns")
    return [
        column
        for column in dataset.columns
        if column.startswith(EXCHANGE_RATE_PREFIXES)
        and not _is_engineered_feature(column, dataset.columns)
        and pd.api.types.is_numeric_dtype(dataset[column])
    ]


def select_producer_price_index_columns(dataset: pd.DataFrame) -> list[str]:
    """Return original PIxxxxxx columns in dataset order."""

    _ensure_dataframe(dataset, "select_producer_price_index_columns")
    return [
        column
        for column in dataset.columns
        if _is_pi_column(column)
        and not _is_engineered_feature(column, dataset.columns)
        and pd.api.types.is_numeric_dtype(dataset[column])
    ]


def select_interaction_pairs(dataset: pd.DataFrame) -> list[tuple[str, str]]:
    """Return the exact Stage 6 interaction pairs in deterministic order."""

    _ensure_dataframe(dataset, "select_interaction_pairs")
    required_columns = [
        "Global_Food_Price_Index",
        "Brent_USD_per_barrel",
        "Imports_Fuel",
        "Imports_Food_Beverages_Tobacco",
        OVERALL_CPI_COLUMN,
    ]
    missing_columns = [column for column in required_columns if column not in dataset.columns]
    if missing_columns:
        raise KeyError(f"Missing columns required for interactions: {missing_columns}")

    for column in required_columns:
        if not pd.api.types.is_numeric_dtype(dataset[column]):
            raise ValueError(f"Interaction column must be numeric: {column}")

    exchange_rate_columns = select_exchange_rate_columns(dataset)
    producer_price_columns = select_producer_price_index_columns(dataset)

    pairs: list[tuple[str, str]] = []
    pairs.extend(("Global_Food_Price_Index", column) for column in exchange_rate_columns)
    pairs.extend(("Brent_USD_per_barrel", column) for column in exchange_rate_columns)
    pairs.append(("Imports_Fuel", "Brent_USD_per_barrel"))
    pairs.append(("Imports_Food_Beverages_Tobacco", "Global_Food_Price_Index"))
    pairs.extend((column, OVERALL_CPI_COLUMN) for column in producer_price_columns)
    return pairs


def _validate_unique_dates_and_columns(
    dataset: pd.DataFrame,
    *,
    date_column: str,
    expected_rows: int,
    label: str,
) -> None:
    if len(dataset) != expected_rows:
        raise ValueError(f"{label} changed row count from {expected_rows} to {len(dataset)}.")
    if dataset[date_column].duplicated().any():
        raise ValueError(f"{label} contains duplicate {date_column!r} values.")
    duplicate_columns = dataset.columns[dataset.columns.duplicated()].tolist()
    if duplicate_columns:
        raise ValueError(f"{label} contains duplicate columns: {duplicate_columns}")


def _stage_feature_selector(stage_name: str):
    stage_key = _normalize_column_key(stage_name).replace("_", "")
    if stage_key == "stage1":
        return _is_lag_feature
    if stage_key == "stage2":
        return lambda column: str(column).endswith("_pct_change")
    if stage_key == "stage3":
        return lambda column: re.search(r"_(?:roll|std)(?:3|6|12)$", str(column)) is not None
    if stage_key == "stage4":
        return lambda column: column in SEASONAL_FEATURE_COLUMNS
    if stage_key == "stage5":
        return lambda column: str(column).endswith("_trend")
    if stage_key == "stage6":
        return lambda column: "*x*" in str(column)
    raise ValueError(f"Unsupported feature stage: {stage_name!r}")


def select_stage_engineered_feature_columns(
    stage_dataset: pd.DataFrame,
    stage_name: str,
    master_columns: Sequence[str],
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
) -> list[str]:
    """Select only newly engineered columns from one stage output."""

    _ensure_dataframe(stage_dataset, "select_stage_engineered_feature_columns")
    selector = _stage_feature_selector(stage_name)
    master_column_set = set(master_columns)
    return [
        column
        for column in stage_dataset.columns
        if column != date_column and column not in master_column_set and selector(column)
    ]


def create_mmarakai_feature_matrix(
    master_dataset: TabularDataset,
    stage_datasets: Sequence[tuple[str, TabularDataset]],
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
) -> tuple[TabularDataset, tuple[tuple[str, int], ...]]:
    """Merge all stage outputs into one modeling matrix using Date as key."""

    _ensure_dataframe(master_dataset, "create_mmarakai_feature_matrix")
    resolved_date = resolve_column_name(master_dataset, date_column)
    matrix = _sort_by_date_preserving_values(master_dataset, resolved_date)
    expected_rows = len(matrix)
    _validate_unique_dates_and_columns(
        matrix,
        date_column=resolved_date,
        expected_rows=expected_rows,
        label="master dataset",
    )

    master_columns = tuple(matrix.columns)
    stage_feature_counts: list[tuple[str, int]] = []
    for stage_name, stage_dataset in stage_datasets:
        _ensure_dataframe(stage_dataset, f"{stage_name} dataset")
        stage_date = resolve_column_name(stage_dataset, resolved_date)
        stage_frame = _sort_by_date_preserving_values(stage_dataset, stage_date)
        if stage_date != resolved_date:
            stage_frame = stage_frame.rename(columns={stage_date: resolved_date})

        _validate_unique_dates_and_columns(
            stage_frame,
            date_column=resolved_date,
            expected_rows=len(stage_frame),
            label=f"{stage_name} dataset",
        )

        feature_columns = select_stage_engineered_feature_columns(
            stage_frame,
            stage_name,
            master_columns,
            date_column=resolved_date,
        )
        duplicate_features = [column for column in feature_columns if column in matrix.columns]
        if duplicate_features:
            raise ValueError(f"{stage_name} would add duplicate columns: {duplicate_features}")

        merge_columns = [resolved_date, *feature_columns]
        matrix = matrix.merge(
            stage_frame[merge_columns],
            how="left",
            on=resolved_date,
            validate="one_to_one",
        )
        _validate_unique_dates_and_columns(
            matrix,
            date_column=resolved_date,
            expected_rows=expected_rows,
            label=f"final matrix after {stage_name}",
        )
        stage_feature_counts.append((stage_name, len(feature_columns)))

    return matrix, tuple(stage_feature_counts)


def create_lag_features(
    dataset: TabularDataset,
    target_column: str = DEFAULT_TARGET_COLUMN,
    group_columns: Sequence[str] | None = None,
    lags: Sequence[int] = STAGE1_LAG_PERIODS,
    date_column: str = DEFAULT_DATE_COLUMN,
    predictor_columns: Sequence[str] | None = None,
) -> TabularDataset:
    """Create leakage-safe monthly lag features for numeric predictors.

    The original columns are preserved, no rows are removed, and the target
    column is excluded from lag generation. Missing values created by lagging
    are intentionally left in place.
    """

    _ensure_dataframe(dataset, "create_lag_features")
    resolved_date = resolve_column_name(dataset, date_column)
    resolved_target = resolve_column_name(dataset, target_column)
    lag_periods = validate_lag_periods(lags)

    engineered = dataset.copy()
    engineered[resolved_date] = pd.to_datetime(engineered[resolved_date], errors="coerce")
    if engineered[resolved_date].isna().any():
        raise ValueError(f"{resolved_date!r} contains unparseable dates.")

    sort_columns = [resolved_date]
    if group_columns:
        missing_groups = [column for column in group_columns if column not in engineered.columns]
        if missing_groups:
            raise KeyError(f"Missing group columns: {missing_groups}")
        sort_columns = [*group_columns, resolved_date]
    engineered = engineered.sort_values(sort_columns, kind="mergesort").reset_index(drop=True)

    if predictor_columns is None:
        predictors = select_numeric_predictor_columns(
            engineered,
            target_column=resolved_target,
            date_column=resolved_date,
        )
    else:
        predictors = list(predictor_columns)
        invalid_predictors = [
            column
            for column in predictors
            if column not in engineered.columns
            or column in {resolved_date, resolved_target}
            or not pd.api.types.is_numeric_dtype(engineered[column])
        ]
        if invalid_predictors:
            raise ValueError(f"Invalid lag predictor columns: {invalid_predictors}")

    lag_frames: list[pd.DataFrame] = []
    if group_columns:
        grouped = engineered.groupby(list(group_columns), dropna=False, sort=False)
        for lag in lag_periods:
            shifted = grouped[predictors].shift(lag)
            shifted.columns = [f"{column}_lag{lag}" for column in predictors]
            lag_frames.append(shifted)
    else:
        for lag in lag_periods:
            shifted = engineered[predictors].shift(lag)
            shifted.columns = [f"{column}_lag{lag}" for column in predictors]
            lag_frames.append(shifted)

    if lag_frames:
        engineered = pd.concat([engineered, *lag_frames], axis=1)
    return engineered


def create_percentage_change_features(
    dataset: TabularDataset,
    target_column: str = DEFAULT_TARGET_COLUMN,
    date_column: str = DEFAULT_DATE_COLUMN,
    predictor_columns: Sequence[str] | None = None,
) -> TabularDataset:
    """Create one-month percentage-change features from original predictors."""

    _ensure_dataframe(dataset, "create_percentage_change_features")
    resolved_date = resolve_column_name(dataset, date_column)
    resolved_target = resolve_column_name(dataset, target_column)
    engineered = _sort_by_date_preserving_values(dataset, resolved_date)

    if predictor_columns is None:
        predictors = select_percentage_change_predictor_columns(
            engineered,
            target_column=resolved_target,
            date_column=resolved_date,
        )
    else:
        predictors = list(predictor_columns)
        invalid_predictors = [
            column
            for column in predictors
            if column not in engineered.columns
            or column in {resolved_date, resolved_target}
            or _is_lag_feature(column)
            or not pd.api.types.is_numeric_dtype(engineered[column])
        ]
        if invalid_predictors:
            raise ValueError(f"Invalid percentage-change predictor columns: {invalid_predictors}")

    pct_change_features = {}
    for column in predictors:
        feature_name = f"{column}_pct_change"
        if feature_name in engineered.columns or feature_name in pct_change_features:
            raise ValueError(f"Percentage-change feature would duplicate an existing column: {feature_name}")
        previous_values = engineered[column].shift(1)
        pct_change_features[feature_name] = (engineered[column] - previous_values) / previous_values

    if pct_change_features:
        engineered = pd.concat([engineered, pd.DataFrame(pct_change_features, index=engineered.index)], axis=1)
    return engineered


def create_rolling_statistics_features(
    dataset: TabularDataset,
    target_column: str = DEFAULT_TARGET_COLUMN,
    date_column: str = DEFAULT_DATE_COLUMN,
    predictor_columns: Sequence[str] | None = None,
    windows: Sequence[int] = STAGE3_ROLLING_WINDOWS,
) -> TabularDataset:
    """Create rolling mean and standard-deviation features from predictors."""

    _ensure_dataframe(dataset, "create_rolling_statistics_features")
    resolved_date = resolve_column_name(dataset, date_column)
    resolved_target = resolve_column_name(dataset, target_column)
    rolling_windows = validate_rolling_windows(windows)
    engineered = _sort_by_date_preserving_values(dataset, resolved_date)

    if predictor_columns is None:
        predictors = select_rolling_statistic_predictor_columns(
            engineered,
            target_column=resolved_target,
            date_column=resolved_date,
        )
    else:
        predictors = list(predictor_columns)
        invalid_predictors = [
            column
            for column in predictors
            if column not in engineered.columns
            or column in {resolved_date, resolved_target}
            or _is_engineered_feature(column, engineered.columns)
            or not pd.api.types.is_numeric_dtype(engineered[column])
        ]
        if invalid_predictors:
            raise ValueError(f"Invalid rolling-statistics predictor columns: {invalid_predictors}")

    rolling_features = {}
    for column in predictors:
        series = engineered[column]
        for window in rolling_windows:
            mean_name = f"{column}_roll{window}"
            std_name = f"{column}_std{window}"
            for feature_name in (mean_name, std_name):
                if feature_name in engineered.columns or feature_name in rolling_features:
                    raise ValueError(f"Rolling-statistics feature would duplicate an existing column: {feature_name}")
            rolling_window = series.rolling(window=window, min_periods=window)
            rolling_features[mean_name] = rolling_window.mean()
            rolling_features[std_name] = rolling_window.std()

    if rolling_features:
        engineered = pd.concat([engineered, pd.DataFrame(rolling_features, index=engineered.index)], axis=1)
    return engineered


def create_seasonal_features(
    dataset: TabularDataset,
    date_column: str = DEFAULT_DATE_COLUMN,
) -> TabularDataset:
    """Create deterministic calendar features from the Date column only."""

    _ensure_dataframe(dataset, "create_seasonal_features")
    resolved_date = resolve_column_name(dataset, date_column)
    engineered = _sort_by_date_preserving_values(dataset, resolved_date)
    parsed_dates = pd.to_datetime(engineered[resolved_date], errors="coerce")
    if parsed_dates.isna().any():
        raise ValueError(f"{resolved_date!r} contains unparseable dates.")

    seasonal_feature_names = ["Month", "Quarter", "Year", "Month_sin", "Month_cos"]
    duplicate_features = [column for column in seasonal_feature_names if column in engineered.columns]
    if duplicate_features:
        raise ValueError(f"Seasonal features already exist: {duplicate_features}")

    month = parsed_dates.dt.month
    seasonal_features = pd.DataFrame(
        {
            "Month": month.astype(int),
            "Quarter": parsed_dates.dt.quarter.astype(int),
            "Year": parsed_dates.dt.year.astype(int),
            "Month_sin": np.sin(2 * np.pi * month / 12),
            "Month_cos": np.cos(2 * np.pi * month / 12),
        },
        index=engineered.index,
    )
    return pd.concat([engineered, seasonal_features], axis=1)


def create_trend_features(
    dataset: TabularDataset,
    target_column: str = DEFAULT_TARGET_COLUMN,
    date_column: str = DEFAULT_DATE_COLUMN,
    predictor_columns: Sequence[str] | None = None,
) -> TabularDataset:
    """Create first-difference trend features from original predictors."""

    _ensure_dataframe(dataset, "create_trend_features")
    resolved_date = resolve_column_name(dataset, date_column)
    resolved_target = resolve_column_name(dataset, target_column)
    engineered = _sort_by_date_preserving_values(dataset, resolved_date)

    if predictor_columns is None:
        predictors = select_trend_predictor_columns(
            engineered,
            target_column=resolved_target,
            date_column=resolved_date,
        )
    else:
        predictors = list(predictor_columns)
        invalid_predictors = [
            column
            for column in predictors
            if column not in engineered.columns
            or column in {resolved_date, resolved_target}
            or _is_engineered_feature(column, engineered.columns)
            or not pd.api.types.is_numeric_dtype(engineered[column])
        ]
        if invalid_predictors:
            raise ValueError(f"Invalid trend predictor columns: {invalid_predictors}")

    trend_features = {}
    for column in predictors:
        feature_name = f"{column}_trend"
        if feature_name in engineered.columns or feature_name in trend_features:
            raise ValueError(f"Trend feature would duplicate an existing column: {feature_name}")
        trend_features[feature_name] = engineered[column] - engineered[column].shift(1)

    if trend_features:
        engineered = pd.concat([engineered, pd.DataFrame(trend_features, index=engineered.index)], axis=1)
    return engineered


def create_interaction_features(
    dataset: TabularDataset,
    target_column: str = DEFAULT_TARGET_COLUMN,
    date_column: str = DEFAULT_DATE_COLUMN,
    interaction_pairs: Sequence[tuple[str, str]] | None = None,
) -> TabularDataset:
    """Create the exact Stage 6 interaction features from original variables."""

    _ensure_dataframe(dataset, "create_interaction_features")
    resolved_date = resolve_column_name(dataset, date_column)
    resolved_target = resolve_column_name(dataset, target_column)
    engineered = _sort_by_date_preserving_values(dataset, resolved_date)

    pairs = list(interaction_pairs) if interaction_pairs is not None else select_interaction_pairs(engineered)
    interaction_features = {}
    for left, right in pairs:
        invalid_columns = [
            column
            for column in (left, right)
            if column not in engineered.columns
            or column in {resolved_date, resolved_target}
            or _is_engineered_feature(column, engineered.columns)
            or not pd.api.types.is_numeric_dtype(engineered[column])
        ]
        if invalid_columns:
            raise ValueError(f"Invalid interaction columns: {invalid_columns}")

        feature_name = f"{left}*x*{right}"
        if feature_name in engineered.columns or feature_name in interaction_features:
            raise ValueError(f"Interaction feature would duplicate an existing column: {feature_name}")
        interaction_features[feature_name] = engineered[left] * engineered[right]

    if interaction_features:
        engineered = pd.concat([engineered, pd.DataFrame(interaction_features, index=engineered.index)], axis=1)
    return engineered


def build_stage1_lag_dataset(
    input_path: str | Path = MERGED_MODELING_DATASET,
    output_path: str | Path = STAGE1_LAG_FEATURES_PATH,
    *,
    target_column: str = DEFAULT_TARGET_COLUMN,
    date_column: str = DEFAULT_DATE_COLUMN,
    lags: Sequence[int] = STAGE1_LAG_PERIODS,
) -> LagFeatureSummary:
    """Read the merged modeling dataset and save the Stage 1 lag dataset."""

    input_file = Path(input_path)
    output_file = Path(output_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Merged modeling dataset not found: {input_file}")

    dataset = pd.read_csv(input_file)
    resolved_target = resolve_column_name(dataset, target_column)
    resolved_date = resolve_column_name(dataset, date_column)
    predictors = select_numeric_predictor_columns(
        dataset,
        target_column=resolved_target,
        date_column=resolved_date,
    )
    lag_periods = validate_lag_periods(lags)
    engineered = create_lag_features(
        dataset,
        target_column=resolved_target,
        date_column=resolved_date,
        lags=lag_periods,
        predictor_columns=predictors,
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    engineered.to_csv(output_file, index=False)

    return LagFeatureSummary(
        input_path=input_file,
        output_path=output_file,
        rows=len(engineered),
        original_columns=len(dataset.columns),
        final_columns=len(engineered.columns),
        target_column=resolved_target,
        date_column=resolved_date,
        predictor_count=len(predictors),
        lag_periods=lag_periods,
        lag_feature_count=len(predictors) * len(lag_periods),
    )


def build_stage2_percentage_change_dataset(
    input_path: str | Path = MERGED_MODELING_DATASET,
    output_path: str | Path = STAGE2_PERCENTAGE_CHANGE_FEATURES_PATH,
    *,
    target_column: str = DEFAULT_TARGET_COLUMN,
    date_column: str = DEFAULT_DATE_COLUMN,
) -> PercentageChangeFeatureSummary:
    """Read the merged modeling dataset and save Stage 2 pct-change features."""

    input_file = Path(input_path)
    output_file = Path(output_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Merged modeling dataset not found: {input_file}")

    dataset = pd.read_csv(input_file)
    resolved_target = resolve_column_name(dataset, target_column)
    resolved_date = resolve_column_name(dataset, date_column)
    predictors = select_percentage_change_predictor_columns(
        dataset,
        target_column=resolved_target,
        date_column=resolved_date,
    )
    engineered = create_percentage_change_features(
        dataset,
        target_column=resolved_target,
        date_column=resolved_date,
        predictor_columns=predictors,
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    engineered.to_csv(output_file, index=False)

    return PercentageChangeFeatureSummary(
        input_path=input_file,
        output_path=output_file,
        rows=len(engineered),
        original_columns=len(dataset.columns),
        final_columns=len(engineered.columns),
        target_column=resolved_target,
        date_column=resolved_date,
        predictor_count=len(predictors),
        percentage_change_feature_count=len(predictors),
    )


def build_stage3_rolling_statistics_dataset(
    input_path: str | Path = MERGED_MODELING_DATASET,
    output_path: str | Path = STAGE3_ROLLING_STATISTICS_PATH,
    *,
    target_column: str = DEFAULT_TARGET_COLUMN,
    date_column: str = DEFAULT_DATE_COLUMN,
    windows: Sequence[int] = STAGE3_ROLLING_WINDOWS,
) -> RollingFeatureSummary:
    """Read the merged modeling dataset and save Stage 3 rolling stats."""

    input_file = Path(input_path)
    output_file = Path(output_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Merged modeling dataset not found: {input_file}")

    dataset = pd.read_csv(input_file)
    resolved_target = resolve_column_name(dataset, target_column)
    resolved_date = resolve_column_name(dataset, date_column)
    rolling_windows = validate_rolling_windows(windows)
    predictors = select_rolling_statistic_predictor_columns(
        dataset,
        target_column=resolved_target,
        date_column=resolved_date,
    )
    engineered = create_rolling_statistics_features(
        dataset,
        target_column=resolved_target,
        date_column=resolved_date,
        predictor_columns=predictors,
        windows=rolling_windows,
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    engineered.to_csv(output_file, index=False)

    return RollingFeatureSummary(
        input_path=input_file,
        output_path=output_file,
        rows=len(engineered),
        original_columns=len(dataset.columns),
        final_columns=len(engineered.columns),
        target_column=resolved_target,
        date_column=resolved_date,
        predictor_count=len(predictors),
        windows=rolling_windows,
        rolling_feature_count=len(predictors) * len(rolling_windows) * 2,
    )


def build_stage4_seasonal_dataset(
    input_path: str | Path = MERGED_MODELING_DATASET,
    output_path: str | Path = STAGE4_SEASONAL_FEATURES_PATH,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
) -> SeasonalFeatureSummary:
    """Read the merged modeling dataset and save Stage 4 seasonal features."""

    input_file = Path(input_path)
    output_file = Path(output_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Merged modeling dataset not found: {input_file}")

    dataset = pd.read_csv(input_file)
    resolved_date = resolve_column_name(dataset, date_column)
    engineered = create_seasonal_features(dataset, date_column=resolved_date)

    output_file.parent.mkdir(parents=True, exist_ok=True)
    engineered.to_csv(output_file, index=False)

    return SeasonalFeatureSummary(
        input_path=input_file,
        output_path=output_file,
        rows=len(engineered),
        original_columns=len(dataset.columns),
        final_columns=len(engineered.columns),
        date_column=resolved_date,
        seasonal_feature_count=5,
    )


def build_stage5_trend_dataset(
    input_path: str | Path = MERGED_MODELING_DATASET,
    output_path: str | Path = STAGE5_TREND_FEATURES_PATH,
    *,
    target_column: str = DEFAULT_TARGET_COLUMN,
    date_column: str = DEFAULT_DATE_COLUMN,
) -> TrendFeatureSummary:
    """Read the merged modeling dataset and save Stage 5 trend features."""

    input_file = Path(input_path)
    output_file = Path(output_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Merged modeling dataset not found: {input_file}")

    dataset = pd.read_csv(input_file)
    resolved_target = resolve_column_name(dataset, target_column)
    resolved_date = resolve_column_name(dataset, date_column)
    predictors = select_trend_predictor_columns(
        dataset,
        target_column=resolved_target,
        date_column=resolved_date,
    )
    engineered = create_trend_features(
        dataset,
        target_column=resolved_target,
        date_column=resolved_date,
        predictor_columns=predictors,
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    engineered.to_csv(output_file, index=False)

    return TrendFeatureSummary(
        input_path=input_file,
        output_path=output_file,
        rows=len(engineered),
        original_columns=len(dataset.columns),
        final_columns=len(engineered.columns),
        target_column=resolved_target,
        date_column=resolved_date,
        predictor_count=len(predictors),
        trend_feature_count=len(predictors),
    )


def build_stage6_interaction_dataset(
    input_path: str | Path = MERGED_MODELING_DATASET,
    output_path: str | Path = STAGE6_INTERACTION_FEATURES_PATH,
    *,
    target_column: str = DEFAULT_TARGET_COLUMN,
    date_column: str = DEFAULT_DATE_COLUMN,
) -> InteractionFeatureSummary:
    """Read the merged modeling dataset and save Stage 6 interactions."""

    input_file = Path(input_path)
    output_file = Path(output_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Merged modeling dataset not found: {input_file}")

    dataset = pd.read_csv(input_file)
    resolved_target = resolve_column_name(dataset, target_column)
    resolved_date = resolve_column_name(dataset, date_column)
    pairs = select_interaction_pairs(dataset)
    engineered = create_interaction_features(
        dataset,
        target_column=resolved_target,
        date_column=resolved_date,
        interaction_pairs=pairs,
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    engineered.to_csv(output_file, index=False)

    return InteractionFeatureSummary(
        input_path=input_file,
        output_path=output_file,
        rows=len(engineered),
        original_columns=len(dataset.columns),
        final_columns=len(engineered.columns),
        target_column=resolved_target,
        date_column=resolved_date,
        interaction_pair_count=len(pairs),
    )


def build_mmarakai_feature_matrix(
    input_path: str | Path = MERGED_MODELING_DATASET,
    stage_paths: Sequence[tuple[str, str | Path]] = DEFAULT_FINAL_STAGE_PATHS,
    output_path: str | Path = FINAL_FEATURE_MATRIX_PATH,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
) -> FinalFeatureMatrixSummary:
    """Assemble the final all-stage MmarakaAI feature matrix."""

    input_file = Path(input_path)
    output_file = Path(output_path)
    if not input_file.exists():
        raise FileNotFoundError(f"Merged modeling dataset not found: {input_file}")

    master_dataset = pd.read_csv(input_file)
    resolved_date = resolve_column_name(master_dataset, date_column)
    stage_datasets: list[tuple[str, pd.DataFrame]] = []
    for stage_name, stage_path in stage_paths:
        stage_file = Path(stage_path)
        if not stage_file.exists():
            raise FileNotFoundError(f"{stage_name} feature dataset not found: {stage_file}")
        stage_datasets.append((stage_name, pd.read_csv(stage_file)))

    matrix, stage_feature_counts = create_mmarakai_feature_matrix(
        master_dataset,
        stage_datasets,
        date_column=resolved_date,
    )

    output_file.parent.mkdir(parents=True, exist_ok=True)
    matrix.to_csv(output_file, index=False)

    engineered_feature_count = sum(count for _, count in stage_feature_counts)
    return FinalFeatureMatrixSummary(
        input_path=input_file,
        output_path=output_file,
        rows=len(matrix),
        original_columns=len(master_dataset.columns),
        final_columns=len(matrix.columns),
        date_column=resolved_date,
        stage_feature_counts=stage_feature_counts,
        engineered_feature_count=engineered_feature_count,
    )


def generate_feature_matrix(
    dataset: TabularDataset,
    target_column: str = DEFAULT_TARGET_COLUMN,
    feature_columns: Sequence[str] | None = None,
    metadata: Mapping[str, Any] | None = None,
) -> tuple[FeatureMatrix, TargetVector]:
    """Split an engineered dataset into feature matrix and target vector."""

    _ensure_dataframe(dataset, "generate_feature_matrix")
    resolved_target = resolve_column_name(dataset, target_column)
    if feature_columns is None:
        feature_columns = [
            column
            for column in dataset.columns
            if column not in {DEFAULT_DATE_COLUMN, resolved_target}
        ]
    missing_features = [column for column in feature_columns if column not in dataset.columns]
    if missing_features:
        raise KeyError(f"Missing feature columns: {missing_features}")

    logger.debug("Feature matrix metadata: %s", metadata)
    return dataset[list(feature_columns)].copy(), dataset[resolved_target].copy()


def main() -> None:
    summaries = [
        ("Stage 1 lag features", build_stage1_lag_dataset()),
        ("Stage 2 percentage-change features", build_stage2_percentage_change_dataset()),
        ("Stage 3 rolling statistics", build_stage3_rolling_statistics_dataset()),
        ("Stage 4 seasonal features", build_stage4_seasonal_dataset()),
        ("Stage 5 trend features", build_stage5_trend_dataset()),
        ("Stage 6 interaction features", build_stage6_interaction_dataset()),
        ("Final MmarakaAI feature matrix", build_mmarakai_feature_matrix()),
    ]
    for label, summary in summaries:
        logger.info("Saved %s to %s", label, summary.output_path)
        print(f"Saved {label} to: {summary.output_path}")
        print(f"Rows: {summary.rows}")
        print(f"Original columns: {summary.original_columns}")
        print(f"Final columns: {summary.final_columns}")


if __name__ == "__main__":
    main()
