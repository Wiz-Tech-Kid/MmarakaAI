from __future__ import annotations

import pandas as pd

from src.feature_selection import (
    build_stageA_clean_feature_matrix,
    clean_stageA_structural_features,
    detect_duplicate_feature_columns,
)


def test_detect_duplicate_feature_columns_keeps_target_when_feature_matches_target() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2020-01-01", "2020-02-01", "2020-03-01"],
            "food_price_inflation": [1.0, 2.0, 3.0],
            "target_copy": [1.0, 2.0, 3.0],
            "feature_a": [5.0, None, 7.0],
            "feature_a_copy": [5.0, None, 7.0],
        }
    )

    duplicate_groups = detect_duplicate_feature_columns(
        raw,
        protected_columns={"Date", "food_price_inflation"},
    )

    assert duplicate_groups == (
        ("food_price_inflation", ("target_copy",)),
        ("feature_a", ("feature_a_copy",)),
    )


def test_clean_stageA_structural_features_removes_only_structural_failures() -> None:
    raw = pd.DataFrame(
        {
            "Date": ["2020-03-01", "2020-01-01", "2020-02-01", "2020-04-01", "2020-05-01"],
            "food_price_inflation": [3.0, 1.0, 2.0, 4.0, 5.0],
            "empty_feature": [None, None, None, None, None],
            "feature_a": [30.0, 10.0, None, 40.0, 50.0],
            "feature_a_copy": [30.0, 10.0, None, 40.0, 50.0],
            "constant_feature": [7.0, None, 7.0, 7.0, 7.0],
            "near_constant_feature": [1.0, 1.0, 1.0, 1.0, 2.0],
            "high_missing_but_valid": [None, None, 8.0, None, 9.0],
            "USD_mean_lag1": [None, 1.0, 2.0, 3.0, 4.0],
            "USD_mean_roll3": [None, None, 2.0, 3.0, 4.0],
            "USD_mean*x*Global_Food_Price_Index": [5.0, 6.0, 7.0, 8.0, 9.0],
            "USD_mean_trend": [2.0, 1.0, 3.0, 1.0, 1.0],
            "USD_mean_pct_change": [None, 0.1, 0.2, 0.3, 0.4],
        }
    )

    cleaned, removal_details = clean_stageA_structural_features(
        raw,
        target_column="Food price inflation",
        near_constant_threshold=0.8,
    )

    assert cleaned["Date"].tolist() == ["2020-01-01", "2020-02-01", "2020-03-01", "2020-04-01", "2020-05-01"]
    assert "food_price_inflation" in cleaned.columns
    assert removal_details["empty_features"] == ("empty_feature",)
    assert removal_details["duplicate_features"] == ("feature_a_copy",)
    assert removal_details["constant_features"] == ("constant_feature",)
    assert removal_details["near_constant_features"] == ("near_constant_feature",)
    assert "high_missing_but_valid" in cleaned.columns
    assert "USD_mean_lag1" in cleaned.columns
    assert "USD_mean_roll3" in cleaned.columns
    assert "USD_mean*x*Global_Food_Price_Index" in cleaned.columns
    assert "USD_mean_trend" in cleaned.columns
    assert "USD_mean_pct_change" in cleaned.columns
    assert len(cleaned) == len(raw)
    assert cleaned.columns.duplicated().sum() == 0


def test_build_stageA_clean_feature_matrix_writes_outputs_and_report(tmp_path) -> None:
    input_path = tmp_path / "mmarakai_feature_matrix.csv"
    output_path = tmp_path / "mmarakai_clean_feature_matrix.csv"
    report_path = tmp_path / "feature_selection_stageA_report.md"
    text_report_path = tmp_path / "feature_selection_stageA_report.txt"
    raw = pd.DataFrame(
        {
            "Date": ["2020-02-01", "2020-01-01", "2020-03-01"],
            "food_price_inflation": [2.0, 1.0, 3.0],
            "empty_feature": [None, None, None],
            "good_feature": [20.0, 10.0, 30.0],
            "good_feature_copy": [20.0, 10.0, 30.0],
            "constant_feature": [5.0, 5.0, 5.0],
        }
    )
    raw.to_csv(input_path, index=False)

    summary = build_stageA_clean_feature_matrix(
        input_path=input_path,
        output_path=output_path,
        report_path=report_path,
        text_report_path=text_report_path,
    )
    cleaned = pd.read_csv(output_path)
    report = report_path.read_text(encoding="utf-8")

    assert summary.rows == len(raw)
    assert summary.original_feature_count == 4
    assert summary.final_feature_count == 1
    assert cleaned.columns.tolist() == ["Date", "food_price_inflation", "good_feature"]
    assert cleaned["Date"].tolist() == ["2020-01-01", "2020-02-01", "2020-03-01"]
    assert "Number of empty features removed: 1" in report
    assert "Number of duplicate features removed: 1" in report
    assert "Number of constant features removed: 1" in report
    assert "`empty_feature`" in report
    assert "`good_feature_copy`" in report
    assert "`constant_feature`" in report
    assert text_report_path.read_text(encoding="utf-8") == report


def test_build_stageA_clean_feature_matrix_on_real_final_matrix(tmp_path) -> None:
    output_path = tmp_path / "mmarakai_clean_feature_matrix.csv"
    report_path = tmp_path / "feature_selection_stageA_report.md"

    summary = build_stageA_clean_feature_matrix(
        output_path=output_path,
        report_path=report_path,
        text_report_path=None,
    )
    cleaned = pd.read_csv(output_path)
    original = pd.read_csv("data/features/mmarakai_feature_matrix.csv")

    assert summary.rows == len(original)
    assert len(cleaned) == len(original)
    assert "Date" in cleaned.columns
    assert "food_price_inflation" in cleaned.columns
    assert cleaned["Date"].is_monotonic_increasing
    assert cleaned.columns.duplicated().sum() == 0
    assert not cleaned.drop(columns=["Date", "food_price_inflation"]).isna().all().any()
    assert report_path.exists()
