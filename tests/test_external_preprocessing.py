from __future__ import annotations

from pathlib import Path

import pandas as pd

from src.external_preprocessing import (
    preprocess_annual_to_monthly,
    preprocess_botswana_aggregate_measurements,
    preprocess_food_price_indices,
    preprocess_monthly_observation_indicators,
    preprocess_producer_price_index,
)


PROJECT_ROOT = Path(__file__).resolve().parents[1]
EXTERNAL_DATA_DIR = PROJECT_ROOT / "data" / "external"


def test_food_price_indices_recovers_real_header_and_features() -> None:
    raw = pd.read_csv(EXTERNAL_DATA_DIR / "food_price_indices_data.csv")

    processed = preprocess_food_price_indices(raw)

    assert list(processed.columns) == ["Date", "Food Price Index", "Meat", "Dairy", "Cereals", "Oils", "Sugar"]
    assert processed.duplicated(subset=["Date"]).sum() == 0
    assert processed.shape[1] > 1


def test_producer_price_index_pivots_series_codes_wide() -> None:
    raw = pd.read_excel(EXTERNAL_DATA_DIR / "Producer Price Index 2000.xlsx")

    processed = preprocess_producer_price_index(raw)

    assert "Date" == processed.columns[0]
    assert {"indicator", "series_code", "value"}.isdisjoint(processed.columns)
    assert {"PI101002", "PI101005"}.issubset(processed.columns)
    assert processed.duplicated(subset=["Date"]).sum() == 0


def test_monthly_observation_indicators_pivot_indicator_values_wide() -> None:
    raw = pd.read_csv(EXTERNAL_DATA_DIR / "ObservationData_bkgkbwg.csv")

    processed = preprocess_monthly_observation_indicators(raw)

    assert "Date" == processed.columns[0]
    assert {"indicator", "Unit", "Value"}.isdisjoint(processed.columns)
    assert "Annual Inflation, Rural Village" in processed.columns
    assert "Food_and_Non_Alcoholic_Beverages_Index" in processed.columns
    assert "Food & Non-" not in processed.columns
    assert "Alcohol" not in processed.columns
    assert processed.duplicated(subset=["Date"]).sum() == 0


def test_crop_observations_filter_botswana_and_pivot_monthly_features() -> None:
    raw = pd.read_csv(EXTERNAL_DATA_DIR / "ObservationData_dioidmb.csv")

    processed = preprocess_botswana_aggregate_measurements(
        raw,
        exclude_indicators={"Cattle", "Goats", "Sheep", "Chicken", "Pigs"},
    )

    assert "Date" == processed.columns[0]
    assert {"district", "sex", "age-group", "marital-status", "indicator", "Unit", "Value"}.isdisjoint(processed.columns)
    assert "Sorghum_Thousand Hectares" in processed.columns
    assert "Sorghum_Thousand Hectares_2" in processed.columns
    assert "Cattle_Number" not in processed.columns
    assert processed.duplicated(subset=["Date"]).sum() == 0


def test_livestock_observations_filter_botswana_and_pivot_monthly_features() -> None:
    raw = pd.read_csv(EXTERNAL_DATA_DIR / "ObservationData_qhkxkob.csv")

    processed = preprocess_botswana_aggregate_measurements(raw)

    assert "Date" == processed.columns[0]
    assert {"district", "sex", "age-group", "marital-status", "indicator", "Unit", "Value"}.isdisjoint(processed.columns)
    assert {"Cattle_Number", "Goats_Number", "Sheep_Number", "Chicken_Number", "Pigs_Number"}.issubset(processed.columns)
    assert processed.duplicated(subset=["Date"]).sum() == 0


def test_annual_to_monthly_expands_each_year_to_twelve_rows() -> None:
    raw = pd.DataFrame({"Date": [2020], "Value": [10]})

    processed = preprocess_annual_to_monthly(raw)

    assert len(processed) == 12
    assert processed["Date"].dt.month.tolist() == list(range(1, 13))
