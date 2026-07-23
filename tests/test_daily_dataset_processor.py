from __future__ import annotations

import pandas as pd

from src.daily_dataset_processor import summarize_daily_to_monthly, summarize_daily_to_weekly, summarize_weekly_to_monthly
from src.merge import build_merge_ready_dataset


def test_daily_rollup_preserves_weekly_intermediate_layer() -> None:
    daily = pd.DataFrame(
        {
            "Date": [
                "2023-01-02",
                "2023-01-03",
                "2023-01-04",
                "2023-01-05",
                "2023-01-06",
                "2023-01-09",
                "2023-01-10",
            ],
            "Value": [1.0, 3.0, 5.0, 7.0, 9.0, 11.0, 13.0],
        }
    )

    weekly = summarize_daily_to_weekly(daily)
    assert list(weekly.columns) == [
        "Date",
        "Value_mean",
        "Value_median",
        "Value_min",
        "Value_max",
        "Value_range",
        "Value_std",
        "Value_variance",
        "Value_first",
        "Value_last",
        "Value_pct_change",
        "Value_count",
    ]
    assert len(weekly) == 2

    monthly = summarize_weekly_to_monthly(weekly)
    assert len(monthly) == 1
    assert "Value_mean" in monthly.columns
    assert "Value_std" in monthly.columns
    assert "Value_count" in monthly.columns

    final_monthly = summarize_daily_to_monthly(daily)
    assert len(final_monthly) == 1
    assert final_monthly.iloc[0]["Value_mean"] == monthly.iloc[0]["Value_mean"]


def test_merge_dataset_has_no_missing_food_price_inflation_values() -> None:
    merged = build_merge_ready_dataset()

    assert "food_price_inflation" in merged.columns
    assert merged["food_price_inflation"].notna().all()


def test_merge_dataset_normalizes_mid_month_brent_dates() -> None:
    merged = build_merge_ready_dataset()

    assert "Brent_USD_per_barrel" in merged.columns
    assert merged["Date"].dt.day.eq(1).all()
    assert merged["Brent_USD_per_barrel"].notna().all()
    assert merged.loc[merged["Date"].eq(pd.Timestamp("2000-01-01")), "Brent_USD_per_barrel"].iloc[0] == 25.51


def test_merge_dataset_includes_requested_external_features() -> None:
    merged = build_merge_ready_dataset()

    expected_columns = {
        "Global_Food_Price_Index",
        "Global_Meat_Index",
        "Global_Dairy_Index",
        "Global_Cereals_Index",
        "Global_Oils_Index",
        "Global_Sugar_Index",
        "PI101002",
        "Food_and_Non_Alcoholic_Beverages_Index",
        "Imports_Food_Beverages_Tobacco",
        "Imports_Fuel",
        "Sorghum_Thousand Hectares",
        "Groundnuts_metric tonnes_2",
        "Cattle_Number",
        "Goats_Number",
        "Sheep_Number",
        "Chicken_Number",
        "Pigs_Number",
    }

    assert expected_columns.issubset(merged.columns)
    assert {"Food & Non-", "Alcohol"}.isdisjoint(merged.columns)
    assert merged.duplicated(subset=["Date"]).sum() == 0
