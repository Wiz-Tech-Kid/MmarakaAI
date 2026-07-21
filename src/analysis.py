"""Objective raw-data audit report generator for VenturePulse.

This module inspects the CSV files in ``data/raw`` and writes reproducible
Markdown reports plus supporting figures under ``output/analysis``. It only
reads input datasets and writes audit artifacts.
"""

from __future__ import annotations

from collections.abc import Mapping, Sequence
from dataclasses import dataclass
from itertools import combinations
import json
import logging
import os
from pathlib import Path
import tempfile
from typing import Any
import warnings

os.environ.setdefault("MPLCONFIGDIR", str(Path(tempfile.gettempdir()) / "venturepulse_matplotlib"))

import matplotlib

matplotlib.use("Agg")

import matplotlib.pyplot as plt
import numpy as np
import pandas as pd

try:
    from .config import OUTPUT_DIR, RAW_DATA_DIR
except ImportError:  # pragma: no cover - supports running this file directly.
    from config import OUTPUT_DIR, RAW_DATA_DIR


ANALYSIS_DIR = OUTPUT_DIR / "analysis"
REPORT_DIR = ANALYSIS_DIR / "reports"
FIGURE_DIR = ANALYSIS_DIR / "figures"
METADATA_DIR = ANALYSIS_DIR / "metadata"

DATE_PARSE_THRESHOLD = 0.75
IDENTIFIER_RATIO_THRESHOLD = 0.95
NEAR_CONSTANT_DOMINANCE_THRESHOLD = 0.95
PREVIEW_ROWS = 5
TOP_N = 10

DATE_COLUMN_CANDIDATES = ("Date", "date", "DATE", "Datetime", "datetime", "Timestamp", "timestamp")
GROUPED_MISSING_IDENTIFIERS = (
    "REF_AREA",
    "REF_AREA_LABEL",
    "Country",
    "country",
    "Item",
    "Item Code",
    "INDICATOR",
    "INDICATOR_LABEL",
    "Indicator",
    "indicator",
    "Year",
    "year",
)
MIXED_DTYPE_TAGS = {
    "mixed",
    "mixed-integer",
    "mixed-integer-float",
    "mixed-integer-na",
    "mixed-string",
}
MEASURE_NAME_PATTERNS = (
    "value",
    "price",
    "rate",
    "close",
    "high",
    "low",
    "index",
    "usd",
    "barrel",
)
LONG_FORMAT_IDENTIFIER_TOKENS = (
    "ref_area",
    "ref_area_label",
    "country",
    "region",
    "indicator",
    "indicator_label",
    "item",
    "item code",
    "item_code",
)
JOIN_KEY_IDENTIFIER_TOKENS = (
    "ref_area",
    "country",
    "region",
    "indicator",
    "item",
    "item code",
    "item_code",
    "code",
)

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


@dataclass(frozen=True, slots=True)
class ColumnGroups:
    """Column groups detected directly from loaded dataframe dtypes and values."""

    numeric: list[str]
    categorical: list[str]
    datetime: list[str]
    object_date: list[str]


@dataclass(frozen=True, slots=True)
class FigurePaths:
    """Generated figure paths for one dataset audit."""

    missing: Path | None = None
    correlation: Path | None = None
    histogram: Path | None = None
    boxplot: Path | None = None
    time_series: Path | None = None


def ensure_output_directories() -> None:
    """Create report, figure, and metadata output directories."""

    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    FIGURE_DIR.mkdir(parents=True, exist_ok=True)
    METADATA_DIR.mkdir(parents=True, exist_ok=True)


def load_dataset(path: Path) -> pd.DataFrame:
    """Load a CSV dataset without writing back to the source path."""

    logger.info("Loading raw dataset: %s", path)
    return pd.read_csv(path, low_memory=False)


def format_bytes(value: int) -> str:
    """Format bytes as a compact human-readable string."""

    if value < 1024:
        return f"{value} B"
    if value < 1024**2:
        return f"{value / 1024:.2f} KB"
    if value < 1024**3:
        return f"{value / 1024**2:.2f} MB"
    return f"{value / 1024**3:.2f} GB"


def dataframe_memory_usage(df: pd.DataFrame) -> int:
    """Return total dataframe memory usage in bytes, including the index."""

    return int(df.memory_usage(index=True, deep=True).sum())


def safe_percentage(numerator: int | float, denominator: int | float) -> float:
    """Return a rounded percentage, or 0.0 when the denominator is zero."""

    if denominator == 0:
        return 0.0
    return round(float(numerator) / float(denominator) * 100, 2)


def parse_datetime_series(series: pd.Series) -> pd.Series:
    """Parse a series to datetimes while preserving invalid entries as NaT."""

    if pd.api.types.is_datetime64_any_dtype(series):
        return pd.to_datetime(series, errors="coerce")

    with warnings.catch_warnings():
        warnings.simplefilter("ignore", category=UserWarning)
        return pd.to_datetime(series, errors="coerce")


def datetime_parse_ratio(series: pd.Series) -> float:
    """Return the share of non-null values that can be parsed as datetimes."""

    non_missing = int(series.notna().sum())
    if non_missing == 0:
        return 0.0

    parsed = parse_datetime_series(series)
    return float(parsed.notna().sum() / non_missing)


def detect_datetime_columns(df: pd.DataFrame) -> list[str]:
    """Detect datetime columns from dtype or parseable object/string values."""

    datetime_columns: list[str] = []
    for column in df.columns:
        series = df[column]
        if pd.api.types.is_datetime64_any_dtype(series):
            datetime_columns.append(column)
            continue

        is_text_like = (
            pd.api.types.is_object_dtype(series)
            or pd.api.types.is_string_dtype(series)
            or isinstance(series.dtype, pd.CategoricalDtype)
        )
        if is_text_like and datetime_parse_ratio(series) >= DATE_PARSE_THRESHOLD:
            datetime_columns.append(column)

    return datetime_columns


def detect_object_date_columns(df: pd.DataFrame) -> list[str]:
    """Return object/string columns whose non-null values are date-like."""

    object_date_columns: list[str] = []
    for column in df.columns:
        series = df[column]
        is_text_like = (
            pd.api.types.is_object_dtype(series)
            or pd.api.types.is_string_dtype(series)
            or isinstance(series.dtype, pd.CategoricalDtype)
        )
        if is_text_like and datetime_parse_ratio(series) >= DATE_PARSE_THRESHOLD:
            object_date_columns.append(column)
    return object_date_columns


def identify_column_groups(df: pd.DataFrame) -> ColumnGroups:
    """Classify columns using measured dtypes and date parseability."""

    datetime_columns = detect_datetime_columns(df)
    object_date_columns = detect_object_date_columns(df)
    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    categorical_columns = [
        column
        for column in df.columns
        if column not in datetime_columns
        and (
            pd.api.types.is_object_dtype(df[column])
            or pd.api.types.is_string_dtype(df[column])
            or isinstance(df[column].dtype, pd.CategoricalDtype)
            or pd.api.types.is_bool_dtype(df[column])
        )
    ]

    return ColumnGroups(
        numeric=numeric_columns,
        categorical=categorical_columns,
        datetime=datetime_columns,
        object_date=object_date_columns,
    )


def first_non_missing_value(series: pd.Series) -> Any:
    """Return the first non-missing value from a series, or an empty string."""

    non_missing = series.dropna()
    if non_missing.empty:
        return ""
    return non_missing.iloc[0]


def format_number(value: Any) -> str:
    """Format numeric values without adding subjective labels."""

    if value is None:
        return ""
    if isinstance(value, (np.integer, int)) and not isinstance(value, bool):
        return str(int(value))
    if isinstance(value, (np.floating, float)):
        if np.isnan(value):
            return "NaN"
        if np.isposinf(value):
            return "Infinity"
        if np.isneginf(value):
            return "-Infinity"
        return f"{float(value):.6g}"
    return str(value)


def format_value(value: Any) -> str:
    """Format scalar values for Markdown table cells."""

    if value is None:
        return ""
    if isinstance(value, pd.Timestamp):
        if pd.isna(value):
            return "NaT"
        if (
            value.hour == 0
            and value.minute == 0
            and value.second == 0
            and value.microsecond == 0
            and value.nanosecond == 0
        ):
            return value.date().isoformat()
        return value.isoformat()
    if isinstance(value, pd.Timedelta):
        if pd.isna(value):
            return "NaT"
        return str(value)
    if isinstance(value, (np.integer, int, np.floating, float)) and not isinstance(value, bool):
        return format_number(value)
    if isinstance(value, (list, tuple, set)):
        return ", ".join(format_value(item) for item in value)
    if isinstance(value, Mapping):
        return ", ".join(f"{format_value(key)}: {format_value(item)}" for key, item in value.items())

    try:
        if pd.isna(value):
            return ""
    except (TypeError, ValueError):
        pass

    return str(value)


def markdown_cell(value: Any) -> str:
    """Escape a value for use in a Markdown table cell."""

    text = format_value(value)
    text = text.replace("\\", "\\\\")
    text = text.replace("|", "\\|")
    text = text.replace("\n", "<br>")
    return text


def markdown_table(records: Sequence[Mapping[str, Any]], columns: Sequence[tuple[str, str]]) -> str:
    """Render records as a Markdown table with stable column ordering."""

    headers = [label for _, label in columns]
    keys = [key for key, _ in columns]
    lines = [
        "| " + " | ".join(headers) + " |",
        "| " + " | ".join("---" for _ in headers) + " |",
    ]

    for record in records:
        lines.append("| " + " | ".join(markdown_cell(record.get(key, "")) for key in keys) + " |")

    return "\n".join(lines)


def dataframe_to_markdown(df: pd.DataFrame) -> str:
    """Render a dataframe preview as Markdown without requiring mutation."""

    if df.empty:
        return "No records."

    records = [{column: row[column] for column in df.columns} for _, row in df.iterrows()]
    columns = [(str(column), str(column)) for column in df.columns]
    return markdown_table(records, columns)


def format_list(values: Sequence[Any]) -> str:
    """Format a sequence for compact report output."""

    if not values:
        return "None"
    return ", ".join(format_value(value) for value in values)


def normalize_dates(series: pd.Series) -> pd.Series:
    """Return parsed dates normalized to midnight for period calculations."""

    return parse_datetime_series(series).dt.normalize()


def select_primary_datetime_column(datetime_columns: Sequence[str]) -> str | None:
    """Select a primary date column using exact common names first."""

    for candidate in DATE_COLUMN_CANDIDATES:
        if candidate in datetime_columns:
            return candidate
    return datetime_columns[0] if datetime_columns else None


def column_profile(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Build per-column structural profile records."""

    row_count = len(df)
    profile: list[dict[str, Any]] = []
    for column in df.columns:
        series = df[column]
        missing_count = int(series.isna().sum())
        profile.append(
            {
                "column": column,
                "data_type": str(series.dtype),
                "memory_usage": format_bytes(int(series.memory_usage(index=False, deep=True))),
                "missing_count": missing_count,
                "missing_percent": safe_percentage(missing_count, row_count),
                "unique_values": int(series.nunique(dropna=False)),
                "example_value": first_non_missing_value(series),
            }
        )
    return profile


def infer_mixed_type_columns(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Detect object columns containing more than one non-null Python type."""

    results: list[dict[str, Any]] = []
    for column in df.columns:
        series = df[column]
        if not pd.api.types.is_object_dtype(series):
            continue

        non_missing = series.dropna()
        inferred_tag = pd.api.types.infer_dtype(non_missing, skipna=True)
        python_types = sorted({type(value).__name__ for value in non_missing})
        if inferred_tag in MIXED_DTYPE_TAGS or len(python_types) > 1:
            results.append(
                {
                    "column": column,
                    "inferred_dtype": inferred_tag,
                    "python_types": ", ".join(python_types),
                }
            )
    return results


def dominant_value_details(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Return dominant-value measurements for every column."""

    details: list[dict[str, Any]] = []
    row_count = len(df)
    for column in df.columns:
        counts = df[column].value_counts(dropna=False)
        if counts.empty:
            details.append(
                {
                    "column": column,
                    "dominant_value": "",
                    "dominant_count": 0,
                    "dominant_percent": 0.0,
                    "unique_values": 0,
                }
            )
            continue

        dominant_value = counts.index[0]
        dominant_count = int(counts.iloc[0])
        details.append(
            {
                "column": column,
                "dominant_value": dominant_value,
                "dominant_count": dominant_count,
                "dominant_percent": safe_percentage(dominant_count, row_count),
                "unique_values": int(df[column].nunique(dropna=False)),
            }
        )
    return details


def constant_columns(dominance: Sequence[Mapping[str, Any]]) -> list[str]:
    """Return columns with one observed value, counting null as a value."""

    return [str(row["column"]) for row in dominance if int(row["unique_values"]) <= 1]


def near_constant_columns(dominance: Sequence[Mapping[str, Any]]) -> list[dict[str, Any]]:
    """Return columns where one value reaches the configured dominance threshold."""

    return [
        dict(row)
        for row in dominance
        if int(row["unique_values"]) > 1
        and float(row["dominant_percent"]) >= NEAR_CONSTANT_DOMINANCE_THRESHOLD * 100
    ]


def potential_identifier_columns(
    df: pd.DataFrame,
    datetime_columns: Sequence[str],
) -> list[dict[str, Any]]:
    """Detect high-cardinality non-float columns using a fixed ratio threshold."""

    identifiers: list[dict[str, Any]] = []
    row_count = len(df)
    if row_count == 0:
        return identifiers

    for column in df.columns:
        if column in datetime_columns or pd.api.types.is_float_dtype(df[column]):
            continue
        unique_values = int(df[column].nunique(dropna=False))
        unique_ratio = unique_values / row_count
        if unique_values > 1 and unique_ratio >= IDENTIFIER_RATIO_THRESHOLD:
            identifiers.append(
                {
                    "column": column,
                    "unique_values": unique_values,
                    "unique_percent": round(unique_ratio * 100, 2),
                }
            )
    return identifiers


def numeric_frame(df: pd.DataFrame, numeric_columns: Sequence[str]) -> pd.DataFrame:
    """Return selected numeric columns coerced to numeric values."""

    if not numeric_columns:
        return pd.DataFrame(index=df.index)
    return df.loc[:, list(numeric_columns)].apply(pd.to_numeric, errors="coerce")


def count_infinite_values(df: pd.DataFrame, numeric_columns: Sequence[str]) -> tuple[int, dict[str, int]]:
    """Count positive and negative infinity values in numeric columns."""

    values = numeric_frame(df, numeric_columns)
    by_column: dict[str, int] = {}
    for column in values.columns:
        by_column[column] = int(np.isinf(values[column].to_numpy(dtype=float, na_value=np.nan)).sum())
    return int(sum(by_column.values())), by_column


def signed_value_counts(df: pd.DataFrame, numeric_columns: Sequence[str]) -> dict[str, Any]:
    """Count zero, negative, and positive values in numeric columns."""

    values = numeric_frame(df, numeric_columns)
    records: list[dict[str, Any]] = []
    for column in values.columns:
        finite = values[column].replace([np.inf, -np.inf], np.nan)
        records.append(
            {
                "column": column,
                "zero_count": int((finite == 0).sum()),
                "negative_count": int((finite < 0).sum()),
                "positive_count": int((finite > 0).sum()),
            }
        )

    return {
        "records": records,
        "zero_total": int(sum(record["zero_count"] for record in records)),
        "negative_total": int(sum(record["negative_count"] for record in records)),
        "positive_total": int(sum(record["positive_count"] for record in records)),
    }


def is_long_format_dataset(df: pd.DataFrame) -> bool:
    """Return True for long/panel-like datasets with repeated dates and a value column."""

    if df.empty:
        return False

    date_column = next((column for column in DATE_COLUMN_CANDIDATES if column in df.columns), None)
    if date_column is None:
        return False

    value_column = next((column for column in df.columns if str(column).lower() == "value"), None)
    if value_column is None:
        return False

    identifier_columns = [
        column
        for column in df.columns
        if any(str(column).lower() == token or str(column).lower().startswith(f"{token} ") for token in LONG_FORMAT_IDENTIFIER_TOKENS)
    ]
    if not identifier_columns:
        return False

    parsed_dates = parse_datetime_series(df[date_column]).dropna()
    if parsed_dates.empty:
        return False

    date_counts = parsed_dates.value_counts()
    return bool((date_counts > 1).any())


def duplicate_dates_by_column(df: pd.DataFrame, datetime_columns: Sequence[str]) -> list[dict[str, Any]]:
    """Measure duplicate date values for each detected datetime column."""

    long_format = is_long_format_dataset(df)
    records: list[dict[str, Any]] = []
    for column in datetime_columns:
        parsed = parse_datetime_series(df[column]).dropna()
        if long_format:
            records.append(
                {
                    "column": column,
                    "expected_repeated_dates": True,
                    "duplicate_date_rows": 0,
                    "duplicate_date_values": 0,
                    "status": "Expected (Long/Panel Structure)",
                    "first_duplicated_dates": "None",
                }
            )
            continue

        duplicate_mask = parsed.duplicated(keep=False)
        duplicated_dates = parsed.loc[duplicate_mask]
        records.append(
            {
                "column": column,
                "expected_repeated_dates": False,
                "duplicate_date_rows": int(parsed.duplicated().sum()),
                "duplicate_date_values": int(duplicated_dates.nunique(dropna=True)),
                "status": "Detected" if int(parsed.duplicated().sum()) > 0 else "No duplicates",
                "first_duplicated_dates": format_list(
                    [value.date().isoformat() for value in duplicated_dates.drop_duplicates().head(TOP_N)]
                ),
            }
        )
    return records


def data_quality_metrics(df: pd.DataFrame, column_groups: ColumnGroups) -> dict[str, Any]:
    """Compute objective data-quality measurements."""

    row_count = len(df)
    column_count = len(df.columns)
    total_cells = row_count * column_count
    total_missing = int(df.isna().sum().sum())
    dominance = dominant_value_details(df)
    constant = constant_columns(dominance)
    near_constant = near_constant_columns(dominance)
    mixed_columns = infer_mixed_type_columns(df)
    identifiers = potential_identifier_columns(df, column_groups.datetime)
    infinite_total, infinite_by_column = count_infinite_values(df, column_groups.numeric)
    signed_counts = signed_value_counts(df, column_groups.numeric)
    duplicate_date_records = duplicate_dates_by_column(df, column_groups.datetime)

    return {
        "total_missing": total_missing,
        "missing_percent": safe_percentage(total_missing, total_cells),
        "missing_by_column": df.isna().sum().astype(int).to_dict(),
        "missing_percent_by_column": {
            column: safe_percentage(int(df[column].isna().sum()), row_count) for column in df.columns
        },
        "duplicate_rows": int(df.duplicated().sum()),
        "duplicate_dates": duplicate_date_records,
        "duplicate_dates_total": int(sum(row["duplicate_date_rows"] for row in duplicate_date_records)),
        "infinite_values": infinite_total,
        "infinite_values_by_column": infinite_by_column,
        "zero_values": signed_counts["zero_total"],
        "negative_values": signed_counts["negative_total"],
        "positive_values": signed_counts["positive_total"],
        "signed_value_counts": signed_counts["records"],
        "constant_columns": constant,
        "near_constant_columns": near_constant,
        "potential_identifier_columns": identifiers,
        "mixed_data_type_columns": mixed_columns,
        "object_columns_containing_dates": column_groups.object_date,
        "dominant_value_details": dominance,
    }


def derived_year_series(df: pd.DataFrame, datetime_columns: Sequence[str]) -> pd.Series | None:
    """Return an observed or derived year series when available."""

    if "Year" in df.columns:
        return df["Year"]
    if "year" in df.columns:
        return df["year"]

    primary_date = select_primary_datetime_column(datetime_columns)
    if primary_date is None:
        return None
    return parse_datetime_series(df[primary_date]).dt.year


def missing_group_table(
    df: pd.DataFrame,
    group_values: pd.Series,
    group_name: str,
) -> list[dict[str, Any]]:
    """Group rows with missing cells by a provided identifier series."""

    missing_row_mask = df.isna().any(axis=1)
    missing_cells = df.isna().sum(axis=1)
    grouped_frame = pd.DataFrame(
        {
            group_name: group_values,
            "missing_cells": missing_cells,
            "has_missing": missing_row_mask,
        }
    )
    grouped_frame = grouped_frame[grouped_frame["has_missing"]]
    if grouped_frame.empty:
        return []

    grouped = (
        grouped_frame.groupby(group_name, dropna=False)
        .agg(missing_rows=("has_missing", "size"), missing_cells=("missing_cells", "sum"))
        .reset_index()
        .sort_values(["missing_cells", "missing_rows"], ascending=False)
        .head(TOP_N)
    )
    return grouped.to_dict(orient="records")


def missing_value_analysis(df: pd.DataFrame, datetime_columns: Sequence[str]) -> dict[str, Any]:
    """Measure missing values by column, row, and relevant identifiers."""

    row_count = len(df)
    missing_row_mask = df.isna().any(axis=1)
    missing_rows = df.loc[missing_row_mask]
    missing_by_column = [
        {
            "column": column,
            "missing_count": int(df[column].isna().sum()),
            "missing_percent": safe_percentage(int(df[column].isna().sum()), row_count),
        }
        for column in df.columns
    ]

    grouped: dict[str, list[dict[str, Any]]] = {}
    for identifier in GROUPED_MISSING_IDENTIFIERS:
        if identifier in df.columns and identifier not in grouped:
            table = missing_group_table(df, df[identifier], identifier)
            if table:
                grouped[identifier] = table

    year_series = derived_year_series(df, datetime_columns)
    if year_series is not None and "Year" not in grouped:
        table = missing_group_table(df, year_series, "Year")
        if table:
            grouped["Year"] = table

    return {
        "missing_by_column": missing_by_column,
        "missing_rows_count": int(missing_rows.shape[0]),
        "missing_rows_percent": safe_percentage(int(missing_rows.shape[0]), row_count),
        "missing_rows_preview": missing_rows.head(TOP_N),
        "grouped_missing": grouped,
    }


def duplicate_analysis(df: pd.DataFrame, datetime_columns: Sequence[str]) -> dict[str, Any]:
    """Measure duplicate rows and duplicate datetime values."""

    duplicates = df[df.duplicated(keep=False)]
    return {
        "duplicate_row_count": int(df.duplicated().sum()),
        "duplicate_records_preview": duplicates.head(TOP_N),
        "duplicate_dates": duplicate_dates_by_column(df, datetime_columns),
    }


def iqr_outlier_count(series: pd.Series) -> tuple[int, float]:
    """Return outlier count and IQR for finite numeric values."""

    finite = pd.to_numeric(series, errors="coerce").replace([np.inf, -np.inf], np.nan).dropna()
    if finite.empty:
        return 0, np.nan

    q1 = float(finite.quantile(0.25))
    q3 = float(finite.quantile(0.75))
    iqr = q3 - q1
    lower = q1 - 1.5 * iqr
    upper = q3 + 1.5 * iqr
    return int(((finite < lower) | (finite > upper)).sum()), iqr


def numeric_statistics(df: pd.DataFrame, numeric_columns: Sequence[str]) -> list[dict[str, Any]]:
    """Compute requested descriptive statistics for every numeric column."""

    records: list[dict[str, Any]] = []
    for column in numeric_columns:
        numeric = pd.to_numeric(df[column], errors="coerce")
        infinite_count = int(np.isinf(numeric.to_numpy(dtype=float, na_value=np.nan)).sum())
        finite = numeric.replace([np.inf, -np.inf], np.nan).dropna()
        mode = finite.mode(dropna=True)
        outlier_count, iqr = iqr_outlier_count(numeric)
        mean = float(finite.mean()) if not finite.empty else np.nan
        std_dev = float(finite.std(ddof=1)) if len(finite) > 1 else np.nan

        records.append(
            {
                "column": column,
                "count": int(finite.count()),
                "mean": mean,
                "median": float(finite.median()) if not finite.empty else np.nan,
                "mode": mode.iloc[0] if not mode.empty else np.nan,
                "minimum": float(finite.min()) if not finite.empty else np.nan,
                "maximum": float(finite.max()) if not finite.empty else np.nan,
                "range": float(finite.max() - finite.min()) if not finite.empty else np.nan,
                "variance": float(finite.var(ddof=1)) if len(finite) > 1 else np.nan,
                "standard_deviation": std_dev,
                "coefficient_of_variation": float(std_dev / mean)
                if len(finite) > 1 and mean != 0 and not np.isnan(mean)
                else np.nan,
                "iqr": iqr,
                "skewness": float(finite.skew()) if len(finite) > 2 else np.nan,
                "kurtosis": float(finite.kurtosis()) if len(finite) > 3 else np.nan,
                "zero_count": int((finite == 0).sum()),
                "negative_count": int((finite < 0).sum()),
                "positive_count": int((finite > 0).sum()),
                "outlier_count_iqr": outlier_count,
                "infinite_count": infinite_count,
            }
        )
    return records


def categorical_statistics(df: pd.DataFrame, categorical_columns: Sequence[str]) -> dict[str, Any]:
    """Compute cardinality and top-value frequencies for categorical columns."""

    results: dict[str, Any] = {}
    for column in categorical_columns:
        series = df[column].astype(object)
        value_counts = series.value_counts(dropna=False)
        top_values = [
            {
                "value": value,
                "frequency": int(count),
                "frequency_percent": safe_percentage(int(count), len(series)),
            }
            for value, count in value_counts.head(TOP_N).items()
        ]
        results[column] = {
            "unique_values": int(series.nunique(dropna=False)),
            "top_values": top_values,
        }
    return results


def spacing_metrics(dates: pd.Series) -> dict[str, Any]:
    """Measure median and most common spacing between unique sorted dates."""

    cleaned = dates.dropna().drop_duplicates().sort_values()
    diffs = cleaned.diff().dropna()
    if diffs.empty:
        return {"median_spacing": pd.NaT, "most_common_spacing": pd.NaT}

    mode = diffs.mode(dropna=True)
    return {
        "median_spacing": diffs.median(),
        "most_common_spacing": mode.iloc[0] if not mode.empty else pd.NaT,
    }


def monthly_continuity(dates: pd.Series) -> dict[str, Any]:
    """Measure continuity over observed monthly periods."""

    valid_dates = dates.dropna()
    if valid_dates.empty:
        return {
            "monthly_applicable": False,
            "unique_months": 0,
            "expected_months": 0,
            "missing_months": 0,
            "duplicate_months": 0,
            "monthly_continuity_percent": 0.0,
            "first_missing_months": "None",
        }

    periods = valid_dates.dt.to_period("M")
    unique_periods = periods.drop_duplicates().sort_values()
    if unique_periods.empty:
        expected = pd.PeriodIndex([], freq="M")
    else:
        expected = pd.period_range(unique_periods.iloc[0], unique_periods.iloc[-1], freq="M")
    missing = expected.difference(pd.PeriodIndex(unique_periods, freq="M"))
    applicable = int(valid_dates.dt.day.nunique(dropna=True)) == 1 and len(unique_periods) >= 2

    return {
        "monthly_applicable": bool(applicable),
        "unique_months": int(len(unique_periods)),
        "expected_months": int(len(expected)),
        "missing_months": int(len(missing)),
        "duplicate_months": int(periods.duplicated().sum()),
        "monthly_continuity_percent": safe_percentage(len(unique_periods), len(expected)),
        "first_missing_months": format_list([str(period) for period in missing[:TOP_N]]),
    }


def business_day_continuity(dates: pd.Series) -> dict[str, Any]:
    """Measure continuity against a Monday-to-Friday business-day calendar."""

    normalized = dates.dropna().dt.normalize()
    if normalized.empty:
        return {
            "business_day_applicable": False,
            "observed_business_days": 0,
            "expected_business_days": 0,
            "missing_business_days": 0,
            "business_day_continuity_percent": 0.0,
            "weekend_records": 0,
            "first_missing_business_days": "None",
        }

    weekend_records = int((normalized.dt.weekday >= 5).sum())
    unique_observed = pd.DatetimeIndex(normalized.drop_duplicates().sort_values())
    expected = pd.bdate_range(unique_observed.min(), unique_observed.max())
    observed_business = pd.DatetimeIndex([value for value in unique_observed if value.weekday() < 5])
    missing = expected.difference(observed_business)
    applicable = weekend_records == 0 and len(unique_observed) >= 2

    return {
        "business_day_applicable": bool(applicable),
        "observed_business_days": int(len(observed_business)),
        "expected_business_days": int(len(expected)),
        "missing_business_days": int(len(missing)),
        "business_day_continuity_percent": safe_percentage(len(observed_business), len(expected)),
        "weekend_records": weekend_records,
        "first_missing_business_days": format_list([value.date().isoformat() for value in missing[:TOP_N]]),
    }


def infer_regular_frequency(dates: pd.Series) -> str:
    """Estimate a frequency label from the observed unique datetime values."""

    unique_dates = dates.dropna().drop_duplicates().sort_values()
    if len(unique_dates) < 2:
        return "Insufficient dates"

    try:
        inferred = pd.infer_freq(pd.DatetimeIndex(unique_dates))
    except ValueError:
        inferred = None
    if inferred:
        return inferred

    monthly = monthly_continuity(unique_dates)
    if monthly["monthly_applicable"] and monthly["monthly_continuity_percent"] >= 90:
        return "Monthly-like"

    business = business_day_continuity(unique_dates)
    if business["business_day_applicable"] and business["business_day_continuity_percent"] >= 85:
        return "Business-day-like"

    expected_daily = pd.date_range(unique_dates.iloc[0], unique_dates.iloc[-1], freq="D")
    daily_coverage = safe_percentage(len(unique_dates), len(expected_daily))
    if daily_coverage >= 95:
        return "Daily-like"

    return "Irregular"


def datetime_analysis(df: pd.DataFrame, datetime_columns: Sequence[str]) -> list[dict[str, Any]]:
    """Measure date range, ordering, spacing, and duplicate date values."""

    records: list[dict[str, Any]] = []
    for column in datetime_columns:
        parsed = parse_datetime_series(df[column])
        valid = parsed.dropna()
        unique_sorted = valid.drop_duplicates().sort_values()
        spacing = spacing_metrics(valid)
        duplicate_dates = int(valid.duplicated().sum())
        chronological = bool(valid.is_monotonic_increasing)

        records.append(
            {
                "column": column,
                "earliest_date": unique_sorted.iloc[0] if not unique_sorted.empty else pd.NaT,
                "latest_date": unique_sorted.iloc[-1] if not unique_sorted.empty else pd.NaT,
                "date_span_days": int((unique_sorted.iloc[-1] - unique_sorted.iloc[0]).days)
                if len(unique_sorted) >= 2
                else 0,
                "unique_dates": int(valid.nunique(dropna=True)),
                "duplicate_dates": duplicate_dates,
                "chronological_ordering": chronological,
                "monotonic_increasing": bool(chronological and duplicate_dates == 0),
                "estimated_frequency": infer_regular_frequency(valid),
                "median_spacing": spacing["median_spacing"],
                "most_common_spacing": spacing["most_common_spacing"],
            }
        )
    return records


def time_series_diagnostics(df: pd.DataFrame, datetime_columns: Sequence[str]) -> list[dict[str, Any]]:
    """Measure period continuity and repeated periods for datetime columns."""

    records: list[dict[str, Any]] = []
    for column in datetime_columns:
        dates = parse_datetime_series(df[column]).dropna()
        monthly = monthly_continuity(dates)
        business = business_day_continuity(dates)
        frequency = infer_regular_frequency(dates)

        if monthly["monthly_applicable"]:
            missing_periods = monthly["missing_months"]
            regular = monthly["missing_months"] == 0 and monthly["duplicate_months"] == 0
        elif business["business_day_applicable"]:
            missing_periods = business["missing_business_days"]
            regular = business["missing_business_days"] == 0 and int(dates.duplicated().sum()) == 0
        else:
            missing_periods = "Not calculated"
            regular = frequency not in {"Irregular", "Insufficient dates"} and int(dates.duplicated().sum()) == 0

        records.append(
            {
                "column": column,
                "regular_frequency": regular,
                "estimated_frequency": frequency,
                "missing_periods": missing_periods,
                "duplicate_periods": int(dates.duplicated().sum()),
                "business_day_applicable": business["business_day_applicable"],
                "business_day_continuity_percent": business["business_day_continuity_percent"]
                if business["business_day_applicable"]
                else "Not applicable",
                "missing_business_days": business["missing_business_days"]
                if business["business_day_applicable"]
                else "Not applicable",
                "unexpected_weekday_gaps": business["missing_business_days"]
                if business["business_day_applicable"]
                else "Not applicable",
                "monthly_applicable": monthly["monthly_applicable"],
                "monthly_continuity_percent": monthly["monthly_continuity_percent"]
                if monthly["monthly_applicable"]
                else "Not applicable",
                "missing_months": monthly["missing_months"] if monthly["monthly_applicable"] else "Not applicable",
            }
        )
    return records


def measurement_numeric_columns(df: pd.DataFrame) -> list[str]:
    """Return numeric columns that look like measurements rather than identifiers."""

    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    if not numeric_columns:
        return []

    row_count = len(df)
    excluded_tokens = ("id", "code", "item code", "item_code", "country code", "region code", "zip", "postal", "ref")
    identifier_like_tokens = ("item", "country", "region", "zip", "postal", "ref", "code", "id")
    measurement_columns: list[str] = []
    for column in numeric_columns:
        name = str(column).lower()
        if any(token in name for token in excluded_tokens):
            continue
        if row_count > 0:
            uniqueness_ratio = int(df[column].nunique(dropna=False)) / row_count
            if uniqueness_ratio >= IDENTIFIER_RATIO_THRESHOLD and any(token in name for token in identifier_like_tokens):
                continue
        measurement_columns.append(column)
    return measurement_columns


def correlation_analysis(df: pd.DataFrame, numeric_columns: Sequence[str]) -> dict[str, Any]:
    """Compute correlation matrix and highest/lowest correlation pairs."""

    measurement_columns = measurement_numeric_columns(df)
    if len(measurement_columns) < 2:
        return {"matrix": pd.DataFrame(), "highest_pair": None, "lowest_pair": None}

    values = numeric_frame(df, measurement_columns).replace([np.inf, -np.inf], np.nan)
    matrix = values.corr()
    upper_mask = np.triu(np.ones(matrix.shape, dtype=bool), k=1)
    pairs = matrix.where(upper_mask).stack().dropna()
    if pairs.empty:
        return {"matrix": matrix, "highest_pair": None, "lowest_pair": None}

    highest_key = pairs.idxmax()
    lowest_key = pairs.idxmin()
    return {
        "matrix": matrix,
        "highest_pair": {
            "columns": f"{highest_key[0]} | {highest_key[1]}",
            "correlation": float(pairs.loc[highest_key]),
        },
        "lowest_pair": {
            "columns": f"{lowest_key[0]} | {lowest_key[1]}",
            "correlation": float(pairs.loc[lowest_key]),
        },
    }


def numeric_outlier_total(numeric_stats: Sequence[Mapping[str, Any]]) -> int:
    """Return total IQR outlier count across numeric columns."""

    return int(sum(int(record["outlier_count_iqr"]) for record in numeric_stats))


def save_missing_plot(df: pd.DataFrame, output_path: Path) -> Path:
    """Save a missing-value count bar chart."""

    missing_counts = df.isna().sum()
    fig_width = max(6.0, len(missing_counts) * 0.6)
    fig, ax = plt.subplots(figsize=(fig_width, 4.5))
    ax.bar(missing_counts.index.astype(str), missing_counts.values, color="#4C78A8")
    ax.set_title("Missing Values by Column")
    ax.set_xlabel("Column")
    ax.set_ylabel("Missing Count")
    ax.tick_params(axis="x", rotation=45)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def save_correlation_heatmap(matrix: pd.DataFrame, output_path: Path) -> Path | None:
    """Save a correlation heatmap when a correlation matrix exists."""

    if matrix.empty:
        return None

    fig_size = max(5.0, len(matrix.columns) * 0.7)
    fig, ax = plt.subplots(figsize=(fig_size, fig_size))
    image = ax.imshow(matrix, cmap="coolwarm", vmin=-1, vmax=1)
    fig.colorbar(image, ax=ax, fraction=0.046, pad=0.04)
    ax.set_xticks(range(len(matrix.columns)))
    ax.set_yticks(range(len(matrix.index)))
    ax.set_xticklabels(matrix.columns, rotation=45, ha="right")
    ax.set_yticklabels(matrix.index)
    ax.set_title("Correlation Matrix")
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def subplot_grid_size(item_count: int) -> tuple[int, int]:
    """Return a compact grid shape for subplot rendering."""

    if item_count <= 0:
        return 0, 0
    columns = min(3, item_count)
    rows = int(np.ceil(item_count / columns))
    return rows, columns


def save_histograms(df: pd.DataFrame, numeric_columns: Sequence[str], output_path: Path) -> Path | None:
    """Save histograms for finite values in numeric columns."""

    values = numeric_frame(df, numeric_columns).replace([np.inf, -np.inf], np.nan)
    valid_columns = [column for column in values.columns if values[column].dropna().shape[0] > 0]
    if not valid_columns:
        return None

    rows, columns = subplot_grid_size(len(valid_columns))
    fig, axes = plt.subplots(rows, columns, figsize=(4.5 * columns, 3.5 * rows), squeeze=False)
    flat_axes = axes.ravel()
    for index, column in enumerate(valid_columns):
        data = values[column].dropna()
        flat_axes[index].hist(data, bins=30, color="#4C78A8", edgecolor="white")
        flat_axes[index].set_title(str(column))
        flat_axes[index].set_ylabel("Frequency")
    for index in range(len(valid_columns), len(flat_axes)):
        fig.delaxes(flat_axes[index])
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def save_boxplots(df: pd.DataFrame, numeric_columns: Sequence[str], output_path: Path) -> Path | None:
    """Save boxplots for finite values in numeric columns."""

    values = numeric_frame(df, numeric_columns).replace([np.inf, -np.inf], np.nan)
    valid_columns = [column for column in values.columns if values[column].dropna().shape[0] > 0]
    if not valid_columns:
        return None

    rows, columns = subplot_grid_size(len(valid_columns))
    fig, axes = plt.subplots(rows, columns, figsize=(4.5 * columns, 3.5 * rows), squeeze=False)
    flat_axes = axes.ravel()
    for index, column in enumerate(valid_columns):
        data = values[column].dropna()
        flat_axes[index].boxplot(data, vert=True)
        flat_axes[index].set_title(str(column))
        flat_axes[index].set_ylabel("Value")
    for index in range(len(valid_columns), len(flat_axes)):
        fig.delaxes(flat_axes[index])
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def save_time_series_plot(
    df: pd.DataFrame,
    datetime_columns: Sequence[str],
    numeric_columns: Sequence[str],
    output_path: Path,
) -> Path | None:
    """Save time-series plots for numeric columns against the primary date."""

    primary_date = select_primary_datetime_column(datetime_columns)
    if primary_date is None or not numeric_columns:
        return None

    dates = parse_datetime_series(df[primary_date])
    values = numeric_frame(df, numeric_columns).replace([np.inf, -np.inf], np.nan)
    plot_frame = values.assign(__date__=dates).dropna(subset=["__date__"])
    valid_columns = [column for column in numeric_columns if plot_frame[column].dropna().shape[0] > 0]
    if not valid_columns:
        return None

    rows, columns = subplot_grid_size(len(valid_columns))
    fig, axes = plt.subplots(rows, columns, figsize=(5.0 * columns, 3.3 * rows), squeeze=False)
    flat_axes = axes.ravel()
    duplicate_dates = int(dates.dropna().duplicated().sum())
    ordered = plot_frame.sort_values("__date__")

    for index, column in enumerate(valid_columns):
        column_data = ordered[["__date__", column]].dropna()
        if duplicate_dates == 0:
            flat_axes[index].plot(column_data["__date__"], column_data[column], linewidth=1.2)
        else:
            flat_axes[index].scatter(column_data["__date__"], column_data[column], s=8, alpha=0.65)
        flat_axes[index].set_title(str(column))
        flat_axes[index].set_xlabel(primary_date)
        flat_axes[index].set_ylabel("Value")
    for index in range(len(valid_columns), len(flat_axes)):
        fig.delaxes(flat_axes[index])
    fig.autofmt_xdate(rotation=30)
    fig.tight_layout()
    fig.savefig(output_path, dpi=150)
    plt.close(fig)
    return output_path


def generate_figures(
    df: pd.DataFrame,
    dataset_stem: str,
    column_groups: ColumnGroups,
    correlation: Mapping[str, Any],
) -> FigurePaths:
    """Generate all supported figures for one dataset."""

    ensure_output_directories()
    missing = save_missing_plot(df, FIGURE_DIR / f"{dataset_stem}_missing.png")
    histogram = save_histograms(df, column_groups.numeric, FIGURE_DIR / f"{dataset_stem}_histogram.png")
    boxplot = save_boxplots(df, column_groups.numeric, FIGURE_DIR / f"{dataset_stem}_boxplot.png")
    time_series = save_time_series_plot(
        df,
        column_groups.datetime,
        column_groups.numeric,
        FIGURE_DIR / f"{dataset_stem}_timeseries.png",
    )
    correlation_path = save_correlation_heatmap(
        correlation["matrix"],
        FIGURE_DIR / f"{dataset_stem}_correlation.png",
    )
    return FigurePaths(
        missing=missing,
        correlation=correlation_path,
        histogram=histogram,
        boxplot=boxplot,
        time_series=time_series,
    )


def long_structure_measure(df: pd.DataFrame) -> dict[str, Any]:
    """Measure whether common long-format columns are present."""

    identifier_columns = [
        column
        for column in ("Date", "Item Code", "Item", "REF_AREA", "INDICATOR", "INDICATOR_LABEL")
        if column in df.columns
    ]
    value_column_present = "Value" in df.columns
    non_value_columns = [column for column in df.columns if column != "Value"]
    long_structure_columns_present = value_column_present and len(identifier_columns) >= 2
    wide_numeric_measure_columns = [
        column
        for column in df.select_dtypes(include=[np.number]).columns
        if column != "Value" and "code" not in column.lower() and "id" not in column.lower()
    ]

    return {
        "value_column_present": value_column_present,
        "identifier_columns_present": format_list(identifier_columns),
        "non_value_columns": len(non_value_columns),
        "long_structure_columns_present": long_structure_columns_present,
        "long_vs_wide_structure": "long" if long_structure_columns_present else "wide_or_other",
        "wide_numeric_measure_columns": format_list(wide_numeric_measure_columns),
    }


def baltic_dry_index_checks(df: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Run Baltic Dry Index checks using a business-day calendar."""

    records: list[dict[str, Any]] = []
    tables: dict[str, list[dict[str, Any]]] = {}
    if "Date" not in df.columns:
        return [{"metric": "Date column present", "value": False}], tables

    dates = normalize_dates(df["Date"]).dropna()
    business = business_day_continuity(dates)
    missing_dates = business["first_missing_business_days"]
    numeric_columns = df.select_dtypes(include=[np.number]).columns.tolist()
    values = numeric_frame(df, numeric_columns).replace([np.inf, -np.inf], np.nan)
    zero_records = [
        {"column": column, "zero_count": int((values[column] == 0).sum())}
        for column in numeric_columns
    ]

    records.extend(
        [
            {"metric": "Duplicate trading days", "value": int(dates.duplicated().sum())},
            {"metric": "Unexpected weekday gaps", "value": business["missing_business_days"]},
            {"metric": "Business-day continuity percent", "value": business["business_day_continuity_percent"]},
            {"metric": "Observed business days", "value": business["observed_business_days"]},
            {"metric": "Expected business days", "value": business["expected_business_days"]},
            {"metric": "Weekend records", "value": business["weekend_records"]},
            {
                "metric": "Date continuity on business-day calendar",
                "value": bool(business["missing_business_days"] == 0 and int(dates.duplicated().sum()) == 0),
            },
            {"metric": "First missing business days", "value": missing_dates},
            {"metric": "Zero values across numeric columns", "value": int(sum(row["zero_count"] for row in zero_records))},
        ]
    )
    tables["Zero values by numeric column"] = zero_records
    return records, tables


def brent_crude_checks(df: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Run Brent crude monthly continuity checks."""

    if "Date" not in df.columns:
        return [{"metric": "Date column present", "value": False}], {}

    dates = normalize_dates(df["Date"]).dropna()
    monthly = monthly_continuity(dates)
    records = [
        {"metric": "Monthly continuity percent", "value": monthly["monthly_continuity_percent"]},
        {"metric": "Duplicate months", "value": monthly["duplicate_months"]},
        {"metric": "Missing months", "value": monthly["missing_months"]},
        {"metric": "Unique months", "value": monthly["unique_months"]},
        {"metric": "Expected months", "value": monthly["expected_months"]},
        {"metric": "First missing months", "value": monthly["first_missing_months"]},
        {"metric": "Chronological ordering", "value": bool(dates.is_monotonic_increasing)},
    ]
    return records, {}


def policy_rate_checks(df: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Run Botswana policy-rate change checks."""

    if "Date" not in df.columns or "policy_rate" not in df.columns:
        return [
            {"metric": "Date column present", "value": "Date" in df.columns},
            {"metric": "policy_rate column present", "value": "policy_rate" in df.columns},
        ], {}

    working = pd.DataFrame(
        {
            "Date": normalize_dates(df["Date"]),
            "policy_rate": pd.to_numeric(df["policy_rate"], errors="coerce"),
        }
    ).dropna(subset=["Date", "policy_rate"])
    working = working.sort_values("Date")
    if working.empty:
        return [{"metric": "Rows with parseable Date and policy_rate", "value": 0}], {}

    change_mask = working["policy_rate"].ne(working["policy_rate"].shift()) & working["policy_rate"].shift().notna()
    change_rows = working.loc[change_mask]
    group_ids = working["policy_rate"].ne(working["policy_rate"].shift()).cumsum()
    grouped = working.assign(group_id=group_ids).groupby("group_id", sort=False)
    periods = grouped.agg(
        start_date=("Date", "min"),
        end_date=("Date", "max"),
        records=("Date", "size"),
        policy_rate=("policy_rate", "first"),
    )
    periods["duration_days"] = (periods["end_date"] - periods["start_date"]).dt.days
    longest = periods.sort_values(["duration_days", "records"], ascending=False).iloc[0]

    records = [
        {"metric": "Number of policy changes", "value": int(change_mask.sum())},
        {"metric": "Dates of changes", "value": format_list(change_rows["Date"].dt.date.astype(str).tolist())},
        {"metric": "Longest unchanged period start", "value": longest["start_date"].date().isoformat()},
        {"metric": "Longest unchanged period end", "value": longest["end_date"].date().isoformat()},
        {"metric": "Longest unchanged period records", "value": int(longest["records"])},
        {"metric": "Longest unchanged period days", "value": int(longest["duration_days"])},
        {"metric": "Negative policy_rate values", "value": int((working["policy_rate"] < 0).sum())},
        {"metric": "Zero policy_rate values", "value": int((working["policy_rate"] == 0).sum())},
    ]
    tables = {
        "Policy change records": [
            {
                "date": row["Date"].date().isoformat(),
                "policy_rate": row["policy_rate"],
            }
            for _, row in change_rows.head(TOP_N).iterrows()
        ]
    }
    return records, tables


def fao_botswana_checks(df: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Run FAO Botswana item and item-month checks."""

    records: list[dict[str, Any]] = []
    tables: dict[str, list[dict[str, Any]]] = {}
    structure = long_structure_measure(df)

    records.extend(
        [
            {"metric": "Unique items", "value": int(df["Item"].nunique(dropna=False)) if "Item" in df.columns else 0},
            {
                "metric": "Unique item codes",
                "value": int(df["Item Code"].nunique(dropna=False)) if "Item Code" in df.columns else 0,
            },
            {"metric": "Value column present", "value": structure["value_column_present"]},
            {"metric": "Identifier columns present", "value": structure["identifier_columns_present"]},
            {"metric": "Long-structure columns present", "value": structure["long_structure_columns_present"]},
            {"metric": "Long vs wide structure", "value": structure["long_vs_wide_structure"]},
            {"metric": "Wide numeric measure columns", "value": structure["wide_numeric_measure_columns"]},
        ]
    )

    if "Date" in df.columns:
        months = normalize_dates(df["Date"]).dt.to_period("M")
        records.append({"metric": "Unique months", "value": int(months.nunique(dropna=True))})
        monthly = monthly_continuity(normalize_dates(df["Date"]).dropna())
        records.append({"metric": "Missing months", "value": monthly["missing_months"]})

        if "Item Code" in df.columns:
            item_month = pd.DataFrame({"Item Code": df["Item Code"], "month": months})
            duplicate_mask = item_month.duplicated()
            records.append({"metric": "Duplicate item-month combinations", "value": int(duplicate_mask.sum())})
            duplicates = item_month[item_month.duplicated(keep=False)].head(TOP_N)
            tables["Duplicate item-month preview"] = duplicates.to_dict(orient="records")

    return records, tables


def human_capital_checks(df: pd.DataFrame) -> tuple[list[dict[str, Any]], dict[str, list[dict[str, Any]]]]:
    """Run Human Capital country, indicator, year, and duplicate checks."""

    records: list[dict[str, Any]] = [
        {"metric": "Countries", "value": int(df["REF_AREA"].nunique(dropna=False)) if "REF_AREA" in df.columns else 0},
        {
            "metric": "Country labels",
            "value": int(df["REF_AREA_LABEL"].nunique(dropna=False)) if "REF_AREA_LABEL" in df.columns else 0,
        },
        {
            "metric": "Indicators",
            "value": int(df["INDICATOR"].nunique(dropna=False)) if "INDICATOR" in df.columns else 0,
        },
        {
            "metric": "Indicator labels",
            "value": int(df["INDICATOR_LABEL"].nunique(dropna=False)) if "INDICATOR_LABEL" in df.columns else 0,
        },
    ]
    tables: dict[str, list[dict[str, Any]]] = {}

    if "Date" in df.columns:
        dates = normalize_dates(df["Date"])
        years = dates.dt.year
        records.append({"metric": "Years", "value": int(years.nunique(dropna=True))})

        if "REF_AREA" in df.columns:
            country_date = pd.DataFrame({"REF_AREA": df["REF_AREA"], "Date": dates})
            records.append({"metric": "Duplicate country-date records", "value": int(country_date.duplicated().sum())})
        if "REF_AREA" in df.columns and "INDICATOR" in df.columns:
            country_indicator_date = pd.DataFrame(
                {
                    "REF_AREA": df["REF_AREA"],
                    "INDICATOR": df["INDICATOR"],
                    "Date": dates,
                }
            )
            records.append(
                {
                    "metric": "Duplicate country-indicator-date records",
                    "value": int(country_indicator_date.duplicated().sum()),
                }
            )

        missing_rows = df[df.isna().any(axis=1)].copy()
        if not missing_rows.empty:
            missing_rows["Year"] = years.loc[missing_rows.index]
            if "REF_AREA" in missing_rows.columns:
                tables["Missing values by country"] = (
                    missing_rows.groupby("REF_AREA", dropna=False)
                    .size()
                    .sort_values(ascending=False)
                    .head(TOP_N)
                    .reset_index(name="missing_rows")
                    .to_dict(orient="records")
                )
            if "INDICATOR" in missing_rows.columns:
                tables["Missing values by indicator"] = (
                    missing_rows.groupby("INDICATOR", dropna=False)
                    .size()
                    .sort_values(ascending=False)
                    .head(TOP_N)
                    .reset_index(name="missing_rows")
                    .to_dict(orient="records")
                )
            tables["Missing values by year"] = (
                missing_rows.groupby("Year", dropna=False)
                .size()
                .sort_values(ascending=False)
                .head(TOP_N)
                .reset_index(name="missing_rows")
                .to_dict(orient="records")
            )

    return records, tables


def dataset_specific_checks(dataset_name: str, df: pd.DataFrame) -> dict[str, Any]:
    """Run dataset-specific checks selected by filename."""

    filename = dataset_name.lower()
    if "baltic_dry_index" in filename or "01_baltic" in filename:
        records, tables = baltic_dry_index_checks(df)
        return {"dataset_type": "Baltic Dry Index", "records": records, "tables": tables}
    if "brent_crude" in filename or "02_brent" in filename:
        records, tables = brent_crude_checks(df)
        return {"dataset_type": "Brent Crude", "records": records, "tables": tables}
    if "policy_rate" in filename or "03_botswana_policy" in filename:
        records, tables = policy_rate_checks(df)
        return {"dataset_type": "Botswana Policy Rate", "records": records, "tables": tables}
    if "fao_botswana" in filename or "04_fao" in filename:
        records, tables = fao_botswana_checks(df)
        return {"dataset_type": "FAO Botswana", "records": records, "tables": tables}
    if "human_capital" in filename or "05_human" in filename:
        records, tables = human_capital_checks(df)
        return {"dataset_type": "Human Capital", "records": records, "tables": tables}

    return {
        "dataset_type": "No filename-specific rule matched",
        "records": [{"metric": "Dataset-specific checks generated", "value": 0}],
        "tables": {},
    }


def objective_pipeline_observations(
    df: pd.DataFrame,
    column_groups: ColumnGroups,
    data_quality: Mapping[str, Any],
    datetime_stats: Sequence[Mapping[str, Any]],
    dataset_specific: Mapping[str, Any],
) -> list[dict[str, Any]]:
    """Return measurable observations for downstream pipeline visibility."""

    observations: list[dict[str, Any]] = []
    object_date_columns = data_quality["object_columns_containing_dates"]
    if object_date_columns:
        observations.append(
            {
                "observation": "Object columns containing date-like values",
                "measured_value": format_list(object_date_columns),
            }
        )
    if data_quality["duplicate_rows"] > 0:
        observations.append({"observation": "Duplicate rows present", "measured_value": data_quality["duplicate_rows"]})
    if data_quality["duplicate_dates_total"] > 0:
        observations.append(
            {"observation": "Duplicate datetime values present", "measured_value": data_quality["duplicate_dates_total"]}
        )
    if data_quality["total_missing"] > 0:
        observations.append({"observation": "Missing values present", "measured_value": data_quality["total_missing"]})
    if data_quality["infinite_values"] > 0:
        observations.append({"observation": "Infinite numeric values present", "measured_value": data_quality["infinite_values"]})
    if data_quality["constant_columns"]:
        observations.append(
            {
                "observation": "Constant columns present",
                "measured_value": format_list(data_quality["constant_columns"]),
            }
        )
    if data_quality["near_constant_columns"]:
        observations.append(
            {
                "observation": "Near-constant columns at configured threshold",
                "measured_value": format_list([row["column"] for row in data_quality["near_constant_columns"]]),
            }
        )
    if data_quality["potential_identifier_columns"]:
        observations.append(
            {
                "observation": "High-cardinality non-float columns at configured threshold",
                "measured_value": format_list([row["column"] for row in data_quality["potential_identifier_columns"]]),
            }
        )

    for record in datetime_stats:
        frequency = record["estimated_frequency"]
        if frequency != "Irregular":
            observations.append(
                {
                    "observation": f"Datetime frequency detected for {record['column']}",
                    "measured_value": frequency,
                }
            )

    structure = long_structure_measure(df)
    if structure["long_structure_columns_present"]:
        observations.append(
            {
                "observation": "Long-structure columns present",
                "measured_value": structure["identifier_columns_present"],
            }
        )

    measure_like_columns = [
        column
        for column in column_groups.numeric
        if any(pattern in column.lower() for pattern in MEASURE_NAME_PATTERNS)
    ]
    if measure_like_columns:
        observations.append(
            {
                "observation": "Numeric measure-like column names present",
                "measured_value": format_list(measure_like_columns),
            }
        )

    observations.append(
        {
            "observation": "Dataset-specific rule applied",
            "measured_value": dataset_specific["dataset_type"],
        }
    )
    return observations


def figure_markdown(path: Path | None, label: str) -> str:
    """Return Markdown image syntax for a generated figure path."""

    if path is None:
        return f"- {label}: Not generated"
    return f"![{label}](../figures/{path.name})"


def dataframe_shape_value(df: pd.DataFrame) -> str:
    """Return dataframe shape as rows x columns."""

    return f"{df.shape[0]} rows x {df.shape[1]} columns"


def datetime_stats_by_column(datetime_stats: Sequence[Mapping[str, Any]]) -> dict[str, Mapping[str, Any]]:
    """Index datetime statistics by column name."""

    return {str(record["column"]): record for record in datetime_stats}


def executive_summary_records(
    dataset_name: str,
    df: pd.DataFrame,
    column_groups: ColumnGroups,
    data_quality: Mapping[str, Any],
    datetime_stats: Sequence[Mapping[str, Any]],
    numeric_stats: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Build executive summary metric records containing measured facts only."""

    primary_date = select_primary_datetime_column(column_groups.datetime)
    stats_by_column = datetime_stats_by_column(datetime_stats)
    if primary_date and primary_date in stats_by_column:
        date_stats = stats_by_column[primary_date]
        date_range = f"{format_value(date_stats['earliest_date'])} to {format_value(date_stats['latest_date'])}"
        frequency = date_stats["estimated_frequency"]
    else:
        date_range = "Not detected"
        frequency = "Not detected"

    return [
        {"metric": "Dataset Name", "value": dataset_name},
        {"metric": "Rows", "value": int(df.shape[0])},
        {"metric": "Columns", "value": int(df.shape[1])},
        {"metric": "Date Range", "value": date_range},
        {"metric": "Detected Frequency", "value": frequency},
        {"metric": "Missing Values", "value": data_quality["total_missing"]},
        {"metric": "Duplicate Rows", "value": data_quality["duplicate_rows"]},
        {"metric": "Duplicate Dates", "value": data_quality["duplicate_dates_total"]},
        {"metric": "Outliers Detected", "value": numeric_outlier_total(numeric_stats)},
        {"metric": "Numeric Columns", "value": len(column_groups.numeric)},
        {"metric": "Categorical Columns", "value": len(column_groups.categorical)},
        {"metric": "Memory Usage", "value": format_bytes(dataframe_memory_usage(df))},
    ]


def dataset_overview_records(df: pd.DataFrame, column_groups: ColumnGroups) -> list[dict[str, Any]]:
    """Build dataset overview records."""

    return [
        {"metric": "Rows", "value": int(df.shape[0])},
        {"metric": "Columns", "value": int(df.shape[1])},
        {"metric": "Memory Usage", "value": format_bytes(dataframe_memory_usage(df))},
        {"metric": "Shape", "value": dataframe_shape_value(df)},
        {"metric": "Column Count", "value": int(len(df.columns))},
        {"metric": "Numeric Columns", "value": format_list(column_groups.numeric)},
        {"metric": "Numeric Column Count", "value": len(column_groups.numeric)},
        {"metric": "Categorical Columns", "value": format_list(column_groups.categorical)},
        {"metric": "Categorical Column Count", "value": len(column_groups.categorical)},
        {"metric": "Datetime Columns", "value": format_list(column_groups.datetime)},
        {"metric": "Datetime Column Count", "value": len(column_groups.datetime)},
    ]


def render_data_quality_section(data_quality: Mapping[str, Any]) -> list[str]:
    """Render data quality summary and detail tables."""

    lines: list[str] = ["## Data Quality", ""]
    summary_records = [
        {"metric": "Missing values", "value": data_quality["total_missing"]},
        {"metric": "Missing %", "value": data_quality["missing_percent"]},
        {"metric": "Duplicate rows", "value": data_quality["duplicate_rows"]},
        {"metric": "Duplicate dates", "value": data_quality["duplicate_dates_total"]},
        {"metric": "Infinite values", "value": data_quality["infinite_values"]},
        {"metric": "Zero values", "value": data_quality["zero_values"]},
        {"metric": "Negative values", "value": data_quality["negative_values"]},
        {"metric": "Constant columns", "value": format_list(data_quality["constant_columns"])},
        {
            "metric": "Near-constant columns",
            "value": format_list([row["column"] for row in data_quality["near_constant_columns"]]),
        },
        {
            "metric": "Potential identifier columns",
            "value": format_list([row["column"] for row in data_quality["potential_identifier_columns"]]),
        },
        {
            "metric": "Mixed data type columns",
            "value": format_list([row["column"] for row in data_quality["mixed_data_type_columns"]]),
        },
        {
            "metric": "Object columns containing dates",
            "value": format_list(data_quality["object_columns_containing_dates"]),
        },
    ]
    lines.append(markdown_table(summary_records, [("metric", "Measure"), ("value", "Value")]))
    lines.append("")

    if data_quality["signed_value_counts"]:
        lines.append("### Numeric Sign Counts")
        lines.append("")
        lines.append(
            markdown_table(
                data_quality["signed_value_counts"],
                [
                    ("column", "Column"),
                    ("zero_count", "Zero Values"),
                    ("negative_count", "Negative Values"),
                    ("positive_count", "Positive Values"),
                ],
            )
        )
        lines.append("")

    if data_quality["near_constant_columns"]:
        lines.append(f"### Near-Constant Columns (Dominant Value >= {NEAR_CONSTANT_DOMINANCE_THRESHOLD:.0%})")
        lines.append("")
        lines.append(
            markdown_table(
                data_quality["near_constant_columns"],
                [
                    ("column", "Column"),
                    ("dominant_value", "Dominant Value"),
                    ("dominant_count", "Dominant Count"),
                    ("dominant_percent", "Dominant %"),
                    ("unique_values", "Unique Values"),
                ],
            )
        )
        lines.append("")

    if data_quality["potential_identifier_columns"]:
        lines.append(f"### Potential Identifier Columns (Unique Ratio >= {IDENTIFIER_RATIO_THRESHOLD:.0%})")
        lines.append("")
        lines.append(
            markdown_table(
                data_quality["potential_identifier_columns"],
                [
                    ("column", "Column"),
                    ("unique_values", "Unique Values"),
                    ("unique_percent", "Unique %"),
                ],
            )
        )
        lines.append("")

    if data_quality["mixed_data_type_columns"]:
        lines.append("### Mixed Data Type Columns")
        lines.append("")
        lines.append(
            markdown_table(
                data_quality["mixed_data_type_columns"],
                [
                    ("column", "Column"),
                    ("inferred_dtype", "Inferred Dtype"),
                    ("python_types", "Python Types"),
                ],
            )
        )
        lines.append("")

    return lines


def render_missing_value_section(missing_analysis_data: Mapping[str, Any]) -> list[str]:
    """Render missing value analysis."""

    lines = ["## Missing Value Analysis", ""]
    lines.append("### Missing Count Per Column")
    lines.append("")
    lines.append(
        markdown_table(
            missing_analysis_data["missing_by_column"],
            [
                ("column", "Column"),
                ("missing_count", "Missing Count"),
                ("missing_percent", "Missing %"),
            ],
        )
    )
    lines.append("")
    lines.append(
        f"Rows containing missing values: {missing_analysis_data['missing_rows_count']} "
        f"({missing_analysis_data['missing_rows_percent']}%)"
    )
    lines.append("")
    lines.append("### Rows Containing Missing Values (First 10)")
    lines.append("")
    lines.append(dataframe_to_markdown(missing_analysis_data["missing_rows_preview"]))
    lines.append("")

    if missing_analysis_data["grouped_missing"]:
        for group_name, records in missing_analysis_data["grouped_missing"].items():
            lines.append(f"### Missing Values Grouped by {group_name}")
            lines.append("")
            lines.append(
                markdown_table(
                    records,
                    [
                        (group_name, group_name),
                        ("missing_rows", "Rows With Missing Values"),
                        ("missing_cells", "Missing Cells"),
                    ],
                )
            )
            lines.append("")
    else:
        lines.append("Grouped missing-value tables generated: 0")
        lines.append("")

    return lines


def render_duplicate_section(duplicate_analysis_data: Mapping[str, Any]) -> list[str]:
    """Render duplicate analysis."""

    lines = ["## Duplicate Analysis", ""]
    lines.append(f"Duplicate count: {duplicate_analysis_data['duplicate_row_count']}")
    lines.append("")
    lines.append("### Preview Duplicate Records")
    lines.append("")
    lines.append(dataframe_to_markdown(duplicate_analysis_data["duplicate_records_preview"]))
    lines.append("")
    lines.append("### Repeated Date Values")
    lines.append("")
    if duplicate_analysis_data["duplicate_dates"]:
        if any(record.get("expected_repeated_dates") for record in duplicate_analysis_data["duplicate_dates"]):
            lines.append("Expected (Long/Panel Structure)")
        else:
            lines.append(
                markdown_table(
                    duplicate_analysis_data["duplicate_dates"],
                    [
                        ("column", "Datetime Column"),
                        ("duplicate_date_rows", "Duplicate Date Rows"),
                        ("duplicate_date_values", "Duplicate Date Values"),
                        ("status", "Status"),
                        ("first_duplicated_dates", "First Duplicated Dates"),
                    ],
                )
            )
    else:
        lines.append("No datetime columns detected.")
    lines.append("")
    return lines


def render_join_key_section(df: pd.DataFrame) -> list[str]:
    """Render objective join-key candidates for the dataset."""

    lines = ["## Join Key Analysis", ""]
    join_keys = detect_candidate_join_keys(df)
    if not join_keys:
        lines.append("No candidate join keys detected.")
        lines.append("")
        return lines

    records = [
        {
            "candidate_key": " + ".join(record["columns"]),
            "classification": record["kind"],
        }
        for record in join_keys
    ]
    lines.append(markdown_table(records, [("candidate_key", "Candidate Key"), ("classification", "Classification")]))
    lines.append("")
    return lines


def render_numeric_statistics_section(numeric_stats: Sequence[Mapping[str, Any]]) -> list[str]:
    """Render numeric statistics."""

    lines = ["## Numeric Statistics", ""]
    if not numeric_stats:
        lines.append("Numeric columns detected: 0")
        lines.append("")
        return lines

    lines.append(
        markdown_table(
            numeric_stats,
            [
                ("column", "Column"),
                ("count", "Count"),
                ("mean", "Mean"),
                ("median", "Median"),
                ("mode", "Mode"),
                ("minimum", "Minimum"),
                ("maximum", "Maximum"),
                ("range", "Range"),
                ("variance", "Variance"),
                ("standard_deviation", "Standard Deviation"),
                ("coefficient_of_variation", "Coefficient of Variation"),
                ("iqr", "IQR"),
                ("skewness", "Skewness"),
                ("kurtosis", "Kurtosis"),
                ("zero_count", "Zero Count"),
                ("negative_count", "Negative Count"),
                ("positive_count", "Positive Count"),
                ("outlier_count_iqr", "Outlier Count Using IQR"),
            ],
        )
    )
    lines.append("")
    return lines


def render_categorical_statistics_section(categorical_stats: Mapping[str, Any]) -> list[str]:
    """Render categorical statistics."""

    lines = ["## Categorical Statistics", ""]
    if not categorical_stats:
        lines.append("Categorical columns detected: 0")
        lines.append("")
        return lines

    for column, stats in categorical_stats.items():
        lines.append(f"### {column}")
        lines.append("")
        lines.append(f"Unique values: {stats['unique_values']}")
        lines.append("")
        lines.append(
            markdown_table(
                stats["top_values"],
                [
                    ("value", "Top 10 Values"),
                    ("frequency", "Frequency"),
                    ("frequency_percent", "Frequency %"),
                ],
            )
        )
        lines.append("")
    return lines


def render_datetime_analysis_section(datetime_stats: Sequence[Mapping[str, Any]]) -> list[str]:
    """Render datetime analysis."""

    lines = ["## Datetime Analysis", ""]
    if not datetime_stats:
        lines.append("Datetime columns detected: 0")
        lines.append("")
        return lines

    lines.append(
        markdown_table(
            datetime_stats,
            [
                ("column", "Column"),
                ("earliest_date", "Earliest Date"),
                ("latest_date", "Latest Date"),
                ("date_span_days", "Date Span Days"),
                ("unique_dates", "Unique Dates"),
                ("duplicate_dates", "Duplicate Dates"),
                ("chronological_ordering", "Chronological Ordering"),
                ("monotonic_increasing", "Monotonic Increasing"),
                ("estimated_frequency", "Estimated Frequency"),
                ("median_spacing", "Median Spacing"),
                ("most_common_spacing", "Most Common Spacing"),
            ],
        )
    )
    lines.append("")
    return lines


def detect_candidate_join_keys(df: pd.DataFrame) -> list[dict[str, Any]]:
    """Return candidate join-key columns and composite keys supported by the observed data."""

    datetime_columns = [column for column in detect_datetime_columns(df) if column in df.columns]
    identifier_columns = [
        column
        for column in df.columns
        if column not in datetime_columns
        and any(str(column).lower() == token or str(column).lower().startswith(f"{token} ") for token in JOIN_KEY_IDENTIFIER_TOKENS)
    ]
    ordered_columns = datetime_columns + identifier_columns
    if not ordered_columns:
        return []

    candidates: list[dict[str, Any]] = []
    for column in ordered_columns:
        values = df[column].dropna()
        if values.empty:
            continue
        if values.nunique(dropna=True) == len(values):
            candidates.append({"columns": [column], "kind": "Candidate Key"})

    for size in range(2, min(4, len(ordered_columns) + 1)):
        for combo in combinations(ordered_columns, size):
            subset = df.loc[:, list(combo)].dropna(how="any")
            if subset.empty:
                continue
            if subset.shape[0] == subset.drop_duplicates().shape[0]:
                candidates.append({"columns": list(combo), "kind": "Composite Candidate Key"})
                return candidates

    return candidates


def render_correlation_section(correlation: Mapping[str, Any]) -> list[str]:
    """Render correlation analysis."""

    lines = ["## Correlation Analysis", ""]
    matrix = correlation["matrix"]
    if matrix.empty:
        lines.append("Numeric columns available for correlation: fewer than 2")
        lines.append("")
        return lines

    records = []
    for index, row in matrix.iterrows():
        record = {"column": index}
        for column in matrix.columns:
            record[str(column)] = row[column]
        records.append(record)
    columns = [("column", "Column")] + [(str(column), str(column)) for column in matrix.columns]
    lines.append(markdown_table(records, columns))
    lines.append("")

    pair_records = []
    if correlation["highest_pair"] is not None:
        pair_records.append({"metric": "Highest correlation pair", **correlation["highest_pair"]})
    if correlation["lowest_pair"] is not None:
        pair_records.append({"metric": "Lowest correlation pair", **correlation["lowest_pair"]})
    if pair_records:
        lines.append(
            markdown_table(
                pair_records,
                [
                    ("metric", "Measure"),
                    ("columns", "Columns"),
                    ("correlation", "Correlation"),
                ],
            )
        )
        lines.append("")
    return lines


def render_distribution_section(figures: FigurePaths) -> list[str]:
    """Render distribution-analysis figure links."""

    lines = ["## Distribution Analysis", ""]
    lines.append(figure_markdown(figures.histogram, "Histograms"))
    lines.append("")
    lines.append(figure_markdown(figures.boxplot, "Boxplots"))
    lines.append("")
    return lines


def render_time_series_diagnostics_section(
    diagnostics: Sequence[Mapping[str, Any]],
    figures: FigurePaths,
) -> list[str]:
    """Render time-series diagnostics."""

    lines = ["## Time-Series Diagnostics", ""]
    if diagnostics:
        lines.append(
            markdown_table(
                diagnostics,
                [
                    ("column", "Column"),
                    ("regular_frequency", "Regular Frequency"),
                    ("estimated_frequency", "Estimated Frequency"),
                    ("missing_periods", "Missing Periods"),
                    ("duplicate_periods", "Duplicate Periods"),
                    ("business_day_applicable", "Business-Day Applicable"),
                    ("business_day_continuity_percent", "Business-Day Continuity %"),
                    ("missing_business_days", "Missing Business Days"),
                    ("unexpected_weekday_gaps", "Unexpected Weekday Gaps"),
                    ("monthly_applicable", "Monthly Applicable"),
                    ("monthly_continuity_percent", "Monthly Continuity %"),
                    ("missing_months", "Missing Months"),
                ],
            )
        )
    else:
        lines.append("Datetime columns detected: 0")
    lines.append("")
    lines.append(figure_markdown(figures.time_series, "Time Series"))
    lines.append("")
    return lines


def render_dataset_specific_section(dataset_specific: Mapping[str, Any]) -> list[str]:
    """Render dataset-specific checks."""

    lines = ["## Dataset-Specific Checks", ""]
    lines.append(f"Dataset-specific rule: {dataset_specific['dataset_type']}")
    lines.append("")
    records = dataset_specific["records"]
    lines.append(markdown_table(records, [("metric", "Measure"), ("value", "Value")]))
    lines.append("")

    for title, table_records in dataset_specific["tables"].items():
        lines.append(f"### {title}")
        lines.append("")
        if table_records:
            columns = [(key, key) for key in table_records[0].keys()]
            lines.append(markdown_table(table_records, columns))
        else:
            lines.append("Records: 0")
        lines.append("")

    return lines


def render_pipeline_impact_section(observations: Sequence[Mapping[str, Any]]) -> list[str]:
    """Render objective pipeline observations."""

    lines = ["## Pipeline Impact", ""]
    lines.append(
        markdown_table(
            observations,
            [
                ("observation", "Measured Observation"),
                ("measured_value", "Measured Value"),
            ],
        )
    )
    lines.append("")
    return lines


def render_figures_section(figures: FigurePaths) -> list[str]:
    """Render all generated figure links."""

    lines = ["## Figures", ""]
    figure_records = [
        {"figure": "Missing-value plot", "path": figures.missing.name if figures.missing else "Not generated"},
        {"figure": "Correlation heatmap", "path": figures.correlation.name if figures.correlation else "Not generated"},
        {"figure": "Histograms", "path": figures.histogram.name if figures.histogram else "Not generated"},
        {"figure": "Boxplots", "path": figures.boxplot.name if figures.boxplot else "Not generated"},
        {"figure": "Time-series plot", "path": figures.time_series.name if figures.time_series else "Not generated"},
    ]
    lines.append(markdown_table(figure_records, [("figure", "Figure"), ("path", "Saved File")]))
    lines.append("")
    lines.append(figure_markdown(figures.missing, "Missing Values"))
    lines.append("")
    lines.append(figure_markdown(figures.correlation, "Correlation Heatmap"))
    lines.append("")
    return lines


def render_markdown_report(
    dataset_path: Path,
    df: pd.DataFrame,
    column_groups: ColumnGroups,
    profile: Sequence[Mapping[str, Any]],
    data_quality: Mapping[str, Any],
    missing_analysis_data: Mapping[str, Any],
    duplicate_analysis_data: Mapping[str, Any],
    numeric_stats: Sequence[Mapping[str, Any]],
    categorical_stats_data: Mapping[str, Any],
    datetime_stats: Sequence[Mapping[str, Any]],
    correlation: Mapping[str, Any],
    diagnostics: Sequence[Mapping[str, Any]],
    dataset_specific: Mapping[str, Any],
    pipeline_observations: Sequence[Mapping[str, Any]],
    figures: FigurePaths,
) -> str:
    """Render the complete Markdown audit report."""

    lines: list[str] = ["# Executive Summary", ""]
    lines.append(
        markdown_table(
            executive_summary_records(
                dataset_path.name,
                df,
                column_groups,
                data_quality,
                datetime_stats,
                numeric_stats,
            ),
            [("metric", "Measure"), ("value", "Value")],
        )
    )
    lines.append("")
    lines.append("## Dataset Overview")
    lines.append("")
    lines.append(markdown_table(dataset_overview_records(df, column_groups), [("metric", "Measure"), ("value", "Value")]))
    lines.append("")
    lines.append("## Column Profile")
    lines.append("")
    lines.append(
        markdown_table(
            profile,
            [
                ("column", "Column"),
                ("data_type", "Data Type"),
                ("memory_usage", "Memory Usage"),
                ("missing_count", "Missing Count"),
                ("missing_percent", "Missing %"),
                ("unique_values", "Unique Values"),
                ("example_value", "Example Value"),
            ],
        )
    )
    lines.append("")
    lines.append("## Preview")
    lines.append("")
    lines.append("### First 5 Rows")
    lines.append("")
    lines.append(dataframe_to_markdown(df.head(PREVIEW_ROWS)))
    lines.append("")
    lines.append("### Last 5 Rows")
    lines.append("")
    lines.append(dataframe_to_markdown(df.tail(PREVIEW_ROWS)))
    lines.append("")

    lines.extend(render_data_quality_section(data_quality))
    lines.extend(render_missing_value_section(missing_analysis_data))
    lines.extend(render_duplicate_section(duplicate_analysis_data))
    lines.extend(render_numeric_statistics_section(numeric_stats))
    lines.extend(render_categorical_statistics_section(categorical_stats_data))
    lines.extend(render_datetime_analysis_section(datetime_stats))
    lines.extend(render_join_key_section(df))
    lines.extend(render_correlation_section(correlation))
    lines.extend(render_distribution_section(figures))
    lines.extend(render_time_series_diagnostics_section(diagnostics, figures))
    lines.extend(render_dataset_specific_section(dataset_specific))
    lines.extend(render_pipeline_impact_section(pipeline_observations))
    lines.extend(render_figures_section(figures))

    return "\n".join(lines).rstrip() + "\n"


def sanitize_for_json(value: Any) -> Any:
    """Convert analysis objects into deterministic JSON-serializable values."""

    if value is None:
        return None
    if isinstance(value, (str, bool, int, float)):
        return value
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, pd.Timestamp):
        return value.isoformat() if not pd.isna(value) else None
    if isinstance(value, pd.Timedelta):
        return str(value)
    if isinstance(value, np.integer):
        return int(value)
    if isinstance(value, np.floating):
        if np.isnan(value) or np.isinf(value):
            return None
        return float(value)
    if isinstance(value, Mapping):
        return {str(key): sanitize_for_json(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [sanitize_for_json(item) for item in value]
    if isinstance(value, pd.DataFrame):
        return {
            str(index): {str(column): sanitize_for_json(row[column]) for column in value.columns}
            for index, row in value.iterrows()
        }
    if isinstance(value, pd.Series):
        return [sanitize_for_json(item) for item in value.tolist()]
    if hasattr(value, "to_dict") and callable(value.to_dict):
        try:
            return sanitize_for_json(value.to_dict())
        except Exception:
            return str(value)
    return str(value)


def build_expected_preprocessing_considerations(
    dataset_name: str,
    df: pd.DataFrame,
    column_groups: ColumnGroups,
    duplicate_analysis_data: Mapping[str, Any],
    datetime_stats: Sequence[Mapping[str, Any]],
) -> list[dict[str, Any]]:
    """Create deterministic preprocessing considerations for downstream planning."""

    considerations: list[dict[str, Any]] = []
    lower_name = dataset_name.lower()

    if "baltic" in lower_name:
        considerations.extend(
            [
                {"category": "duplicate_removal", "action": "Remove duplicate rows", "priority": "high"},
                {"category": "datetime", "action": "Convert Date to datetime", "priority": "high"},
                {"category": "sorting", "action": "Sort chronologically by Date", "priority": "medium"},
            ]
        )
    elif "brent" in lower_name:
        considerations.append({"category": "datetime", "action": "Convert Date to datetime", "priority": "high"})
    elif "policy" in lower_name:
        considerations.append({"category": "datetime", "action": "Convert Date to datetime", "priority": "high"})
    elif "fao" in lower_name:
        considerations.extend(
            [
                {"category": "reshape", "action": "Pivot Long to Wide", "priority": "high"},
                {"category": "column_management", "action": "Rename indicator columns", "priority": "medium"},
            ]
        )
    elif "human" in lower_name:
        considerations.extend(
            [
                {"category": "reshape", "action": "Pivot indicator rows into columns", "priority": "high"},
                {"category": "column_management", "action": "Preserve Country and Date columns", "priority": "high"},
            ]
        )

    if duplicate_analysis_data.get("duplicate_row_count", 0) > 0:
        considerations.append({"category": "duplicate_checks", "action": "Verify duplicate removal", "priority": "medium"})
    if datetime_stats:
        considerations.append({"category": "datetime_checks", "action": "Verify datetime conversion", "priority": "medium"})
    if column_groups.numeric:
        considerations.append({"category": "schema_checks", "action": "Verify expected columns", "priority": "medium"})
    if df.shape[0] > 0:
        considerations.append({"category": "row_count_checks", "action": "Verify row counts", "priority": "medium"})

    return considerations


def build_expected_merge_considerations(
    dataset_name: str,
    candidate_join_keys: Sequence[Mapping[str, Any]],
    panel_long_dataset: bool,
) -> list[dict[str, Any]]:
    """Create deterministic merge considerations for downstream planning."""

    lower_name = dataset_name.lower()
    considerations: list[dict[str, Any]] = []
    if candidate_join_keys:
        key_names = [" + ".join(item["columns"]) for item in candidate_join_keys]
        considerations.append({"category": "join_keys", "action": "Use observed candidate join keys", "keys": key_names})
    if panel_long_dataset:
        considerations.append({"category": "panel_structure", "action": "Preserve long-format identity columns", "keys": ["Date"]})
    if "fao" in lower_name:
        considerations.append({"category": "merge_key", "action": "Merge on Date and Item Code", "keys": ["Date", "Item Code"]})
    elif "human" in lower_name:
        considerations.append({"category": "merge_key", "action": "Merge on Date and indicator dimensions", "keys": ["Date", "REF_AREA", "INDICATOR"]})
    else:
        considerations.append({"category": "merge_key", "action": "Merge on primary date column", "keys": ["Date"]})
    return considerations


def build_analysis_metadata(
    dataset_path: Path,
    df: pd.DataFrame,
    column_groups: ColumnGroups,
    profile: Sequence[Mapping[str, Any]],
    data_quality: Mapping[str, Any],
    missing_analysis_data: Mapping[str, Any],
    duplicate_analysis_data: Mapping[str, Any],
    numeric_stats: Sequence[Mapping[str, Any]],
    categorical_stats_data: Mapping[str, Any],
    datetime_stats: Sequence[Mapping[str, Any]],
    correlation: Mapping[str, Any],
    diagnostics: Sequence[Mapping[str, Any]],
    dataset_specific: Mapping[str, Any],
    pipeline_observations: Sequence[Mapping[str, Any]],
    figures: FigurePaths,
) -> dict[str, Any]:
    """Build deterministic machine-readable metadata from the same analysis objects used for reports."""

    candidate_join_keys = detect_candidate_join_keys(df)
    measurement_columns = measurement_numeric_columns(df)
    panel_long_dataset = is_long_format_dataset(df)

    correlation_matrix = correlation.get("matrix", pd.DataFrame())
    correlation_summary = {
        "measurement_numeric_columns": measurement_columns,
        "matrix": sanitize_for_json(
            {
                str(index): {str(column): sanitize_for_json(row[column]) for column in correlation_matrix.columns}
                for index, row in correlation_matrix.iterrows()
            }
        ),
        "highest_pair": sanitize_for_json(correlation.get("highest_pair")),
        "lowest_pair": sanitize_for_json(correlation.get("lowest_pair")),
    }

    return {
        "file_name": dataset_path.name,
        "dataset_name": dataset_path.stem,
        "shape": {"rows": int(df.shape[0]), "columns": int(df.shape[1])},
        "column_names": [str(column) for column in df.columns],
        "data_types": {str(column): str(dtype) for column, dtype in df.dtypes.items()},
        "column_profile": sanitize_for_json(list(profile)),
        "missing_value_analysis": sanitize_for_json(dict(missing_analysis_data)),
        "duplicate_row_analysis": {
            "duplicate_row_count": int(duplicate_analysis_data.get("duplicate_row_count", 0)),
            "duplicate_records_preview": sanitize_for_json(
                duplicate_analysis_data.get("duplicate_records_preview")
            ),
        },
        "duplicate_date_analysis": {
            "records": sanitize_for_json(duplicate_analysis_data.get("duplicate_dates", [])),
            "duplicate_dates_total": int(data_quality.get("duplicate_dates_total", 0)),
        },
        "datetime_analysis": sanitize_for_json(list(datetime_stats)),
        "frequency_analysis": sanitize_for_json(
            [{"column": record.get("column"), "estimated_frequency": record.get("estimated_frequency")} for record in datetime_stats]
        ),
        "candidate_join_keys": sanitize_for_json(list(candidate_join_keys)),
        "panel_long_dataset": bool(panel_long_dataset),
        "correlation_summary": correlation_summary,
        "summary_statistics": {
            "numeric_columns": sanitize_for_json(list(numeric_stats)),
            "categorical_columns": sanitize_for_json(dict(categorical_stats_data)),
        },
        "numeric_columns": sanitize_for_json(list(numeric_stats)),
        "categorical_columns": sanitize_for_json(dict(categorical_stats_data)),
        "time_series_diagnostics": sanitize_for_json(list(diagnostics)),
        "pipeline_observations": sanitize_for_json(list(pipeline_observations)),
        "engineering_observations": [
            {"category": "long_format", "value": bool(panel_long_dataset)},
            {"category": "measurement_numeric_columns", "value": measurement_columns},
            {"category": "datetime_columns", "value": list(column_groups.datetime)},
        ],
        "preprocessing_observations": [
            {"category": "duplicate_rows", "value": int(duplicate_analysis_data.get("duplicate_row_count", 0))},
            {"category": "missing_values", "value": int(data_quality.get("total_missing", 0))},
            {"category": "object_date_columns", "value": list(column_groups.object_date)},
            {"category": "numeric_columns", "value": list(column_groups.numeric)},
        ],
        "expected_preprocessing_considerations": sanitize_for_json(
            build_expected_preprocessing_considerations(
                dataset_path.stem,
                df,
                column_groups,
                duplicate_analysis_data,
                datetime_stats,
            )
        ),
        "expected_merge_considerations": sanitize_for_json(
            build_expected_merge_considerations(dataset_path.stem, candidate_join_keys, panel_long_dataset)
        ),
        "dataset_specific_checks": sanitize_for_json(dict(dataset_specific)),
        "data_quality": sanitize_for_json(dict(data_quality)),
        "figure_paths": {
            "missing": str(figures.missing) if figures.missing else None,
            "correlation": str(figures.correlation) if figures.correlation else None,
            "histogram": str(figures.histogram) if figures.histogram else None,
            "boxplot": str(figures.boxplot) if figures.boxplot else None,
            "time_series": str(figures.time_series) if figures.time_series else None,
        },
    }


def save_metadata_payload(metadata: Mapping[str, Any], output_path: Path) -> Path:
    """Write one JSON metadata payload to disk."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(json.dumps(metadata, indent=2, sort_keys=True), encoding="utf-8")
    logger.info("Saved analysis metadata: %s", output_path)
    return output_path


def save_report(report_text: str, output_path: Path) -> Path:
    """Write one Markdown report to disk."""

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(report_text, encoding="utf-8")
    logger.info("Saved audit report: %s", output_path)
    return output_path


def analyse_dataset(dataset_path: Path) -> Path:
    """Audit one raw CSV dataset and return its report path."""

    ensure_output_directories()
    df = load_dataset(dataset_path)
    column_groups = identify_column_groups(df)
    profile = column_profile(df)
    data_quality = data_quality_metrics(df, column_groups)
    missing_analysis_data = missing_value_analysis(df, column_groups.datetime)
    duplicate_analysis_data = duplicate_analysis(df, column_groups.datetime)
    numeric_stats = numeric_statistics(df, column_groups.numeric)
    categorical_stats_data = categorical_statistics(df, column_groups.categorical)
    datetime_stats = datetime_analysis(df, column_groups.datetime)
    correlation = correlation_analysis(df, column_groups.numeric)
    diagnostics = time_series_diagnostics(df, column_groups.datetime)
    dataset_specific = dataset_specific_checks(dataset_path.name, df)
    figures = generate_figures(df, dataset_path.stem, column_groups, correlation)
    pipeline_observations = objective_pipeline_observations(
        df,
        column_groups,
        data_quality,
        datetime_stats,
        dataset_specific,
    )

    report_text = render_markdown_report(
        dataset_path=dataset_path,
        df=df,
        column_groups=column_groups,
        profile=profile,
        data_quality=data_quality,
        missing_analysis_data=missing_analysis_data,
        duplicate_analysis_data=duplicate_analysis_data,
        numeric_stats=numeric_stats,
        categorical_stats_data=categorical_stats_data,
        datetime_stats=datetime_stats,
        correlation=correlation,
        diagnostics=diagnostics,
        dataset_specific=dataset_specific,
        pipeline_observations=pipeline_observations,
        figures=figures,
    )
    report_path = save_report(report_text, REPORT_DIR / f"{dataset_path.stem}.md")
    metadata = build_analysis_metadata(
        dataset_path=dataset_path,
        df=df,
        column_groups=column_groups,
        profile=profile,
        data_quality=data_quality,
        missing_analysis_data=missing_analysis_data,
        duplicate_analysis_data=duplicate_analysis_data,
        numeric_stats=numeric_stats,
        categorical_stats_data=categorical_stats_data,
        datetime_stats=datetime_stats,
        correlation=correlation,
        diagnostics=diagnostics,
        dataset_specific=dataset_specific,
        pipeline_observations=pipeline_observations,
        figures=figures,
    )
    save_metadata_payload(metadata, METADATA_DIR / f"{dataset_path.stem}.json")
    return report_path


def analyse_all_raw_csvs(raw_data_dir: Path = RAW_DATA_DIR) -> list[Path]:
    """Audit every CSV file in the configured raw-data directory."""

    if not raw_data_dir.exists():
        raise FileNotFoundError(f"Raw data directory does not exist: {raw_data_dir}")

    csv_files = sorted(raw_data_dir.glob("*.csv"))
    logger.info("Detected %s CSV files in %s", len(csv_files), raw_data_dir)
    reports: list[Path] = []
    for dataset_path in csv_files:
        try:
            reports.append(analyse_dataset(dataset_path))
        except Exception:
            logger.exception("Failed to audit dataset: %s", dataset_path)
            raise
    return reports


def main() -> None:
    """Command-line entry point for raw CSV audits."""

    reports = analyse_all_raw_csvs()
    for report in reports:
        logger.info("Generated report: %s", report)


if __name__ == "__main__":
    main()
