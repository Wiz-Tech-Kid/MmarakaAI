from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from .config import PROJECT_ROOT
except ImportError:  # pragma: no cover - supports running this file directly.
    from config import PROJECT_ROOT


FEATURE_DATA_DIR = PROJECT_ROOT / "data" / "features"
FINAL_FEATURE_MATRIX_PATH = FEATURE_DATA_DIR / "mmarakai_feature_matrix.csv"
STAGEA_CLEAN_FEATURE_MATRIX_PATH = FEATURE_DATA_DIR / "mmarakai_clean_feature_matrix.csv"
STAGEA_REPORT_PATH = FEATURE_DATA_DIR / "feature_selection_stageA_report.md"
STAGEA_TEXT_REPORT_PATH = FEATURE_DATA_DIR / "feature_selection_stageA_report.txt"

DEFAULT_DATE_COLUMN = "Date"
DEFAULT_TARGET_COLUMN = "Food price inflation"
DEFAULT_NEAR_CONSTANT_THRESHOLD = 0.995


@dataclass(frozen=True, slots=True)
class StageAFeatureSelectionSummary:
    input_path: Path
    output_path: Path
    report_path: Path
    text_report_path: Path | None
    rows: int
    original_columns: int
    final_columns: int
    original_feature_count: int
    final_feature_count: int
    date_column: str
    target_column: str
    empty_features: tuple[str, ...]
    duplicate_features: tuple[str, ...]
    constant_features: tuple[str, ...]
    near_constant_features: tuple[str, ...]

    @property
    def removed_feature_count(self) -> int:
        return (
            len(self.empty_features)
            + len(self.duplicate_features)
            + len(self.constant_features)
            + len(self.near_constant_features)
        )

    def as_dict(self) -> dict[str, Any]:
        return {
            "input_path": str(self.input_path),
            "output_path": str(self.output_path),
            "report_path": str(self.report_path),
            "text_report_path": str(self.text_report_path) if self.text_report_path else None,
            "rows": self.rows,
            "original_columns": self.original_columns,
            "final_columns": self.final_columns,
            "original_feature_count": self.original_feature_count,
            "final_feature_count": self.final_feature_count,
            "date_column": self.date_column,
            "target_column": self.target_column,
            "empty_features_removed": len(self.empty_features),
            "duplicate_features_removed": len(self.duplicate_features),
            "constant_features_removed": len(self.constant_features),
            "near_constant_features_removed": len(self.near_constant_features),
            "total_features_removed": self.removed_feature_count,
        }


def _normalize_column_key(column_name: str) -> str:
    text = str(column_name or "").strip().lower()
    return "".join(character if character.isalnum() else "_" for character in text).strip("_")


def resolve_column_name(dataset: pd.DataFrame, requested_column: str) -> str:
    if requested_column in dataset.columns:
        return requested_column

    requested_key = _normalize_column_key(requested_column)
    column_lookup = {_normalize_column_key(column): column for column in dataset.columns}
    if requested_key in column_lookup:
        return column_lookup[requested_key]

    raise KeyError(f"Column {requested_column!r} was not found in the dataset.")


def _sort_by_date_preserving_values(dataset: pd.DataFrame, date_column: str) -> pd.DataFrame:
    parsed_dates = pd.to_datetime(dataset[date_column], errors="coerce")
    if parsed_dates.isna().any():
        raise ValueError(f"{date_column!r} contains unparseable dates.")
    return (
        dataset.assign(__stagea_parsed_date=parsed_dates)
        .sort_values("__stagea_parsed_date", kind="mergesort")
        .drop(columns="__stagea_parsed_date")
        .reset_index(drop=True)
    )


def _feature_columns(dataset: pd.DataFrame, protected_columns: set[str]) -> list[str]:
    return [column for column in dataset.columns if column not in protected_columns]


def _series_values_equal(left: pd.Series, right: pd.Series) -> bool:
    same_missing = left.isna() & right.isna()
    same_values = left.eq(right).fillna(False)
    return bool((same_missing | same_values).all())


def _column_hash_key(series: pd.Series) -> tuple[int, ...]:
    return tuple(pd.util.hash_pandas_object(series, index=False).tolist())


def detect_duplicate_feature_columns(
    dataset: pd.DataFrame,
    *,
    protected_columns: set[str],
) -> tuple[tuple[str, tuple[str, ...]], ...]:
    """Detect exact duplicate columns while never removing protected columns."""

    hash_groups: dict[tuple[int, ...], list[str]] = {}
    for column in dataset.columns:
        hash_groups.setdefault(_column_hash_key(dataset[column]), []).append(column)

    duplicate_groups: list[tuple[str, tuple[str, ...]]] = []
    for candidate_columns in hash_groups.values():
        if len(candidate_columns) < 2:
            continue

        exact_groups: list[list[str]] = []
        for column in candidate_columns:
            for exact_group in exact_groups:
                if _series_values_equal(dataset[column], dataset[exact_group[0]]):
                    exact_group.append(column)
                    break
            else:
                exact_groups.append([column])

        for exact_group in exact_groups:
            if len(exact_group) < 2:
                continue

            protected_in_group = [column for column in exact_group if column in protected_columns]
            keep_column = protected_in_group[0] if protected_in_group else exact_group[0]
            removed_columns = tuple(
                column for column in exact_group if column != keep_column and column not in protected_columns
            )
            if removed_columns:
                duplicate_groups.append((keep_column, removed_columns))

    return tuple(duplicate_groups)


def detect_constant_features(dataset: pd.DataFrame, *, protected_columns: set[str]) -> tuple[str, ...]:
    constant_features: list[str] = []
    for column in _feature_columns(dataset, protected_columns):
        if dataset[column].nunique(dropna=True) == 1:
            constant_features.append(column)
    return tuple(constant_features)


def detect_near_constant_features(
    dataset: pd.DataFrame,
    *,
    protected_columns: set[str],
    threshold: float = DEFAULT_NEAR_CONSTANT_THRESHOLD,
) -> tuple[str, ...]:
    if not 0 < threshold <= 1:
        raise ValueError("Near-constant threshold must be greater than 0 and less than or equal to 1.")

    near_constant_features: list[str] = []
    for column in _feature_columns(dataset, protected_columns):
        non_missing_values = dataset[column].dropna()
        if non_missing_values.empty or non_missing_values.nunique(dropna=True) <= 1:
            continue
        dominant_share = non_missing_values.value_counts(dropna=True).iloc[0] / len(non_missing_values)
        if dominant_share >= threshold:
            near_constant_features.append(column)
    return tuple(near_constant_features)


def clean_stageA_structural_features(
    dataset: pd.DataFrame,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
    target_column: str = DEFAULT_TARGET_COLUMN,
    near_constant_threshold: float = DEFAULT_NEAR_CONSTANT_THRESHOLD,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    """Remove only objectively unsuitable structural features from a matrix."""

    if dataset is None or not isinstance(dataset, pd.DataFrame):
        raise ValueError("Stage A requires a pandas DataFrame.")

    resolved_date = resolve_column_name(dataset, date_column)
    resolved_target = resolve_column_name(dataset, target_column)
    protected_columns = {resolved_date, resolved_target}
    cleaned = _sort_by_date_preserving_values(dataset.copy(), resolved_date)

    empty_features = tuple(
        column for column in _feature_columns(cleaned, protected_columns) if cleaned[column].isna().all()
    )
    if empty_features:
        cleaned = cleaned.drop(columns=list(empty_features))

    duplicate_groups = detect_duplicate_feature_columns(cleaned, protected_columns=protected_columns)
    duplicate_features = tuple(column for _, removed_columns in duplicate_groups for column in removed_columns)
    if duplicate_features:
        cleaned = cleaned.drop(columns=list(duplicate_features))

    constant_features = detect_constant_features(cleaned, protected_columns=protected_columns)
    if constant_features:
        cleaned = cleaned.drop(columns=list(constant_features))

    near_constant_features = detect_near_constant_features(
        cleaned,
        protected_columns=protected_columns,
        threshold=near_constant_threshold,
    )
    if near_constant_features:
        cleaned = cleaned.drop(columns=list(near_constant_features))

    removal_details: dict[str, tuple[str, ...] | tuple[tuple[str, tuple[str, ...]], ...]] = {
        "empty_features": empty_features,
        "duplicate_groups": duplicate_groups,
        "duplicate_features": duplicate_features,
        "constant_features": constant_features,
        "near_constant_features": near_constant_features,
    }
    return cleaned, removal_details


def render_stageA_report(
    summary: StageAFeatureSelectionSummary,
    *,
    duplicate_groups: tuple[tuple[str, tuple[str, ...]], ...],
) -> str:
    sections = [
        "# Feature Selection Stage A Report",
        "",
        "Structural feature cleaning only. No predictive importance, correlation analysis, imputation, or feature-family removal was performed.",
        "",
        "## Summary",
        "",
        f"- Input file: `{summary.input_path}`",
        f"- Output file: `{summary.output_path}`",
        f"- Rows: {summary.rows}",
        f"- Protected date column: `{summary.date_column}`",
        f"- Protected target column: `{summary.target_column}`",
        f"- Original number of features: {summary.original_feature_count}",
        f"- Number of empty features removed: {len(summary.empty_features)}",
        f"- Number of duplicate features removed: {len(summary.duplicate_features)}",
        f"- Number of constant features removed: {len(summary.constant_features)}",
        f"- Number of near-constant features removed: {len(summary.near_constant_features)}",
        f"- Final number of features: {summary.final_feature_count}",
        "",
    ]

    def add_feature_list(title: str, features: tuple[str, ...]) -> None:
        sections.extend([f"## {title}", ""])
        if not features:
            sections.append("- None")
        else:
            sections.extend(f"- `{feature}`" for feature in features)
        sections.append("")

    add_feature_list("Removed Empty Features", summary.empty_features)

    sections.extend(["## Removed Duplicate Features", ""])
    if not duplicate_groups:
        sections.append("- None")
    else:
        for kept_column, removed_columns in duplicate_groups:
            sections.append(f"- Kept `{kept_column}`; removed: " + ", ".join(f"`{column}`" for column in removed_columns))
    sections.append("")

    add_feature_list("Removed Constant Features", summary.constant_features)
    add_feature_list("Removed Near-Constant Features", summary.near_constant_features)
    return "\n".join(sections).rstrip() + "\n"


def build_stageA_clean_feature_matrix(
    input_path: str | Path = FINAL_FEATURE_MATRIX_PATH,
    output_path: str | Path = STAGEA_CLEAN_FEATURE_MATRIX_PATH,
    report_path: str | Path = STAGEA_REPORT_PATH,
    text_report_path: str | Path | None = STAGEA_TEXT_REPORT_PATH,
    *,
    date_column: str = DEFAULT_DATE_COLUMN,
    target_column: str = DEFAULT_TARGET_COLUMN,
    near_constant_threshold: float = DEFAULT_NEAR_CONSTANT_THRESHOLD,
) -> StageAFeatureSelectionSummary:
    input_file = Path(input_path)
    output_file = Path(output_path)
    report_file = Path(report_path)
    text_report_file = Path(text_report_path) if text_report_path else None
    if not input_file.exists():
        raise FileNotFoundError(f"Feature matrix not found: {input_file}")

    dataset = pd.read_csv(input_file)
    resolved_date = resolve_column_name(dataset, date_column)
    resolved_target = resolve_column_name(dataset, target_column)
    protected_columns = {resolved_date, resolved_target}
    original_feature_count = len(_feature_columns(dataset, protected_columns))

    cleaned, removal_details = clean_stageA_structural_features(
        dataset,
        date_column=resolved_date,
        target_column=resolved_target,
        near_constant_threshold=near_constant_threshold,
    )
    final_feature_count = len(_feature_columns(cleaned, protected_columns))

    output_file.parent.mkdir(parents=True, exist_ok=True)
    cleaned.to_csv(output_file, index=False)

    duplicate_groups = removal_details["duplicate_groups"]
    if not isinstance(duplicate_groups, tuple):
        raise TypeError("duplicate_groups should be a tuple.")

    summary = StageAFeatureSelectionSummary(
        input_path=input_file,
        output_path=output_file,
        report_path=report_file,
        text_report_path=text_report_file,
        rows=len(cleaned),
        original_columns=len(dataset.columns),
        final_columns=len(cleaned.columns),
        original_feature_count=original_feature_count,
        final_feature_count=final_feature_count,
        date_column=resolved_date,
        target_column=resolved_target,
        empty_features=removal_details["empty_features"],  # type: ignore[arg-type]
        duplicate_features=removal_details["duplicate_features"],  # type: ignore[arg-type]
        constant_features=removal_details["constant_features"],  # type: ignore[arg-type]
        near_constant_features=removal_details["near_constant_features"],  # type: ignore[arg-type]
    )
    report_text = render_stageA_report(summary, duplicate_groups=duplicate_groups)  # type: ignore[arg-type]
    report_file.parent.mkdir(parents=True, exist_ok=True)
    report_file.write_text(report_text, encoding="utf-8")
    if text_report_file:
        text_report_file.parent.mkdir(parents=True, exist_ok=True)
        text_report_file.write_text(report_text, encoding="utf-8")
    return summary


def main() -> None:
    summary = build_stageA_clean_feature_matrix()
    print(f"Saved Stage A clean feature matrix to: {summary.output_path}")
    print(f"Saved Stage A report to: {summary.report_path}")
    if summary.text_report_path:
        print(f"Saved Stage A text report to: {summary.text_report_path}")
    print(f"Rows: {summary.rows}")
    print(f"Original features: {summary.original_feature_count}")
    print(f"Final features: {summary.final_feature_count}")
    print(f"Removed features: {summary.removed_feature_count}")


if __name__ == "__main__":
    main()
