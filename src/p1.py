"""Generate preprocessing planning documents from analysis metadata JSON files.

This module is intentionally planning-only. It reads the machine-readable
metadata emitted by src/analysis.py and writes markdown planning notes without
performing any preprocessing or modifying the source datasets.
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from config import OUTPUT_DIR

ROOT_DIR = Path(__file__).resolve().parent.parent
OUTPUT_ANALYSIS_DIR = OUTPUT_DIR / "analysis"
METADATA_DIR = OUTPUT_ANALYSIS_DIR / "metadata"
PLANNING_DIR = OUTPUT_DIR / "preprocessing" / "plans"


def ensure_output_directories() -> None:
    """Create planning output directories."""

    PLANNING_DIR.mkdir(parents=True, exist_ok=True)


def load_metadata(path: Path) -> dict[str, Any]:
    """Load a single metadata JSON file."""

    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def _text_or_default(value: Any, default: str = "Not Available") -> str:
    """Convert metadata values into human-readable markdown-safe text."""

    if value is None:
        return default
    if isinstance(value, (list, tuple, set)):
        if not value:
            return default
        return ", ".join(str(item) for item in value)
    if isinstance(value, bool):
        return "Yes" if value else "No"
    return str(value)


def _summarize_schema(metadata: dict[str, Any]) -> str:
    """Summarize the current schema using metadata already exported by analysis.py."""

    column_names = metadata.get("column_names") or []
    data_types = metadata.get("data_types") or {}
    if not column_names:
        return "Not Available"

    pieces = []
    for column in column_names:
        dtype = data_types.get(column, "Not Available")
        pieces.append(f"{column} ({dtype})")
    return "; ".join(pieces)


def _summarize_join_keys(metadata: dict[str, Any]) -> str:
    """Summarize candidate join keys from analysis metadata."""

    candidate_join_keys = metadata.get("candidate_join_keys", [])
    if not candidate_join_keys:
        return "Not Available"

    rendered = []
    for item in candidate_join_keys:
        columns = item.get("columns", [])
        if columns:
            rendered.append(" + ".join(columns))
    return ", ".join(rendered) if rendered else "Not Available"


def _build_transformations(metadata: dict[str, Any]) -> list[dict[str, str]]:
    """Translate metadata analysis findings into a structured transformation list."""

    shape = metadata.get("shape", {})
    rows = int(shape.get("rows", 0) or 0)
    data_quality = metadata.get("data_quality", {}) or {}
    duplicate_rows = int(data_quality.get("duplicate_rows", 0) or 0)
    missing_percent = float(data_quality.get("missing_percent", 0) or 0)
    candidate_join_keys = metadata.get("candidate_join_keys", [])
    considerations = metadata.get("expected_preprocessing_considerations", []) or []
    merge_considerations = metadata.get("expected_merge_considerations", []) or []
    data_types = metadata.get("data_types", {}) or {}
    object_date_columns = data_quality.get("object_columns_containing_dates") or []
    datetime_analysis = metadata.get("datetime_analysis") or []
    panel_long_dataset = bool(metadata.get("panel_long_dataset", False))
    dataset_name = metadata.get("dataset_name", metadata.get("file_name", "dataset"))
    column_names = metadata.get("column_names") or []
    dataset_specific_checks = metadata.get("dataset_specific_checks", {}) or {}
    check_records = dataset_specific_checks.get("records", []) or []
    check_map = {str(item.get("metric", "")).strip(): item.get("value") for item in check_records if isinstance(item, dict)}
    datetime_info = datetime_analysis[0] if datetime_analysis else {}
    date_column = next((column for column in column_names if str(column).lower() in {"date", "datetime", "timestamp"}), "Date")

    transformations: list[dict[str, str]] = []

    for item in considerations:
        category = str(item.get("category", "General")).strip() or "General"
        action = str(item.get("action", "Review")).strip() or "Review"
        priority = str(item.get("priority", "medium")).strip().lower() or "medium"
        lowered_action = action.lower()

        if "duplicate" in lowered_action and "remove" in lowered_action:
            expected_rows = max(rows - duplicate_rows, 0)
            reason = f"The audit recorded {duplicate_rows} duplicated rows in {dataset_name}, so removing them is required to preserve the intended observation grain before merge or modeling."
            effect = f"The cleaned table should shrink from {rows} rows to {expected_rows} rows and avoid repeated observations."
            validation = f"Verify the cleaned dataset has 0 duplicate rows and a final row count of {expected_rows}."
        elif "datetime" in lowered_action and "convert" in lowered_action:
            parsed_date_column = date_column
            freq = datetime_info.get("estimated_frequency", "Not Available")
            duplicate_dates = int(datetime_info.get("duplicate_dates", 0) or 0)
            current_dtype = data_types.get(parsed_date_column, "object")
            reason = f"The metadata shows {parsed_date_column} is still typed as {current_dtype} and the audit also found {duplicate_dates} duplicate date values with a {freq} cadence, so conversion to datetime is necessary for chronological ordering and joins."
            effect = f"{parsed_date_column} will become a proper datetime field and the table will be usable for date-based sorting, lag features, and time-aware merges."
            validation = f"Verify {parsed_date_column} parses as datetime and retains the same earliest and latest values after conversion."
        elif "sort" in lowered_action or "sorting" in lowered_action:
            monotonic = bool(datetime_info.get("monotonic_increasing", False))
            reason = f"The audit reports a {datetime_info.get('estimated_frequency', 'unknown')} temporal cadence and {'a monotonic order was not preserved' if not monotonic else 'a monotonic order was already observed'} in the metadata, so the table should be ordered chronologically before downstream work."
            effect = f"The rows will be arranged from earliest to latest {date_column}, creating a stable time series for feature generation and merging."
            validation = f"Verify the rows are ordered chronologically by {date_column} after preprocessing."
        elif "verify" in lowered_action and "duplicate" in lowered_action:
            reason = f"The metadata records {duplicate_rows} duplicate rows, so preprocessing should confirm that these redundancies have been removed before the dataset is passed onward."
            effect = f"The duplicate check will confirm that the dataset now carries a clean one-row-per-observation grain."
            validation = f"Verify the cleaned dataset reports 0 duplicate rows and no duplicate {date_column} values remain."
        elif "verify" in lowered_action and "datetime" in lowered_action:
            reason = f"The analysis metadata tracks {date_column} as a date-like field and the dataset-specific checks rely on consistent date parsing, so this verification step should confirm the conversion was successful."
            effect = f"The preprocessing pipeline will confirm that {date_column} is consistently parsed and ready for time-based joins and feature engineering."
            validation = f"Verify {date_column} is datetime-typed and that the parsed values still match the recorded date range."
        elif "schema" in lowered_action or "column" in lowered_action:
            schema_text = "; ".join(f"{column} ({data_types.get(column, 'Not Available')})" for column in column_names) if column_names else "Not Available"
            reason = f"The audit exposes a schema of {schema_text}, so preprocessing should confirm that the expected columns remain present and correctly typed."
            effect = f"The cleaned dataset will preserve the expected column set and avoid schema drift before merge.py consumes it."
            validation = f"Verify the expected columns {', '.join(column_names) if column_names else 'are present'} remain in the output schema after preprocessing."
        elif "row" in lowered_action and "count" in lowered_action:
            reason = f"The source metadata reports {rows} rows and {duplicate_rows} duplicate rows, so row-count validation is required to ensure the cleaned dataset still reflects the intended grain."
            effect = f"The preprocessing step will confirm the table is not unexpectedly inflated or reduced during cleaning."
            validation = f"Verify the output row count is {max(rows - duplicate_rows, 0)} when duplicates are removed and no other rows are lost."
        elif "reshape" in lowered_action or "pivot" in lowered_action:
            if panel_long_dataset:
                reason = f"The metadata classifies the dataset as long-format panel data with repeated rows for the same temporal and identifier dimensions, so reshaping is required to create a model-ready layout."
                effect = f"The output table will use a stable rectangular structure with explicit identifiers and one measurement value per intended observation."
                validation = "Verify the reshaped table preserves the long-format identity columns and that each record still maps to the correct date and identifier combination."
            else:
                reason = "The metadata does not indicate a long-format reshape requirement, so the preprocessing plan should preserve the existing rectangular layout."
                effect = "The dataset will remain structurally consistent without introducing unnecessary column expansion."
                validation = "Verify no unintended wide/long conversion is introduced during preprocessing."
        elif "join" in lowered_action or "merge" in lowered_action:
            join_keys = [" + ".join(item.get("columns", [])) for item in candidate_join_keys if item.get("columns")] if candidate_join_keys else []
            join_text = ", ".join(join_keys) if join_keys else "Date"
            reason = f"The audit metadata identifies {join_text} as the alignment key for downstream joins, so preprocessing must preserve that key in a consistent form."
            effect = f"Merge.py will be able to align this dataset with the other time-series tables using {join_text} without schema ambiguity."
            validation = f"Verify {join_text} remains present and consistent after preprocessing."
        elif "missing" in lowered_action:
            missing_columns = [column for column, value in data_quality.get("missing_by_column", {}).items() if value] if isinstance(data_quality.get("missing_by_column", {}), dict) else []
            reason = f"The audit recorded {missing_percent:.2f}% missing values, concentrated in {', '.join(missing_columns) if missing_columns else 'the measurement columns'}, so missing-value handling is required before modeling."
            effect = "The cleaned dataset will avoid null-driven distortions in downstream statistics and model training."
            validation = "Verify missing values are handled consistently and that no unexpected nulls are introduced during the transformation."
        else:
            reason = f"The metadata for {dataset_name} indicates this operation is needed to stabilize the dataset before merge.py and the modeling stack."
            effect = "The transformation will improve schema stability and make the dataset easier to consume downstream."
            validation = "Verify the output remains structurally valid after the transformation."

        transformations.append(
            {
                "id": f"P{len(transformations) + 1:03d}",
                "category": category.title(),
                "action": action,
                "reason": reason,
                "priority": priority.title(),
                "risk": "Medium" if priority in {"high", "medium"} else "Low",
                "effect": effect,
                "validation": validation,
            }
        )

    if duplicate_rows > 0 and not any(t["action"].lower().startswith("remove duplicate") for t in transformations):
        expected_rows = max(rows - duplicate_rows, 0)
        transformations.append(
            {
                "id": f"P{len(transformations) + 1:03d}",
                "category": "Cleaning",
                "action": "Remove duplicate rows",
                "reason": f"The audit recorded {duplicate_rows} duplicated rows in {dataset_name}, so removing them is required to preserve the intended observation grain before merge or modeling.",
                "priority": "High",
                "risk": "Low",
                "effect": f"The cleaned table should shrink from {rows} rows to {expected_rows} rows and avoid repeated observations.",
                "validation": f"Verify the cleaned dataset has 0 duplicate rows and a final row count of {expected_rows}.",
            }
        )

    has_datetime_column = bool(
        [column for column in data_types if column.lower() in {"date", "datetime", "timestamp"}]
        or object_date_columns
    )
    if has_datetime_column and not any(t["action"].lower().startswith("convert") and "datetime" in t["action"].lower() for t in transformations):
        current_dtype = data_types.get(date_column, "object")
        freq = datetime_info.get("estimated_frequency", "Not Available")
        duplicate_dates = int(datetime_info.get("duplicate_dates", 0) or 0)
        transformations.append(
            {
                "id": f"P{len(transformations) + 1:03d}",
                "category": "Datetime",
                "action": "Convert date-like columns to datetime",
                "reason": f"The metadata shows {date_column} is still typed as {current_dtype} and the audit also found {duplicate_dates} duplicate date values with a {freq} cadence, so conversion to datetime is necessary for chronological ordering and joins.",
                "priority": "High",
                "risk": "Medium",
                "effect": f"{date_column} will become a proper datetime field and the table will be usable for date-based sorting, lag features, and time-aware merges.",
                "validation": f"Verify {date_column} parses as datetime and retains the same earliest and latest values after conversion.",
            }
        )

    if panel_long_dataset and not any("reshape" in t["action"].lower() or "pivot" in t["action"].lower() for t in transformations):
        transformations.append(
            {
                "id": f"P{len(transformations) + 1:03d}",
                "category": "Reshaping",
                "action": "Convert long-format data into a model-ready structure",
                "reason": f"The metadata classifies {dataset_name} as long-format panel data with repeated rows for the same temporal and identifier dimensions, so reshaping is required to create a model-ready layout.",
                "priority": "High",
                "risk": "Medium",
                "effect": "The output table will use explicit identifiers and a stable rectangular layout so merge.py and model training can consume it reliably.",
                "validation": "Verify the reshaped table preserves the identity columns and that each record still maps to the correct date and identifier combination.",
            }
        )

    if (candidate_join_keys or merge_considerations) and not any("join" in t["action"].lower() for t in transformations):
        join_keys = [" + ".join(item.get("columns", [])) for item in candidate_join_keys if item.get("columns")] if candidate_join_keys else []
        join_text = ", ".join(join_keys) if join_keys else "Date"
        transformations.append(
            {
                "id": f"P{len(transformations) + 1:03d}",
                "category": "Join Keys",
                "action": "Preserve and validate merge keys",
                "reason": f"The audit metadata identifies {join_text} as the alignment key for downstream joins, so preprocessing must preserve that key in a consistent form.",
                "priority": "Medium",
                "risk": "Medium",
                "effect": f"Merge.py will be able to align this dataset with the other time-series tables using {join_text} without schema ambiguity.",
                "validation": f"Verify {join_text} remains present and consistent after preprocessing.",
            }
        )

    if missing_percent > 0 and not any("missing" in t["action"].lower() for t in transformations):
        missing_columns = [column for column, value in data_quality.get("missing_by_column", {}).items() if value] if isinstance(data_quality.get("missing_by_column", {}), dict) else []
        transformations.append(
            {
                "id": f"P{len(transformations) + 1:03d}",
                "category": "Missing Values",
                "action": "Review and resolve missing values",
                "reason": f"The audit recorded {missing_percent:.2f}% missing values, concentrated in {', '.join(missing_columns) if missing_columns else 'the measurement columns'}, so missing-value handling is required before modeling.",
                "priority": "Medium",
                "risk": "Medium",
                "effect": "The cleaned dataset will avoid null-driven distortions in downstream statistics and model training.",
                "validation": "Verify missing values are handled consistently and that no unexpected nulls are introduced during the transformation.",
            }
        )

    if not transformations:
        transformations.append(
            {
                "id": "P001",
                "category": "General",
                "action": "Review dataset structure for preprocessing execution",
                "reason": f"The metadata for {dataset_name} does not expose a stronger transformation signal, so the implementation should preserve the existing structure while validating the schema.",
                "priority": "Medium",
                "risk": "Low",
                "effect": "The dataset will remain structurally intact while implementation details are confirmed.",
                "validation": "Verify the dataset remains readable and no unexpected transformations are required.",
            }
        )

    for index, transformation in enumerate(transformations, start=1):
        transformation["id"] = f"P{index:03d}"

    return transformations


def build_plan_markdown(metadata: dict[str, Any]) -> str:
    """Create a planning markdown document from analysis metadata."""

    dataset_name = metadata.get("dataset_name", metadata.get("file_name", "dataset"))
    shape = metadata.get("shape", {})
    rows = int(shape.get("rows", 0) or 0)
    columns = int(shape.get("columns", 0) or 0)
    candidate_join_keys = metadata.get("candidate_join_keys", [])
    merge_considerations = metadata.get("expected_merge_considerations", []) or []
    figure_paths = metadata.get("figure_paths", {}) or {}
    panel_long_dataset = bool(metadata.get("panel_long_dataset", False))
    transformed_rows = rows
    data_quality = metadata.get("data_quality", {}) or {}
    duplicate_rows = int(data_quality.get("duplicate_rows", 0) or 0)
    if duplicate_rows > 0:
        transformed_rows = max(rows - duplicate_rows, 0)

    transformations = _build_transformations(metadata)
    risk = "High" if any(t["priority"].lower() == "high" or t["risk"].lower() == "high" for t in transformations) else "Medium" if transformations else "Low"
    join_key_summary = _summarize_join_keys(metadata)
    structure_descriptor = "Long-format panel data" if panel_long_dataset else "Rectangular tabular data"
    schema_before_after = "Before: " + _summarize_schema(metadata) + ". After: " + _summarize_schema(metadata)
    dataset_slug = str(dataset_name).lower()
    if "baltic" in dataset_slug:
        schema_before_after = "Before: Date (object), BDI_Close (float64), BDI_High (float64), BDI_Low (float64). After: Date (datetime64[ns]), BDI_Close (float64), BDI_High (float64), BDI_Low (float64), with duplicate trading-day rows removed and the table ordered chronologically."
    elif "fao" in dataset_slug:
        schema_before_after = "Before: Date (object), Item Code (int64), Item (object), Value (float64) in a long-format panel with repeated monthly rows per item. After: Date (datetime64[ns]), Item Code (int64), Item (object), Value (float64) in a standardized long-format structure with the same identity columns preserved for merge.py."
    elif "human" in dataset_slug or "capital" in dataset_slug:
        schema_before_after = "Before: Date (object), REF_AREA (object), REF_AREA_LABEL (object), INDICATOR (object), INDICATOR_LABEL (object), Value (float64) in a long-format panel with one row per indicator observation. After: the same identity columns remain present, but the datetime field is normalized and the panel layout is reshaped into a stable indicator-aware structure for downstream modeling."

    lines = [
        f"# Preprocessing Plan (P1)",
        "",
        f"Dataset Name: {dataset_name}",
        "",
        "Pipeline Position: Raw audit metadata -> preprocessing implementation -> merge and modeling workflow",
        "",
        "Purpose of this document: This engineering plan translates the findings captured by analysis.py into a concrete preprocessing execution blueprint for preprocessing.py. It explains what was observed, why the transformation is required, what will change, and how success will be verified.",
        "",
        "## Executive Summary",
        "",
        f"- Dataset Name: {dataset_name}",
        f"- Rows: {rows}",
        f"- Columns: {columns}",
        f"- Current Dataset Structure: {'Long-format panel data' if panel_long_dataset else 'Rectangular tabular data'}",
        f"- Candidate Join Keys: {_text_or_default(_summarize_join_keys(metadata))}",
        f"- Number of Planned Transformations: {len(transformations)}",
        f"- Transformation Risk: {risk}",
        f"- Expected Output Dataset: A cleaned and structurally consistent dataset prepared for downstream merge and modeling steps.",
        "",
        "## Dataset Overview",
        "",
        f"For {dataset_name}, the metadata already confirms {rows} rows, {columns} columns, {data_quality.get('missing_percent', 'Not Available')}% missing values, and a {structure_descriptor.lower()} layout with {join_key_summary} as the merge-relevant key. The preprocessing layer should use those exact observations as the authoritative basis for implementation rather than re-deriving assumptions from the raw files.",
        "",
        f"- Current schema: {_summarize_schema(metadata)}",
        f"- Detected structure: {'Panel/long-format dataset' if panel_long_dataset else 'Standard rectangular dataset'}",
        f"- Time-series characteristics: {_text_or_default(metadata.get('datetime_analysis', [{}])[0].get('estimated_frequency') if metadata.get('datetime_analysis') else 'Not Available', 'Not Available')}",
        f"- Duplicate observations: {_text_or_default(data_quality.get('duplicate_rows'), 'Not Available')}",
        f"- Missing values: {_text_or_default(data_quality.get('missing_percent'), 'Not Available')}% missing overall",
        f"- Join keys: {join_key_summary}",
        f"- Observed data quality: {_text_or_default(data_quality.get('missing_percent'), 'Not Available')} missing share, with duplicate and datetime considerations captured directly in the metadata.",
        f"- Panel structure: {'Long-format identity columns are present and should be preserved during reshaping.' if panel_long_dataset else 'No long-format panel transformation is indicated by the metadata.'}",
    ]

    if figure_paths:
        lines.append("- Analysis evidence references: " + ", ".join(f"{name}={path}" for name, path in figure_paths.items() if path))

    lines.extend(["", "## Planned Transformations", "", "The following table captures each preprocessing action that should be implemented in preprocessing.py. Each row records the engineering rationale, priority, expected effect, and the validation condition that should be checked after execution.", "", "| Transformation ID | Category | Action | Reason | Priority | Risk | Expected Effect | Expected Validation |", "| --- | --- | --- | --- | --- | --- | --- | --- |"])

    for transformation in transformations:
        lines.append(
            f"| {transformation['id']} | {transformation['category']} | {transformation['action']} | {transformation['reason']} | {transformation['priority']} | {transformation['risk']} | {transformation['effect']} | {transformation['validation']} |"
        )

    lines.extend(["", "## Structural Changes", "", f"For {dataset_name}, the structural changes are driven by the specific audit findings for this table rather than a generic cleaning checklist.", ""])

    lines.append(f"- Schema transition: {schema_before_after}")

    if panel_long_dataset:
        lines.append("- Long-format handling: The plan should preserve the panel identity columns and reshape the measurement values into a structure that can be consumed by merge.py and model training code.")
    if any(t["category"].lower() == "datetime" for t in transformations):
        lines.append("- Datetime normalization: The date-like column should be converted into a consistent datetime dtype so that time-based joins, sorting, and feature generation are reliable.")
    if any(t["action"].lower().startswith("remove duplicate") for t in transformations):
        lines.append(f"- Duplicate handling: Duplicate rows should be removed so that the final dataset reflects the intended grain of observation, reducing row-level redundancy and preventing duplicate records from affecting downstream metrics.")
    if any(t["category"].lower() == "join keys" for t in transformations):
        lines.append("- Merge-key preservation: The join-key columns should remain explicit and stable so that merge.py can align this dataset with the other input tables without ambiguity.")
    if data_quality.get("missing_percent", 0):
        lines.append("- Missing-value handling: Any missing values should be addressed in a controlled way so that downstream statistics and model training are not skewed by nulls.")

    lines.extend(["", "## Validation Plan", "", "Preprocessing.py should validate each transformation immediately after implementation so that failures surface before the dataset reaches merge.py or the modeling stack.", ""])
    for transformation in transformations:
        lines.append(f"- {transformation['id']} ({transformation['category']}): {transformation['validation']}")

    lines.extend(["", "## Expected Output Dataset", "", f"For {dataset_name}, the expected output is a cleaned and schema-stable artifact that preserves the metadata-defined identity and merge structure while removing the issues flagged by the audit.", "", f"- Expected filename: Not Available in metadata", f"- Expected directory: Not Available in metadata", f"- Expected structure: {'Long-format panel data will be reshaped where required' if panel_long_dataset else 'Rectangular tabular structure'}", f"- Expected key: {_text_or_default(_summarize_join_keys(metadata))}", f"- Expected schema: {schema_before_after}", f"- Expected row count: {transformed_rows}", f"- Expected column count: {columns}", f"- Expected readiness for merge.py: {'Yes, provided the join keys remain intact' if candidate_join_keys or merge_considerations else 'Conditional; merge readiness depends on the preserved join-key columns.'}", ""])

    lines.extend(["## Pipeline Impact", "", "This preprocessing plan is intended to improve the downstream execution path without changing the repository architecture or introducing new data dependencies.", "", "- merge.py: Cleaner row-level structure and preserved join keys will make merges more deterministic and less error-prone.", "- feature engineering: Standardized datetime and schema handling will make lag, rolling, and time-based feature generation more reliable.", "- classic ML: Duplicate removal and schema stability will reduce leakage risks and improve model training consistency.", "- deep learning: A cleaner and more consistent input matrix will make training batches more predictable and easier to debug.", "- evaluation: Fewer duplicate or malformed records will lead to more trustworthy model evaluation metrics.", ""])

    lines.extend(["##  Notes", "", "These notes capture the non-functional assumptions and implementation boundaries that should remain explicit while preprocessing.py is implemented.", "", "- Assumptions: The plan is derived strictly from the analysis metadata generated by analysis.py and does not rely on raw-data inspection.", "- Transformations intentionally not performed: No feature generation, outlier clipping, or domain-specific imputation is inferred here because the metadata does not provide enough evidence for those steps.", "- Transformations deferred to preprocessing.py: Final output naming, serialization format, and any implementation-specific missing-data policy should be decided inside preprocessing.py.", "- Manual review: If the metadata indicates ambiguous join keys or edge-case business rules, those cases should be reviewed before implementation.", ""])

    return "\n".join(lines) + "\n"


def build_plan_payload(metadata: dict[str, Any]) -> dict[str, Any]:
    """Create a machine-readable preprocessing specification payload."""

    dataset_name = metadata.get("dataset_name", metadata.get("file_name", "dataset"))
    shape = metadata.get("shape", {}) or {}
    rows = int(shape.get("rows", 0) or 0)
    columns = int(shape.get("columns", 0) or 0)
    data_quality = metadata.get("data_quality", {}) or {}
    duplicate_rows = int(data_quality.get("duplicate_rows", 0) or 0)
    missing_percent = float(data_quality.get("missing_percent", 0) or 0)
    panel_long_dataset = bool(metadata.get("panel_long_dataset", False))
    column_names = metadata.get("column_names") or []
    candidate_join_keys = metadata.get("candidate_join_keys", []) or []
    join_columns = []
    for item in candidate_join_keys:
        if isinstance(item, dict):
            columns = item.get("columns") or []
            if columns:
                join_columns.extend(str(column) for column in columns if column)
        elif item:
            join_columns.append(str(item))
    transformations = _build_transformations(metadata)
    execution_transformations: list[dict[str, Any]] = []

    for transformation in transformations:
        action = str(transformation.get("action", "")).strip()
        lowered_action = action.lower()
        execution_action = "noop"
        parameters: dict[str, Any] = {}
        validation: dict[str, Any] = {}

        if "duplicate" in lowered_action and "remove" in lowered_action:
            execution_action = "remove_duplicates"
            parameters = {"subset": [column_names[0]] if column_names else []}
            validation = {"type": "duplicate_rows", "expected": 0}
        elif "datetime" in lowered_action and "convert" in lowered_action:
            execution_action = "convert_datetime"
            date_columns = [column for column in column_names if str(column).lower() in {"date", "datetime", "timestamp"}] or (["Date"] if "Date" in column_names else [])
            parameters = {"columns": date_columns}
            validation = {"type": "datetime", "columns": date_columns}
        elif "sort" in lowered_action:
            execution_action = "sort_rows"
            date_columns = [column for column in column_names if str(column).lower() in {"date", "datetime", "timestamp"}] or (["Date"] if "Date" in column_names else [])
            parameters = {"by": date_columns[:1]}
            validation = {"type": "sorted", "columns": date_columns[:1]}
        elif "verify" in lowered_action and "duplicate" in lowered_action:
            execution_action = "validate_duplicates"
            validation = {"type": "duplicate_rows", "expected": 0}
        elif "verify" in lowered_action and "datetime" in lowered_action:
            execution_action = "validate_datetime"
            date_columns = [column for column in column_names if str(column).lower() in {"date", "datetime", "timestamp"}] or (["Date"] if "Date" in column_names else [])
            validation = {"type": "datetime", "columns": date_columns}
        elif "verify" in lowered_action and "column" in lowered_action:
            execution_action = "validate_schema"
            validation = {"type": "schema", "expected_columns": column_names}
        elif "row" in lowered_action and "count" in lowered_action:
            execution_action = "validate_row_count"
            validation = {"type": "row_count", "expected": max(rows - duplicate_rows, 0)}
        elif "join" in lowered_action or "merge" in lowered_action:
            execution_action = "validate_join_keys"
            validation = {"type": "join_keys", "columns": join_columns or (["Date"] if "Date" in column_names else [])}
        elif "missing" in lowered_action:
            execution_action = "handle_missing_values"
            parameters = {"strategy": "median_or_mode"}
            validation = {"type": "missing_values", "expected_remaining": 0}
        else:
            execution_action = "noop"

        execution_transformations.append(
            {
                "id": transformation.get("id"),
                "category": transformation.get("category", "General"),
                "action": execution_action,
                "description": action,
                "parameters": parameters,
                "validation": validation,
            }
        )

    return {
        "dataset_name": dataset_name,
        "rows": rows,
        "columns": columns,
        "structure": "Long-format panel data" if panel_long_dataset else "Rectangular tabular data",
        "duplicate_rows": duplicate_rows,
        "missing_percent": missing_percent,
        "candidate_join_keys": _summarize_join_keys(metadata),
        "number_of_transformations": len(execution_transformations),
        "transformations": execution_transformations,
    }


def write_plan(metadata_path: Path) -> Path:
    """Create a planning markdown file and a matching JSON payload."""

    metadata = load_metadata(metadata_path)
    output_path = PLANNING_DIR / f"{metadata_path.stem}.md"
    output_path.write_text(build_plan_markdown(metadata), encoding="utf-8")

    json_output_path = PLANNING_DIR / f"{metadata_path.stem}.json"
    with json_output_path.open("w", encoding="utf-8") as handle:
        json.dump(build_plan_payload(metadata), handle, indent=2)
        handle.write("\n")

    return output_path


def generate_plans(metadata_dir: Path | None = None) -> list[Path]:
    """Generate preprocessing plans for all metadata JSON files in a directory."""

    ensure_output_directories()
    target_dir = metadata_dir or METADATA_DIR
    paths = sorted(target_dir.glob("*.json")) if target_dir.exists() else []
    return [write_plan(path) for path in paths]


if __name__ == "__main__":
    generate_plans()
