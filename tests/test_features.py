from __future__ import annotations

import pandas as pd

from src.features import (
    STAGE1_LAG_PERIODS,
    STAGE3_ROLLING_WINDOWS,
    build_stage1_lag_dataset,
    build_stage2_percentage_change_dataset,
    build_stage3_rolling_statistics_dataset,
    build_stage4_seasonal_dataset,
    build_stage5_trend_dataset,
    build_stage6_interaction_dataset,
    build_mmarakai_feature_matrix,
    create_interaction_features,
    create_mmarakai_feature_matrix,
    create_lag_features,
    create_percentage_change_features,
    create_rolling_statistics_features,
    create_seasonal_features,
    create_trend_features,
    select_interaction_pairs,
    select_percentage_change_predictor_columns,
    select_rolling_statistic_predictor_columns,
    select_stage_engineered_feature_columns,
    select_trend_predictor_columns,
    select_numeric_predictor_columns,
)


def test_create_lag_features_sorts_dates_and_uses_only_history() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2020-03-01", "2020-01-01", "2020-02-01", "2020-04-01"],
            "food_price_inflation": [30.0, 10.0, 20.0, 40.0],
            "USD_mean": [3.0, 1.0, 2.0, 4.0],
            "category": ["c", "a", "b", "d"],
        }
    )

    engineered = create_lag_features(raw, lags=(1, 2))

    assert engineered["Date"].dt.strftime("%Y-%m-%d").tolist() == [
        "2020-01-01",
        "2020-02-01",
        "2020-03-01",
        "2020-04-01",
    ]
    assert "food_price_inflation_lag1" not in engineered.columns
    assert "category_lag1" not in engineered.columns
    assert engineered["USD_mean"].tolist() == [1.0, 2.0, 3.0, 4.0]
    assert pd.isna(engineered.loc[0, "USD_mean_lag1"])
    assert engineered["USD_mean_lag1"].tolist()[1:] == [1.0, 2.0, 3.0]
    assert pd.isna(engineered.loc[0, "USD_mean_lag2"])
    assert pd.isna(engineered.loc[1, "USD_mean_lag2"])
    assert engineered["USD_mean_lag2"].tolist()[2:] == [1.0, 2.0]
    assert len(engineered) == len(raw)


def test_select_numeric_predictors_excludes_date_and_target() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2020-01-01"],
            "food_price_inflation": [1.0],
            "food_inflation": [2.0],
            "Global_Food_Price_Index": [3.0],
            "label": ["x"],
        }
    )

    predictors = select_numeric_predictor_columns(raw)

    assert predictors == ["food_inflation", "Global_Food_Price_Index"]


def test_build_stage1_lag_dataset_preserves_rows_and_adds_exact_lags(tmp_path) -> None:
    output_path = tmp_path / "stage1_lag_features.csv"

    summary = build_stage1_lag_dataset(output_path=output_path)
    engineered = pd.read_csv(output_path)
    original = pd.read_csv("data/merged/merged_modeling_dataset.csv")
    predictors = select_numeric_predictor_columns(original)

    assert summary.rows == len(original)
    assert len(engineered) == len(original)
    assert summary.lag_periods == STAGE1_LAG_PERIODS
    assert summary.lag_feature_count == len(predictors) * len(STAGE1_LAG_PERIODS)
    assert len(engineered.columns) == len(original.columns) + summary.lag_feature_count
    assert "food_price_inflation_lag1" not in engineered.columns
    assert "Global_Food_Price_Index_lag12" in engineered.columns
    assert "USD_mean_lag6" in engineered.columns
    assert engineered["Global_Food_Price_Index_lag1"].isna().iloc[0]
    assert engineered.loc[1, "Global_Food_Price_Index_lag1"] == original.loc[0, "Global_Food_Price_Index"]
    assert engineered.duplicated(subset=["Date"]).sum() == 0


def test_create_percentage_change_features_uses_previous_month_only() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2020-03-01", "2020-01-01", "2020-02-01"],
            "food_price_inflation": [3.0, 1.0, 2.0],
            "USD_mean": [121.0, 100.0, 110.0],
            "policy_rate": [6.0, 5.0, 5.5],
            "USD_mean_lag1": [110.0, 90.0, 100.0],
            "label": ["c", "a", "b"],
        }
    )

    engineered = create_percentage_change_features(raw)

    assert engineered["Date"].tolist() == ["2020-01-01", "2020-02-01", "2020-03-01"]
    assert "food_price_inflation_pct_change" not in engineered.columns
    assert "label_pct_change" not in engineered.columns
    assert "USD_mean_lag1_pct_change" not in engineered.columns
    assert pd.isna(engineered.loc[0, "USD_mean_pct_change"])
    assert engineered.loc[1, "USD_mean_pct_change"] == 0.1
    assert engineered.loc[2, "USD_mean_pct_change"] == 0.1
    assert engineered.loc[1, "policy_rate_pct_change"] == 0.1
    assert len(engineered) == len(raw)


def test_select_percentage_change_predictors_uses_requested_groups_only() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2020-01-01"],
            "food_price_inflation": [1.0],
            "BDI_Close_mean": [2.0],
            "Brent_USD_per_barrel": [3.0],
            "Global_Food_Price_Index": [4.0],
            "USD_mean": [5.0],
            "policy_rate": [6.0],
            "headline_cpi": [7.0],
            "PI101001": [8.0],
            "Inflation (%)": [9.0],
            "Imports_Fuel": [10.0],
            "Sorghum_Thousand Hectares": [11.0],
            "Cattle_Number": [12.0],
            "SEI00003": [13.0],
            "random_numeric": [14.0],
            "BDI_Close_mean_lag1": [15.0],
        }
    )

    predictors = select_percentage_change_predictor_columns(raw)

    assert predictors == [
        "BDI_Close_mean",
        "Brent_USD_per_barrel",
        "Global_Food_Price_Index",
        "USD_mean",
        "policy_rate",
        "headline_cpi",
        "PI101001",
        "Inflation (%)",
        "Imports_Fuel",
        "Sorghum_Thousand Hectares",
        "Cattle_Number",
    ]


def test_build_stage2_percentage_change_dataset_preserves_originals_and_rows(tmp_path) -> None:
    output_path = tmp_path / "stage2_percentage_change_features.csv"

    summary = build_stage2_percentage_change_dataset(output_path=output_path)
    engineered = pd.read_csv(output_path)
    original = pd.read_csv("data/merged/merged_modeling_dataset.csv")
    predictors = select_percentage_change_predictor_columns(original)

    assert summary.rows == len(original)
    assert len(engineered) == len(original)
    assert summary.percentage_change_feature_count == len(predictors)
    assert len(engineered.columns) == len(original.columns) + len(predictors)
    assert list(engineered.columns[: len(original.columns)]) == list(original.columns)
    assert "food_price_inflation_pct_change" not in engineered.columns
    assert "Date_pct_change" not in engineered.columns
    assert "Global_Food_Price_Index_pct_change" in engineered.columns
    assert "PI101001_pct_change" in engineered.columns
    assert "SEI00003_pct_change" not in engineered.columns
    assert engineered["Global_Food_Price_Index_pct_change"].isna().iloc[0]
    expected = (original.loc[1, "Global_Food_Price_Index"] - original.loc[0, "Global_Food_Price_Index"]) / original.loc[0, "Global_Food_Price_Index"]
    assert abs(engineered.loc[1, "Global_Food_Price_Index_pct_change"] - expected) < 1e-12
    assert engineered.duplicated(subset=["Date"]).sum() == 0


def test_create_rolling_statistics_features_uses_requested_groups_and_full_windows() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2020-04-01", "2020-01-01", "2020-02-01", "2020-03-01"],
            "food_price_inflation": [4.0, 1.0, 2.0, 3.0],
            "USD_mean": [140.0, 100.0, 110.0, 121.0],
            "policy_rate": [8.0, 5.0, 6.0, 7.0],
            "Sorghum_Thousand Hectares": [40.0, 10.0, 20.0, 30.0],
            "Cattle_Number": [400.0, 100.0, 200.0, 300.0],
            "USD_mean_lag1": [121.0, 90.0, 100.0, 110.0],
            "USD_mean_pct_change": [0.1, None, 0.1, 0.1],
            "label": ["d", "a", "b", "c"],
        }
    )

    engineered = create_rolling_statistics_features(raw, windows=(3,))

    assert engineered["Date"].tolist() == ["2020-01-01", "2020-02-01", "2020-03-01", "2020-04-01"]
    assert "food_price_inflation_roll3" not in engineered.columns
    assert "Sorghum_Thousand Hectares_roll3" not in engineered.columns
    assert "Cattle_Number_roll3" not in engineered.columns
    assert "USD_mean_lag1_roll3" not in engineered.columns
    assert "USD_mean_pct_change_roll3" not in engineered.columns
    assert pd.isna(engineered.loc[0, "USD_mean_roll3"])
    assert pd.isna(engineered.loc[1, "USD_mean_roll3"])
    assert engineered.loc[2, "USD_mean_roll3"] == raw.sort_values("Date")["USD_mean"].iloc[:3].mean()
    assert engineered.loc[2, "USD_mean_std3"] == raw.sort_values("Date")["USD_mean"].iloc[:3].std()
    assert len(engineered) == len(raw)


def test_select_rolling_predictors_excludes_agriculture_livestock_and_engineered_columns() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2020-01-01"],
            "food_price_inflation": [1.0],
            "BDI_Close_mean": [2.0],
            "Brent_USD_per_barrel": [3.0],
            "Global_Food_Price_Index": [4.0],
            "USD_mean": [5.0],
            "policy_rate": [6.0],
            "headline_cpi": [7.0],
            "PI101001": [8.0],
            "Inflation (%)": [9.0],
            "Imports_Fuel": [10.0],
            "Sorghum_Thousand Hectares": [11.0],
            "Cattle_Number": [12.0],
            "Global_Food_Price_Index_pct_change": [0.1],
            "BDI_Close_mean_lag1": [15.0],
            "random_numeric": [16.0],
        }
    )

    predictors = select_rolling_statistic_predictor_columns(raw)

    assert predictors == [
        "BDI_Close_mean",
        "Brent_USD_per_barrel",
        "Global_Food_Price_Index",
        "USD_mean",
        "policy_rate",
        "headline_cpi",
        "PI101001",
        "Inflation (%)",
        "Imports_Fuel",
    ]


def test_build_stage3_rolling_dataset_preserves_rows_and_excludes_crop_livestock(tmp_path) -> None:
    output_path = tmp_path / "stage3_rolling_statistics.csv"

    summary = build_stage3_rolling_statistics_dataset(output_path=output_path)
    engineered = pd.read_csv(output_path)
    original = pd.read_csv("data/merged/merged_modeling_dataset.csv")
    predictors = select_rolling_statistic_predictor_columns(original)

    assert summary.rows == len(original)
    assert len(engineered) == len(original)
    assert summary.windows == STAGE3_ROLLING_WINDOWS
    assert summary.rolling_feature_count == len(predictors) * len(STAGE3_ROLLING_WINDOWS) * 2
    assert len(engineered.columns) == len(original.columns) + summary.rolling_feature_count
    assert list(engineered.columns[: len(original.columns)]) == list(original.columns)
    assert "food_price_inflation_roll3" not in engineered.columns
    assert "Sorghum_Thousand Hectares_roll3" not in engineered.columns
    assert "Cattle_Number_roll3" not in engineered.columns
    assert "Global_Food_Price_Index_roll12" in engineered.columns
    assert "USD_mean_std6" in engineered.columns
    assert engineered["Global_Food_Price_Index_roll3"].isna().iloc[:2].all()
    expected = original.loc[:2, "Global_Food_Price_Index"].mean()
    assert abs(engineered.loc[2, "Global_Food_Price_Index_roll3"] - expected) < 1e-12
    assert engineered.duplicated(subset=["Date"]).sum() == 0


def test_create_seasonal_features_uses_date_only_and_preserves_rows() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2020-04-01", "2020-01-01"],
            "food_price_inflation": [4.0, 1.0],
            "USD_mean": [140.0, 100.0],
        }
    )

    engineered = create_seasonal_features(raw)

    assert engineered["Date"].tolist() == ["2020-01-01", "2020-04-01"]
    assert engineered["Month"].tolist() == [1, 4]
    assert engineered["Quarter"].tolist() == [1, 2]
    assert engineered["Year"].tolist() == [2020, 2020]
    assert abs(engineered.loc[0, "Month_sin"] - 0.5) < 1e-12
    assert abs(engineered.loc[0, "Month_cos"] - 0.8660254037844387) < 1e-12
    assert len(engineered) == len(raw)


def test_build_stage4_seasonal_dataset_preserves_originals_and_rows(tmp_path) -> None:
    output_path = tmp_path / "stage4_seasonal_features.csv"

    summary = build_stage4_seasonal_dataset(output_path=output_path)
    engineered = pd.read_csv(output_path)
    original = pd.read_csv("data/merged/merged_modeling_dataset.csv")

    assert summary.rows == len(original)
    assert len(engineered) == len(original)
    assert summary.seasonal_feature_count == 5
    assert len(engineered.columns) == len(original.columns) + 5
    assert list(engineered.columns[: len(original.columns)]) == list(original.columns)
    assert ["Month", "Quarter", "Year", "Month_sin", "Month_cos"] == list(engineered.columns[-5:])
    assert engineered.loc[0, "Month"] == 1
    assert engineered.loc[0, "Quarter"] == 1
    assert engineered.loc[0, "Year"] == 2000
    assert engineered.duplicated(subset=["Date"]).sum() == 0


def test_create_trend_features_uses_previous_month_difference() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2020-03-01", "2020-01-01", "2020-02-01"],
            "food_price_inflation": [3.0, 1.0, 2.0],
            "USD_mean": [121.0, 100.0, 110.0],
            "policy_rate": [7.0, 5.0, 6.0],
            "Sorghum_Thousand Hectares": [30.0, 10.0, 20.0],
            "Cattle_Number": [300.0, 100.0, 200.0],
            "USD_mean_lag1": [110.0, 90.0, 100.0],
            "label": ["c", "a", "b"],
        }
    )

    engineered = create_trend_features(raw)

    assert engineered["Date"].tolist() == ["2020-01-01", "2020-02-01", "2020-03-01"]
    assert "food_price_inflation_trend" not in engineered.columns
    assert "Sorghum_Thousand Hectares_trend" not in engineered.columns
    assert "Cattle_Number_trend" not in engineered.columns
    assert "USD_mean_lag1_trend" not in engineered.columns
    assert "label_trend" not in engineered.columns
    assert pd.isna(engineered.loc[0, "USD_mean_trend"])
    assert engineered.loc[1, "USD_mean_trend"] == 10.0
    assert engineered.loc[2, "USD_mean_trend"] == 11.0
    assert engineered.loc[1, "policy_rate_trend"] == 1.0
    assert len(engineered) == len(raw)


def test_build_stage5_trend_dataset_preserves_rows_and_excludes_crop_livestock(tmp_path) -> None:
    output_path = tmp_path / "stage5_trend_features.csv"

    summary = build_stage5_trend_dataset(output_path=output_path)
    engineered = pd.read_csv(output_path)
    original = pd.read_csv("data/merged/merged_modeling_dataset.csv")
    predictors = select_trend_predictor_columns(original)

    assert summary.rows == len(original)
    assert len(engineered) == len(original)
    assert summary.trend_feature_count == len(predictors)
    assert len(engineered.columns) == len(original.columns) + len(predictors)
    assert list(engineered.columns[: len(original.columns)]) == list(original.columns)
    assert "food_price_inflation_trend" not in engineered.columns
    assert "Sorghum_Thousand Hectares_trend" not in engineered.columns
    assert "Cattle_Number_trend" not in engineered.columns
    assert "Global_Food_Price_Index_trend" in engineered.columns
    assert "PI101001_trend" in engineered.columns
    assert pd.isna(engineered.loc[0, "Global_Food_Price_Index_trend"])
    expected = original.loc[1, "Global_Food_Price_Index"] - original.loc[0, "Global_Food_Price_Index"]
    assert abs(engineered.loc[1, "Global_Food_Price_Index_trend"] - expected) < 1e-12
    assert engineered.duplicated(subset=["Date"]).sum() == 0


def test_select_interaction_pairs_returns_only_requested_pairs() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2020-01-01"],
            "food_price_inflation": [1.0],
            "Global_Food_Price_Index": [2.0],
            "Brent_USD_per_barrel": [3.0],
            "USD_mean": [4.0],
            "EUR_mean": [5.0],
            "Imports_Fuel": [6.0],
            "Imports_Food_Beverages_Tobacco": [7.0],
            "general_index": [8.0],
            "PI101001": [9.0],
            "PI101002": [10.0],
            "USD_mean_lag1": [11.0],
            "random_numeric": [12.0],
        }
    )

    pairs = select_interaction_pairs(raw)

    assert pairs == [
        ("Global_Food_Price_Index", "USD_mean"),
        ("Global_Food_Price_Index", "EUR_mean"),
        ("Brent_USD_per_barrel", "USD_mean"),
        ("Brent_USD_per_barrel", "EUR_mean"),
        ("Imports_Fuel", "Brent_USD_per_barrel"),
        ("Imports_Food_Beverages_Tobacco", "Global_Food_Price_Index"),
        ("PI101001", "general_index"),
        ("PI101002", "general_index"),
    ]


def test_create_interaction_features_multiplies_only_selected_pairs() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2020-02-01", "2020-01-01"],
            "food_price_inflation": [2.0, 1.0],
            "Global_Food_Price_Index": [20.0, 10.0],
            "Brent_USD_per_barrel": [40.0, 30.0],
            "USD_mean": [3.0, 2.0],
            "Imports_Fuel": [6.0, 5.0],
            "Imports_Food_Beverages_Tobacco": [8.0, 7.0],
            "general_index": [12.0, 11.0],
            "PI101001": [4.0, 3.0],
        }
    )

    engineered = create_interaction_features(raw)

    assert engineered["Date"].tolist() == ["2020-01-01", "2020-02-01"]
    assert engineered.loc[0, "Global_Food_Price_Index*x*USD_mean"] == 20.0
    assert engineered.loc[0, "Brent_USD_per_barrel*x*USD_mean"] == 60.0
    assert engineered.loc[0, "Imports_Fuel*x*Brent_USD_per_barrel"] == 150.0
    assert engineered.loc[0, "Imports_Food_Beverages_Tobacco*x*Global_Food_Price_Index"] == 70.0
    assert engineered.loc[0, "PI101001*x*general_index"] == 33.0
    assert "food_price_inflation*x*USD_mean" not in engineered.columns
    assert len(engineered) == len(raw)


def test_build_stage6_interaction_dataset_preserves_rows_and_expected_count(tmp_path) -> None:
    output_path = tmp_path / "stage6_interaction_features.csv"

    summary = build_stage6_interaction_dataset(output_path=output_path)
    engineered = pd.read_csv(output_path)
    original = pd.read_csv("data/merged/merged_modeling_dataset.csv")
    pairs = select_interaction_pairs(original)

    assert summary.rows == len(original)
    assert len(engineered) == len(original)
    assert summary.interaction_pair_count == len(pairs)
    assert len(engineered.columns) == len(original.columns) + len(pairs)
    assert list(engineered.columns[: len(original.columns)]) == list(original.columns)
    assert "Global_Food_Price_Index*x*USD_mean" in engineered.columns
    assert "Brent_USD_per_barrel*x*USD_mean" in engineered.columns
    assert "Imports_Fuel*x*Brent_USD_per_barrel" in engineered.columns
    assert "Imports_Food_Beverages_Tobacco*x*Global_Food_Price_Index" in engineered.columns
    assert "PI101001*x*general_index" in engineered.columns
    assert "Global_Food_Price_Index*x*policy_rate" not in engineered.columns
    expected = original.loc[0, "Global_Food_Price_Index"] * original.loc[0, "USD_mean"]
    actual = engineered.loc[0, "Global_Food_Price_Index*x*USD_mean"]
    if pd.isna(expected):
        assert pd.isna(actual)
    else:
        assert actual == expected
    assert engineered.duplicated(subset=["Date"]).sum() == 0


def test_select_stage_engineered_feature_columns_excludes_master_originals() -> None:
    master_columns = ["Date", "food_price_inflation", "USD_mean", "USD_pct_change"]
    stage2 = pd.DataFrame(
        {
            "Date": ["2020-01-01"],
            "USD_mean": [10.0],
            "USD_pct_change": [0.1],
            "USD_mean_pct_change": [0.2],
            "USD_pct_change_pct_change": [0.3],
            "random_feature": [1.0],
        }
    )
    stage6 = pd.DataFrame(
        {
            "Date": ["2020-01-01"],
            "Global_Food_Price_Index*x*USD_mean": [20.0],
            "Global_Food_Price_Index": [5.0],
        }
    )

    assert select_stage_engineered_feature_columns(stage2, "stage2", master_columns) == [
        "USD_mean_pct_change",
        "USD_pct_change_pct_change",
    ]
    assert select_stage_engineered_feature_columns(stage6, "stage6", master_columns) == [
        "Global_Food_Price_Index*x*USD_mean"
    ]


def test_create_mmarakai_feature_matrix_merges_only_engineered_columns() -> None:
    master = pd.DataFrame(
        {
            "Date": ["2020-02-01", "2020-01-01"],
            "food_price_inflation": [2.0, 1.0],
            "USD_mean": [20.0, 10.0],
            "USD_pct_change": [1.0, None],
        }
    )
    stage_datasets = [
        (
            "stage1",
            pd.DataFrame(
                {
                    "Date": ["2020-01-01", "2020-02-01"],
                    "USD_mean": [10.0, 20.0],
                    "USD_mean_lag1": [None, 10.0],
                }
            ),
        ),
        (
            "stage2",
            pd.DataFrame(
                {
                    "Date": ["2020-01-01", "2020-02-01"],
                    "USD_pct_change": [None, 1.0],
                    "USD_mean_pct_change": [None, 1.0],
                    "USD_pct_change_pct_change": [None, None],
                }
            ),
        ),
        (
            "stage3",
            pd.DataFrame(
                {
                    "Date": ["2020-01-01", "2020-02-01"],
                    "USD_mean_roll3": [None, None],
                    "USD_mean_std3": [None, None],
                }
            ),
        ),
        (
            "stage4",
            pd.DataFrame(
                {
                    "Date": ["2020-01-01", "2020-02-01"],
                    "Month": [1, 2],
                    "Quarter": [1, 1],
                    "Year": [2020, 2020],
                    "Month_sin": [0.5, 0.8660254037844386],
                    "Month_cos": [0.8660254037844387, 0.5],
                }
            ),
        ),
        (
            "stage5",
            pd.DataFrame(
                {
                    "Date": ["2020-01-01", "2020-02-01"],
                    "USD_mean_trend": [None, 10.0],
                }
            ),
        ),
        (
            "stage6",
            pd.DataFrame(
                {
                    "Date": ["2020-01-01", "2020-02-01"],
                    "Global_Food_Price_Index*x*USD_mean": [50.0, 120.0],
                }
            ),
        ),
    ]

    matrix, stage_counts = create_mmarakai_feature_matrix(master, stage_datasets)

    assert matrix["Date"].tolist() == ["2020-01-01", "2020-02-01"]
    assert list(matrix.columns[: len(master.columns)]) == list(master.columns)
    assert stage_counts == (
        ("stage1", 1),
        ("stage2", 2),
        ("stage3", 2),
        ("stage4", 5),
        ("stage5", 1),
        ("stage6", 1),
    )
    assert "USD_mean" in matrix.columns
    assert "USD_mean_lag1" in matrix.columns
    assert "USD_mean_pct_change" in matrix.columns
    assert "USD_pct_change_pct_change" in matrix.columns
    assert "USD_mean_roll3" in matrix.columns
    assert "USD_mean_std3" in matrix.columns
    assert "Month_sin" in matrix.columns
    assert "USD_mean_trend" in matrix.columns
    assert "Global_Food_Price_Index*x*USD_mean" in matrix.columns
    assert matrix.columns.tolist().count("USD_pct_change") == 1
    assert len(matrix) == len(master)
    assert matrix.duplicated(subset=["Date"]).sum() == 0
    assert matrix.columns.duplicated().sum() == 0


def test_build_mmarakai_feature_matrix_preserves_master_and_all_stage_features(tmp_path) -> None:
    stage_paths = (
        ("stage1", tmp_path / "stage1_lag_features.csv"),
        ("stage2", tmp_path / "stage2_percentage_change_features.csv"),
        ("stage3", tmp_path / "stage3_rolling_statistics.csv"),
        ("stage4", tmp_path / "stage4_seasonal_features.csv"),
        ("stage5", tmp_path / "stage5_trend_features.csv"),
        ("stage6", tmp_path / "stage6_interaction_features.csv"),
    )
    build_stage1_lag_dataset(output_path=stage_paths[0][1])
    build_stage2_percentage_change_dataset(output_path=stage_paths[1][1])
    build_stage3_rolling_statistics_dataset(output_path=stage_paths[2][1])
    build_stage4_seasonal_dataset(output_path=stage_paths[3][1])
    build_stage5_trend_dataset(output_path=stage_paths[4][1])
    build_stage6_interaction_dataset(output_path=stage_paths[5][1])

    output_path = tmp_path / "mmarakai_feature_matrix.csv"
    summary = build_mmarakai_feature_matrix(stage_paths=stage_paths, output_path=output_path)
    matrix = pd.read_csv(output_path)
    master = pd.read_csv("data/merged/merged_modeling_dataset.csv")
    expected_stage_counts = []
    for stage_name, stage_path in stage_paths:
        stage_dataset = pd.read_csv(stage_path)
        expected_stage_counts.append(
            (
                stage_name,
                len(select_stage_engineered_feature_columns(stage_dataset, stage_name, master.columns)),
            )
        )

    assert summary.rows == len(master)
    assert len(matrix) == len(master)
    assert summary.stage_feature_counts == tuple(expected_stage_counts)
    assert summary.engineered_feature_count == sum(count for _, count in expected_stage_counts)
    assert len(matrix.columns) == len(master.columns) + summary.engineered_feature_count
    assert list(matrix.columns[: len(master.columns)]) == list(master.columns)
    assert "food_price_inflation_lag1" not in matrix.columns
    assert "Global_Food_Price_Index_lag12" in matrix.columns
    assert "Global_Food_Price_Index_pct_change" in matrix.columns
    assert "Global_Food_Price_Index_roll12" in matrix.columns
    assert "Month_cos" in matrix.columns
    assert "Global_Food_Price_Index_trend" in matrix.columns
    assert "Global_Food_Price_Index*x*USD_mean" in matrix.columns
    assert matrix.columns.tolist().count("USD_pct_change") == 1
    assert matrix.duplicated(subset=["Date"]).sum() == 0
    assert matrix.columns.duplicated().sum() == 0
