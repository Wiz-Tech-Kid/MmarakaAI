from __future__ import annotations

from pathlib import Path

import pandas as pd

PROJECT_ROOT = Path(__file__).resolve().parents[1]
DATA_PROCESSED_DIR = PROJECT_ROOT / "data" / "processed"
OUTPUT_PROCESSED_DIR = PROJECT_ROOT / "output" / "processed"
OUTPUT_EXT_PROCESSED_DIR = PROJECT_ROOT / "output" / "ext" / "processed"
MERGED_OUTPUT_DIR = PROJECT_ROOT / "data" / "merged"

MASTER_DATASET = DATA_PROCESSED_DIR / "04_fao_botswana_prices_processed.csv"
JOIN_DATASETS = [
    DATA_PROCESSED_DIR / "02_brent_crude_monthly_processed.csv",
    DATA_PROCESSED_DIR / "03_botswana_policy_rate_processed.csv",
    DATA_PROCESSED_DIR / "01_baltic_dry_index_monthly_processed.csv",
    DATA_PROCESSED_DIR / "bank-of-botswana-exchange-rates_processed.csv",
    OUTPUT_PROCESSED_DIR / "Botswana Consumer Price Index_processed.csv",
]

GLOBAL_FOOD_INDEX_RENAMES = {
    "Food Price Index": "Global_Food_Price_Index",
    "Meat": "Global_Meat_Index",
    "Dairy": "Global_Dairy_Index",
    "Cereals": "Global_Cereals_Index",
    "Oils": "Global_Oils_Index",
    "Sugar": "Global_Sugar_Index",
}

REQUESTED_EXTERNAL_JOINS = [
    {
        "path": OUTPUT_EXT_PROCESSED_DIR / "food_price_indices_data_processed.csv",
        "columns": list(GLOBAL_FOOD_INDEX_RENAMES),
        "rename": GLOBAL_FOOD_INDEX_RENAMES,
    },
    {"path": OUTPUT_EXT_PROCESSED_DIR / "Producer Price Index 2000_processed.csv"},
    {"path": OUTPUT_EXT_PROCESSED_DIR / "ObservationData_bkgkbwg_processed.csv"},
    {
        "path": OUTPUT_EXT_PROCESSED_DIR / "6-16_processed.csv",
        "columns": ["Imports_Food_Beverages_Tobacco", "Imports_Fuel"],
    },
    {"path": OUTPUT_EXT_PROCESSED_DIR / "ObservationData_dioidmb_processed.csv"},
    {
        "path": OUTPUT_EXT_PROCESSED_DIR / "ObservationData_qhkxkob_processed.csv",
        "columns": ["Cattle_Number", "Goats_Number", "Sheep_Number", "Chicken_Number", "Pigs_Number"],
    },
]


def _load_monthly_frame(path: Path) -> pd.DataFrame:
    frame = pd.read_csv(path)
    if "Date" not in frame.columns:
        raise KeyError(f"Expected 'Date' in {path.name}")
    frame = frame.copy()
    parsed_dates = pd.to_datetime(frame["Date"], errors="coerce")
    frame["Date"] = parsed_dates.dt.to_period("M").dt.to_timestamp()
    frame = frame.dropna(subset=["Date"]).drop_duplicates(subset=["Date"]).sort_values("Date").reset_index(drop=True)
    return frame


def _prepare_join_frame(path: Path, columns: list[str] | None = None, rename: dict[str, str] | None = None) -> pd.DataFrame:
    frame = _load_monthly_frame(path)
    if columns is not None:
        missing_columns = [column for column in columns if column not in frame.columns]
        if missing_columns:
            raise KeyError(f"{path.name} is missing expected columns: {missing_columns}")
        frame = frame[["Date", *columns]].copy()
    if rename:
        frame = frame.rename(columns=rename)
    return frame


def _left_join_monthly_features(
    merged: pd.DataFrame,
    path: Path,
    columns: list[str] | None = None,
    rename: dict[str, str] | None = None,
) -> pd.DataFrame:
    join_frame = _prepare_join_frame(path, columns=columns, rename=rename)
    overlapping_columns = (set(merged.columns) & set(join_frame.columns)) - {"Date"}
    if overlapping_columns:
        raise ValueError(f"{path.name} would create duplicate columns: {sorted(overlapping_columns)}")
    return merged.merge(join_frame, on="Date", how="left")


def build_merge_ready_dataset() -> pd.DataFrame:
    """Create the requested monthly master table by left-joining all processed monthly datasets on Date."""

    master = _load_monthly_frame(MASTER_DATASET)
    master = master.rename(
        columns={
            "Consumer Prices, Food Indices (2015 = 100)": "food_index",
            "Consumer Prices, General Indices (2015 = 100)": "general_index",
            "Food price inflation": "food_price_inflation",
        }
    )

    merged = master.copy()
    for dataset_path in JOIN_DATASETS:
        merged = _left_join_monthly_features(merged, dataset_path)

    for join_spec in REQUESTED_EXTERNAL_JOINS:
        merged = _left_join_monthly_features(
            merged,
            join_spec["path"],
            columns=join_spec.get("columns"),
            rename=join_spec.get("rename"),
        )

    merged = merged.sort_values("Date").reset_index(drop=True)
    return merged


def main() -> None:
    MERGED_OUTPUT_DIR.mkdir(parents=True, exist_ok=True)
    merged = build_merge_ready_dataset()
    output_path = MERGED_OUTPUT_DIR / "merged_modeling_dataset.csv"
    merged.to_csv(output_path, index=False)
    print(f"Saved merged dataset to: {output_path}")
    print(f"Rows: {len(merged)}")
    print(f"Columns: {len(merged.columns)}")


if __name__ == "__main__":
    main()
