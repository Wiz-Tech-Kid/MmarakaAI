"""Dataset-specific preprocessing for external reference datasets."""

from __future__ import annotations

import re
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd


def _normalize_column_name(value: Any) -> str:
    text = str(value or "").strip()
    text = re.sub(r"\s+", "_", text).lower()
    return re.sub(r"[^a-z0-9]+", "_", text).strip("_")


def _parse_month_like(value: Any) -> pd.Timestamp | pd.NaT:
    if value is None or (isinstance(value, float) and np.isnan(value)):
        return pd.NaT
    if isinstance(value, pd.Timestamp):
        return value
    if isinstance(value, pd.Period):
        return value.to_timestamp()
    text = str(value).strip()
    if not text:
        return pd.NaT

    pattern_month_code = re.fullmatch(r"MO(\d{2})(\d{4})", text)
    if pattern_month_code:
        month = int(pattern_month_code.group(1))
        year = int(pattern_month_code.group(2))
        if 1 <= month <= 12:
            return pd.Timestamp(year=year, month=month, day=1)
        return pd.NaT

    if re.fullmatch(r"\d{4}M\d{1,2}", text):
        text = f"{text[:4]}-{text[5:]}"
    elif re.fullmatch(r"\d{4}-\d{2}", text):
        pass
    elif re.fullmatch(r"\d{4}", text):
        text = f"{text}-01"
    else:
        text = text.replace("/", "-")
    try:
        parsed = pd.to_datetime(text, errors="coerce")
    except Exception:
        return pd.NaT
    if pd.isna(parsed):
        return pd.NaT
    if parsed.tzinfo is not None:
        parsed = parsed.tz_convert(None)
    return parsed.to_period("M").to_timestamp()


def _coerce_numeric_frame(df: pd.DataFrame, columns: list[str]) -> pd.DataFrame:
    cleaned = df.copy()
    for column in columns:
        if column in cleaned.columns:
            cleaned[column] = pd.to_numeric(cleaned[column], errors="coerce")
    return cleaned


def _compact_label(value: Any) -> str:
    """Return a stable feature-label fragment while preserving source wording."""

    if value is None or pd.isna(value):
        return ""
    text = str(value or "").strip()
    return re.sub(r"\s+", " ", text)


def _combine_feature_label(*parts: Any) -> str:
    labels = [_compact_label(part) for part in parts if _compact_label(part)]
    return "_".join(labels)


def _add_duplicate_feature_suffixes(dataset: pd.DataFrame, feature_column: str, value_column: str) -> pd.DataFrame:
    """Preserve repeated Date/feature observations as separate wide columns."""

    cleaned = dataset.copy()
    duplicate_keys = cleaned.duplicated(subset=["Date", feature_column], keep=False)
    if not duplicate_keys.any():
        return cleaned

    ordinals = cleaned.groupby(["Date", feature_column], sort=False).cumcount()
    suffixes = (ordinals + 1).astype(str)
    cleaned.loc[duplicate_keys & ordinals.gt(0), feature_column] = (
        cleaned.loc[duplicate_keys & ordinals.gt(0), feature_column].astype(str)
        + "_"
        + suffixes.loc[duplicate_keys & ordinals.gt(0)]
    )
    cleaned[value_column] = pd.to_numeric(cleaned[value_column], errors="coerce")
    return cleaned


def _pivot_monthly_features(
    dataset: pd.DataFrame,
    *,
    feature_column: str,
    value_column: str,
    preserve_duplicate_features: bool = False,
) -> pd.DataFrame:
    cleaned = dataset.dropna(subset=["Date", feature_column, value_column]).copy()
    if cleaned.empty:
        return pd.DataFrame(columns=["Date"])

    cleaned["Date"] = cleaned["Date"].apply(_parse_month_like)
    cleaned[value_column] = pd.to_numeric(cleaned[value_column], errors="coerce")
    cleaned = cleaned.dropna(subset=["Date", value_column]).copy()
    if cleaned.empty:
        return pd.DataFrame(columns=["Date"])

    if preserve_duplicate_features:
        cleaned = _add_duplicate_feature_suffixes(cleaned, feature_column, value_column)

    feature_order = [feature for feature in pd.unique(cleaned[feature_column]) if pd.notna(feature)]
    wide = pd.pivot_table(
        cleaned,
        index="Date",
        columns=feature_column,
        values=value_column,
        aggfunc="first",
        sort=False,
    )
    wide = wide.reindex(columns=feature_order)
    wide.columns.name = None
    return wide.reset_index().sort_values("Date").reset_index(drop=True)


def _expand_annual_observations_to_monthly(dataset: pd.DataFrame) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for _, row in dataset.iterrows():
        raw_date = row.get("Date")
        parsed_date = _parse_month_like(raw_date)
        if pd.isna(parsed_date):
            continue

        raw_date_text = str(raw_date).strip()
        if re.fullmatch(r"\d{4}", raw_date_text):
            for month in range(1, 13):
                expanded = dict(row)
                expanded["Date"] = pd.Timestamp(year=parsed_date.year, month=month, day=1)
                rows.append(expanded)
        else:
            expanded = dict(row)
            expanded["Date"] = parsed_date
            rows.append(expanded)
    return pd.DataFrame(rows)


def _infer_month_date_column(df: pd.DataFrame, column_name: str = "Date") -> pd.Series:
    if column_name in df.columns:
        return df[column_name].apply(_parse_month_like)
    raise KeyError(f"Column {column_name!r} was not found in the dataset")


def preprocess_bank_of_botswana_exchange_rates(dataset: pd.DataFrame) -> pd.DataFrame:
    cleaned = dataset.copy()
    cleaned.columns = [str(column).strip() for column in cleaned.columns]
    if "Date" not in cleaned.columns:
        raise KeyError("Date column not found for exchange-rate preprocessing")

    cleaned = cleaned.dropna(subset=["Date"]).copy()
    cleaned["Date"] = pd.to_datetime(cleaned["Date"], errors="coerce")
    cleaned = cleaned.dropna(subset=["Date"]).copy()
    cleaned = cleaned.sort_values("Date").reset_index(drop=True)

    numeric_columns = [column for column in cleaned.columns if column != "Date" and pd.api.types.is_numeric_dtype(cleaned[column])]
    if not numeric_columns:
        numeric_columns = [column for column in cleaned.columns if column != "Date"]
    cleaned = _coerce_numeric_frame(cleaned, numeric_columns)

    cleaned["week_start"] = cleaned["Date"] - pd.to_timedelta(cleaned["Date"].dt.dayofweek, unit="D")
    cleaned["week_start"] = cleaned["week_start"].dt.normalize()

    weekly_groups = cleaned.groupby("week_start", sort=True)
    weekly_rows: list[dict[str, Any]] = []
    for week_start, frame in weekly_groups:
        row: dict[str, Any] = {"Date": week_start}
        for column in numeric_columns:
            values = frame[column].dropna()
            if values.empty:
                continue
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
            row[f"{column}_mean"] = mean_value
            row[f"{column}_median"] = median_value
            row[f"{column}_min"] = min_value
            row[f"{column}_max"] = max_value
            row[f"{column}_range"] = range_value
            row[f"{column}_std"] = std_value
            row[f"{column}_variance"] = variance_value
            row[f"{column}_first"] = first_value
            row[f"{column}_last"] = last_value
            row[f"{column}_pct_change"] = pct_change_value
            row[f"{column}_count"] = int(values.count())
        weekly_rows.append(row)

    weekly_frame = pd.DataFrame(weekly_rows)
    if weekly_frame.empty:
        return pd.DataFrame(columns=["Date"])

    monthly_groups = weekly_frame.groupby(weekly_frame["Date"].dt.to_period("M"), sort=True)
    monthly_rows: list[dict[str, Any]] = []
    metric_columns = [column for column in weekly_frame.columns if column != "Date" and pd.api.types.is_numeric_dtype(weekly_frame[column])]
    metric_prefixes = sorted({column.rsplit("_", 1)[0] for column in metric_columns})

    for month_period, frame in monthly_groups:
        row: dict[str, Any] = {"Date": month_period.to_timestamp()}
        for prefix in metric_prefixes:
            stats_map = {
                metric: frame[f"{prefix}_{metric}"]
                for metric in ["mean", "median", "min", "max", "range", "std", "variance", "first", "last", "pct_change", "count"]
                if f"{prefix}_{metric}" in frame.columns
            }
            if not stats_map:
                continue

            for metric, series in stats_map.items():
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

    monthly_frame = pd.DataFrame(monthly_rows).sort_values("Date").reset_index(drop=True)
    return monthly_frame


def preprocess_food_price_indices(dataset: pd.DataFrame) -> pd.DataFrame:
    cleaned = dataset.copy()
    if cleaned.shape[1] < 2:
        return cleaned
    cleaned.columns = [str(column).strip() for column in cleaned.columns]
    cleaned = cleaned.dropna(how="all")
    if cleaned.empty:
        return pd.DataFrame(columns=["Date"])

    header_index: Any | None = None
    header_labels: list[str] = []
    for row_index, row in cleaned.iterrows():
        labels = [_compact_label(value) for value in row.tolist()]
        if "Date" in labels and any(label in {"Food Price Index", "Meat", "Dairy", "Cereals", "Oils", "Sugar"} for label in labels):
            header_index = row_index
            header_labels = labels
            break

    if header_index is not None:
        keep_positions = [idx for idx, label in enumerate(header_labels) if label]
        cleaned = cleaned.iloc[cleaned.index.get_loc(header_index) + 1 :, keep_positions].copy()
        cleaned.columns = [header_labels[idx] for idx in keep_positions]
    elif "Date" not in cleaned.columns:
        first_column = cleaned.columns[0]
        cleaned = cleaned.rename(columns={first_column: "Date"})

    if "Date" not in cleaned.columns:
        return pd.DataFrame(columns=["Date"])

    cleaned = cleaned.dropna(subset=["Date"]).copy()
    cleaned["Date"] = cleaned["Date"].apply(_parse_month_like)
    cleaned = cleaned.dropna(subset=["Date"]).copy()
    cleaned = cleaned.sort_values("Date").reset_index(drop=True)

    numeric_columns = []
    for column in cleaned.columns:
        if column == "Date":
            continue
        numeric_values = pd.to_numeric(cleaned[column], errors="coerce")
        if numeric_values.notna().any():
            cleaned[column] = numeric_values
            numeric_columns.append(column)
    cleaned = _coerce_numeric_frame(cleaned, numeric_columns)
    cleaned = cleaned.drop_duplicates(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    return cleaned[["Date", *numeric_columns]]


def preprocess_producer_price_index(dataset: pd.DataFrame) -> pd.DataFrame:
    cleaned = dataset.copy()
    cleaned.columns = [str(column).strip() if column is not None else "" for column in cleaned.columns]
    cleaned = cleaned.dropna(how="all")
    if cleaned.empty:
        return pd.DataFrame(columns=["Date", "indicator", "value"])
    header_row = cleaned.iloc[0].tolist()
    if len(header_row) < 9:
        return pd.DataFrame(columns=["Date", "indicator", "value"])

    month_labels = [value for value in header_row[8:] if pd.notna(value)]
    if not month_labels:
        return pd.DataFrame(columns=["Date", "indicator", "value"])

    month_dates: list[pd.Timestamp] = []
    for label in month_labels:
        parsed_month = _parse_month_like(label)
        if pd.isna(parsed_month):
            month_dates.append(pd.NaT)
        else:
            month_dates.append(parsed_month)

    rows = []
    for _, row in cleaned.iloc[1:].iterrows():
        if len(row) < 9:
            continue
        series_name = str(row.iloc[4]).strip() if len(row) > 4 else ""
        code = str(row.iloc[2]).strip() if len(row) > 2 else ""
        values = [row.iloc[i] for i in range(8, min(len(row), 8 + len(month_labels)))]
        if not any(pd.notna(value) for value in values):
            continue
        if any(token in series_name.lower() for token in ["all groups", "forestry", "fishing", "mining"]):
            continue
        if not any(token in series_name.lower() for token in ["agriculture", "food", "animal", "grain", "vegetables", "fruits", "oil", "sugar", "milk", "eggs"]):
            continue
        for month_date, value in zip(month_dates, values):
            if pd.isna(month_date) or pd.isna(value):
                continue
            rows.append({"Date": month_date, "indicator": series_name, "series_code": code, "value": pd.to_numeric(value, errors="coerce")})

    if not rows:
        return pd.DataFrame(columns=["Date", "indicator", "value", "series_code"])
    result = pd.DataFrame(rows).dropna(subset=["value"]).sort_values(["Date", "series_code"]).reset_index(drop=True)
    return _pivot_monthly_features(result, feature_column="series_code", value_column="value")


def preprocess_imports_table(dataset: pd.DataFrame) -> pd.DataFrame:
    cleaned = dataset.copy()
    cleaned.columns = [str(column).strip() if column is not None else "" for column in cleaned.columns]
    cleaned = cleaned.dropna(how="all")
    if cleaned.empty:
        return pd.DataFrame(columns=["Date", "Imports_Food_Beverages_Tobacco", "Imports_Fuel"])

    if cleaned.shape[1] >= 7:
        month_names = {
            "jan": 1,
            "feb": 2,
            "mar": 3,
            "apr": 4,
            "may": 5,
            "jun": 6,
            "jul": 7,
            "aug": 8,
            "sep": 9,
            "oct": 10,
            "nov": 11,
            "dec": 12,
        }
        quarter_months = {
            "q1": [1, 2, 3],
            "q2": [4, 5, 6],
            "q3": [7, 8, 9],
            "q4": [10, 11, 12],
        }

        records: list[dict[str, Any]] = []
        current_year: int | None = None
        for row in cleaned.itertuples(index=False, name=None):
            if len(row) < 7:
                continue

            year_value = row[0]
            if pd.notna(year_value):
                year = pd.to_numeric(year_value, errors="coerce")
                if pd.isna(year):
                    continue
                current_year = int(year)

            if current_year is None:
                continue

            label = str(row[1]).strip() if len(row) > 1 else ""
            fuel_value = pd.to_numeric(row[3], errors="coerce") if len(row) > 3 else np.nan
            food_value = pd.to_numeric(row[6], errors="coerce") if len(row) > 6 else np.nan

            if pd.isna(fuel_value) and pd.isna(food_value):
                continue

            label_key = label.lower() if label else ""
            if not label_key:
                months = list(range(1, 13))
                for month in months:
                    records.append(
                        {
                            "Date": pd.Timestamp(year=current_year, month=month, day=1),
                            "Imports_Food_Beverages_Tobacco": float(food_value / 12.0) if pd.notna(food_value) else np.nan,
                            "Imports_Fuel": float(fuel_value / 12.0) if pd.notna(fuel_value) else np.nan,
                        }
                    )
                continue

            if label_key in quarter_months:
                for month in quarter_months[label_key]:
                    records.append(
                        {
                            "Date": pd.Timestamp(year=current_year, month=month, day=1),
                            "Imports_Food_Beverages_Tobacco": float(food_value / 3.0) if pd.notna(food_value) else np.nan,
                            "Imports_Fuel": float(fuel_value / 3.0) if pd.notna(fuel_value) else np.nan,
                        }
                    )
                continue

            month_number = month_names.get(label_key)
            if month_number is None:
                continue
            records.append(
                {
                    "Date": pd.Timestamp(year=current_year, month=month_number, day=1),
                    "Imports_Food_Beverages_Tobacco": float(food_value) if pd.notna(food_value) else np.nan,
                    "Imports_Fuel": float(fuel_value) if pd.notna(fuel_value) else np.nan,
                }
            )

        if records:
            result = pd.DataFrame(records)
            result = result.dropna(subset=["Date"]).drop_duplicates(subset=["Date"]).sort_values("Date").reset_index(drop=True)
            result = result[["Date", "Imports_Food_Beverages_Tobacco", "Imports_Fuel"]]
            if result.shape[1] == 3:
                return result

    return pd.DataFrame(columns=["Date", "Imports_Food_Beverages_Tobacco", "Imports_Fuel"])


def preprocess_consumer_price_index(dataset: pd.DataFrame) -> pd.DataFrame:
    cleaned = dataset.copy()
    cleaned.columns = [str(column).strip() if column is not None else "" for column in cleaned.columns]
    cleaned = cleaned.dropna(how="all")
    if cleaned.empty:
        return pd.DataFrame(columns=["Date", "headline_cpi", "imported_tradeables_inflation", "food_inflation", "core_inflation"])

    rows = []
    for row in cleaned.itertuples(index=False, name=None):
        date_value = row[0] if len(row) > 0 else None
        if pd.isna(date_value):
            continue
        parsed_date = _parse_month_like(date_value)
        if pd.isna(parsed_date):
            continue
        values = [row[idx] for idx in range(1, min(len(row), 10))]
        if not any(pd.notna(value) for value in values):
            continue
        rows.append({
            "Date": parsed_date,
            "headline_cpi": pd.to_numeric(row[1], errors="coerce") if len(row) > 1 else np.nan,
            "imported_tradeables_inflation": pd.to_numeric(row[7], errors="coerce") if len(row) > 7 else np.nan,
            "food_inflation": pd.to_numeric(row[2], errors="coerce") if len(row) > 2 else np.nan,
            "core_inflation": pd.to_numeric(row[8], errors="coerce") if len(row) > 8 else np.nan,
        })
    if not rows:
        return pd.DataFrame(columns=["Date", "headline_cpi", "imported_tradeables_inflation", "food_inflation", "core_inflation"])
    result = pd.DataFrame(rows).dropna(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    return result


def preprocess_fao_botswana_prices(dataset: pd.DataFrame) -> pd.DataFrame:
    cleaned = dataset.copy()
    cleaned.columns = [str(column).strip() if column is not None else "" for column in cleaned.columns]
    cleaned = cleaned.dropna(how="all")
    if cleaned.empty:
        return pd.DataFrame(columns=["Date", "Consumer Prices, Food Indices (2015 = 100)", "Consumer Prices, General Indices (2015 = 100)", "Food price inflation"])

    required_columns = {"Date", "Item", "Value"}
    if not required_columns.issubset(cleaned.columns):
        return cleaned.copy()

    cleaned = cleaned.dropna(subset=["Date", "Item", "Value"]).copy()
    cleaned["Date"] = cleaned["Date"].apply(_parse_month_like)
    cleaned = cleaned.dropna(subset=["Date"]).copy()
    cleaned["Value"] = pd.to_numeric(cleaned["Value"], errors="coerce")
    cleaned = cleaned.dropna(subset=["Value"]).copy()

    wide = pd.pivot_table(cleaned, index="Date", columns="Item", values="Value", aggfunc="first")
    wide = wide.reset_index().sort_values("Date").reset_index(drop=True)

    if "Consumer Prices, Food Indices (2015 = 100)" in wide.columns and "Food price inflation" not in wide.columns:
        wide["Food price inflation"] = wide["Consumer Prices, Food Indices (2015 = 100)"].pct_change(12) * 100

    if "Food price inflation" in wide.columns:
        wide["Food price inflation"] = pd.to_numeric(wide["Food price inflation"], errors="coerce")
        wide["Food price inflation"] = wide["Food price inflation"].bfill().ffill()

    ordered_columns = [
        "Date",
        "Consumer Prices, Food Indices (2015 = 100)",
        "Consumer Prices, General Indices (2015 = 100)",
        "Food price inflation",
    ]
    available_columns = [column for column in ordered_columns if column in wide.columns]
    extra_columns = [column for column in wide.columns if column not in available_columns]
    return wide[available_columns + extra_columns].reset_index(drop=True)


def preprocess_annual_to_monthly(dataset: pd.DataFrame, value_column: str = "Value") -> pd.DataFrame:
    cleaned = dataset.copy()
    if "Date" not in cleaned.columns:
        raise KeyError("Date column not found for annual-to-monthly preprocessing")
    cleaned = cleaned.dropna(subset=["Date"]).copy()
    cleaned["Date"] = cleaned["Date"].apply(_parse_month_like)
    cleaned = cleaned.dropna(subset=["Date"]).copy()
    cleaned[value_column] = pd.to_numeric(cleaned[value_column], errors="coerce")
    cleaned = cleaned.dropna(subset=[value_column])
    cleaned = cleaned.drop_duplicates(subset=["Date", *[col for col in cleaned.columns if col not in {"Date", value_column}]])
    rows: list[dict[str, Any]] = []
    for _, row in cleaned.iterrows():
        year = row["Date"].year
        for month in range(1, 13):
            expanded = dict(row)
            expanded["Date"] = pd.Timestamp(year=year, month=month, day=1)
            rows.append(expanded)
    return pd.DataFrame(rows).sort_values("Date").reset_index(drop=True)


def preprocess_monthly_observation_indicators(dataset: pd.DataFrame) -> pd.DataFrame:
    cleaned = dataset.copy()
    cleaned.columns = [str(column).strip() if column is not None else "" for column in cleaned.columns]
    required_columns = {"indicator", "Unit", "Date", "Value"}
    if not required_columns.issubset(cleaned.columns):
        return cleaned.copy()

    cleaned = cleaned.dropna(subset=["indicator", "Date", "Value"]).copy()
    indicator_labels = set(cleaned["indicator"].apply(_compact_label))
    if {"Food & Non-", "Alcohol"}.issubset(indicator_labels):
        cleaned = cleaned[cleaned["indicator"].apply(_compact_label) != "Alcohol"].copy()
        cleaned.loc[
            cleaned["indicator"].apply(_compact_label) == "Food & Non-",
            "indicator",
        ] = "Food_and_Non_Alcoholic_Beverages_Index"
    cleaned["Value"] = pd.to_numeric(cleaned["Value"], errors="coerce")
    cleaned = cleaned.dropna(subset=["Value"]).copy()
    if cleaned.empty:
        return pd.DataFrame(columns=["Date"])

    unit_counts = cleaned.groupby("indicator", dropna=False)["Unit"].nunique(dropna=True)
    multi_unit_indicators = set(unit_counts[unit_counts.gt(1)].index)

    if multi_unit_indicators:
        cleaned["feature_name"] = cleaned.apply(
            lambda row: _combine_feature_label(row["indicator"], row["Unit"])
            if row["indicator"] in multi_unit_indicators
            else _compact_label(row["indicator"]),
            axis=1,
        )
    else:
        cleaned["feature_name"] = cleaned["indicator"].apply(_compact_label)

    return _pivot_monthly_features(cleaned, feature_column="feature_name", value_column="Value")


def preprocess_botswana_aggregate_measurements(
    dataset: pd.DataFrame,
    *,
    exclude_indicators: set[str] | None = None,
) -> pd.DataFrame:
    cleaned = dataset.copy()
    cleaned.columns = [str(column).strip() if column is not None else "" for column in cleaned.columns]
    required_columns = {"district", "indicator", "Unit", "Date", "Value"}
    if not required_columns.issubset(cleaned.columns):
        return preprocess_annual_to_monthly(cleaned, value_column="Value")

    cleaned = cleaned.dropna(subset=["district", "indicator", "Unit", "Date", "Value"]).copy()
    cleaned = cleaned[cleaned["district"].astype(str).str.strip().eq("Botswana")].copy()
    if exclude_indicators:
        excluded = {_compact_label(indicator) for indicator in exclude_indicators}
        cleaned = cleaned[~cleaned["indicator"].apply(_compact_label).isin(excluded)].copy()
    if cleaned.empty:
        return pd.DataFrame(columns=["Date"])

    cleaned["Value"] = pd.to_numeric(cleaned["Value"], errors="coerce")
    cleaned = cleaned.dropna(subset=["Value"]).copy()
    cleaned["feature_name"] = cleaned.apply(lambda row: _combine_feature_label(row["indicator"], row["Unit"]), axis=1)
    monthly = _expand_annual_observations_to_monthly(cleaned)
    return _pivot_monthly_features(
        monthly,
        feature_column="feature_name",
        value_column="Value",
        preserve_duplicate_features=True,
    )


def preprocess_exchange_rate_table(dataset: pd.DataFrame) -> pd.DataFrame:
    cleaned = dataset.copy()
    cleaned.columns = [str(column).strip() if column is not None else "" for column in cleaned.columns]
    cleaned = cleaned.dropna(how="all")
    if cleaned.empty:
        return pd.DataFrame(columns=["Date", "series", "value"])
    rows = []
    for row in cleaned.itertuples(index=False, name=None):
        first_cell = str(row[0]).strip() if len(row) > 0 else ""
        if re.fullmatch(r"\d{4}", first_cell):
            year = int(first_cell)
            base = pd.Timestamp(year=year, month=1, day=1)
            for idx in range(1, len(row)):
                label = str(row[idx]).strip() if len(row) > idx else ""
                value = row[idx]
                if pd.isna(value):
                    continue
                if not re.search(r"\d", str(value)):
                    continue
                rows.append({"Date": base, "series": label, "value": pd.to_numeric(value, errors="coerce")})
    if not rows:
        return pd.DataFrame(columns=["Date", "series", "value"])
    result = pd.DataFrame(rows).dropna(subset=["value"]).sort_values(["series", "Date"]).reset_index(drop=True)
    return result


def preprocess_real_exchange_rate_index(dataset: pd.DataFrame) -> pd.DataFrame:
    cleaned = dataset.copy()
    cleaned.columns = [str(column).strip() if column is not None else "" for column in cleaned.columns]
    cleaned = cleaned.dropna(how="all")
    if cleaned.empty:
        return pd.DataFrame(columns=["Date", "series", "value"])

    rows = []
    for row in cleaned.itertuples(index=False, name=None):
        first_cell = str(row[0]).strip() if len(row) > 0 else ""
        if re.fullmatch(r"\d{4}", first_cell):
            year = int(first_cell)
            base = pd.Timestamp(year=year, month=1, day=1)
            for idx in range(2, len(row)):
                label = str(row[idx]).strip() if len(row) > idx else ""
                value = row[idx]
                if pd.isna(value):
                    continue
                if not re.search(r"\d", str(value)):
                    continue
                rows.append({"Date": base, "series": label, "value": pd.to_numeric(value, errors="coerce")})
    if not rows:
        return pd.DataFrame(columns=["Date", "series", "value"])
    result = pd.DataFrame(rows).dropna(subset=["value"]).sort_values(["series", "Date"]).reset_index(drop=True)
    return result


def preprocess_external_dataset(dataset_name: str, dataset: pd.DataFrame, source_path: str | Path | None = None) -> pd.DataFrame:
    """Apply dataset-specific preprocessing based on the dataset filename."""

    name = str(dataset_name).lower()
    if "04_fao_botswana_prices" in name or "fao_botswana_prices" in name:
        return preprocess_fao_botswana_prices(dataset)
    if "bank-of-botswana-exchange-rates" in name:
        return preprocess_bank_of_botswana_exchange_rates(dataset)
    if "food_price_indices" in name:
        return preprocess_food_price_indices(dataset)
    if "producer_price_index" in name or "producer price index" in name:
        return preprocess_producer_price_index(dataset)
    if "6-16" in name or "imports" in name:
        return preprocess_imports_table(dataset)
    if "consumer_price_index" in name or "consumer price index" in name:
        return preprocess_consumer_price_index(dataset)
    if "observationdata_dioidmb" in name or "dioidmb" in name:
        return preprocess_botswana_aggregate_measurements(
            dataset,
            exclude_indicators={"Cattle", "Goats", "Sheep", "Chicken", "Pigs"},
        )
    if "observationdata_qhkxkob" in name or "qhkxkob" in name:
        return preprocess_botswana_aggregate_measurements(dataset)
    if "total number" in name or "totalnumber" in name:
        return preprocess_annual_to_monthly(dataset, value_column="Value")
    if "f6-10" in name:
        return preprocess_exchange_rate_table(dataset)
    if "f6-13" in name:
        return preprocess_real_exchange_rate_index(dataset)
    if "observationdata_bkgkbwg" in name or "bkgkbwg" in name:
        return preprocess_monthly_observation_indicators(dataset)
    return dataset.copy()
