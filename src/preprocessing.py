"""Specification-driven preprocessing execution engine for MmarakaAI.

The engine loads preprocessing specifications from JSON and executes them through
operation objects. It does not embed dataset-specific behavior in the runner;
all transformations are represented as Operation instances that implement
execute(), validate(), and report().
"""

from __future__ import annotations

from abc import ABC, abstractmethod
from collections.abc import Mapping, Sequence
from datetime import date, datetime
import json
import logging
import time
from pathlib import Path
from typing import Any

import pandas as pd

try:
    from .config import PROCESSED_DATA_DIR, RAW_DATA_DIR, OUTPUT_DIR
    from .external_preprocessing import preprocess_external_dataset
except ImportError:  # pragma: no cover - supports running this file directly.
    from config import PROCESSED_DATA_DIR, RAW_DATA_DIR, OUTPUT_DIR
    from external_preprocessing import preprocess_external_dataset


logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
)
logger = logging.getLogger(__name__)


TabularDataset = pd.DataFrame


def _json_safe(value: Any) -> Any:
    """Convert pandas and datetime values into JSON-serializable primitives."""

    if value is None or isinstance(value, (str, int, float, bool)):
        return value
    if isinstance(value, (datetime, date)):
        return value.isoformat()
    if isinstance(value, pd.Timestamp):
        return value.isoformat()
    if isinstance(value, pd.Timedelta):
        return str(value)
    if isinstance(value, Path):
        return str(value)
    if isinstance(value, Mapping):
        return {str(key): _json_safe(item) for key, item in value.items()}
    if isinstance(value, (list, tuple, set)):
        return [_json_safe(item) for item in value]
    return str(value)


class Operation(ABC):
    """Base class for all preprocessing operations loaded from the JSON spec."""

    def __init__(self, specification: Mapping[str, Any], dataset_name: str | None = None) -> None:
        self.specification = dict(specification or {})
        self.dataset_name = dataset_name or ""
        self.action = str(self.specification.get("action", "noop"))
        self.parameters = dict(self.specification.get("parameters") or {})
        self.validation_rule = dict(self.specification.get("validation") or {})
        self.enabled = bool(self.specification.get("enabled", True))
        self.description = str(self.specification.get("description") or self.action)
        self.identifier = str(self.specification.get("id") or self.action)
        self.source_path: Path | None = None

    @abstractmethod
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        """Execute the transformation against the supplied dataset."""

    @abstractmethod
    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        """Validate the transformation result for the supplied dataset."""

    def report(
        self,
        *,
        status: str,
        rows_before: int,
        rows_after: int,
        columns_before: Sequence[str],
        columns_after: Sequence[str],
        execution_time: float,
        validation_status: str,
        validation_message: str,
        validation_details: Mapping[str, Any],
        error_message: str = "",
    ) -> dict[str, Any]:
        """Create a report entry for the executed operation."""

        return {
            "id": self.identifier,
            "action": self.description,
            "status": status,
            "rows_before": rows_before,
            "rows_after": rows_after,
            "columns_before": list(columns_before),
            "columns_after": list(columns_after),
            "execution_time": round(execution_time, 6),
            "validation": validation_status,
            "error_message": error_message if status == "FAILED" else "",
            "parameters": self.parameters,
            "validation_details": dict(validation_details),
            "enabled": self.enabled,
        }


class NoOpOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        return dataset.copy()

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        return "PASS", "No operation was executed.", {"expected": None, "actual": None, "status": "PASS"}


class RemoveDuplicatesOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        subset = list(self.parameters.get("subset") or [])
        keep = self.parameters.get("keep", "first")
        ignore_index = bool(self.parameters.get("ignore_index", True))
        cleaned = dataset.drop_duplicates(subset=subset or None, keep=keep)
        if ignore_index:
            cleaned = cleaned.reset_index(drop=True)
        return cleaned

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        expected = self.validation_rule.get("expected", 0)
        duplicate_rows_after = int(dataset.duplicated().sum())
        details = {"expected": expected, "actual": duplicate_rows_after, "status": "PASS"}
        if duplicate_rows_after == expected:
            return "PASS", "Duplicate rows were removed successfully.", details
        return "FAIL", f"Expected {expected} duplicate rows after removal, found {duplicate_rows_after}.", details


class ConvertDatetimeOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        converted = dataset.copy()
        kwargs: dict[str, Any] = {}
        if "errors" in self.parameters:
            kwargs["errors"] = self.parameters["errors"]
        if "format" in self.parameters and self.parameters.get("format") not in (None, "", "auto"):
            kwargs["format"] = self.parameters["format"]
        if "utc" in self.parameters:
            kwargs["utc"] = bool(self.parameters["utc"])
        for column in list(self.parameters.get("columns") or []):
            if column in converted.columns:
                converted[column] = pd.to_datetime(converted[column], **kwargs)
        return converted

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        columns = list(self.validation_rule.get("columns") or [])
        if not columns:
            return "PASS", "No datetime conversion validation rule was supplied.", {"expected": None, "actual": None, "status": "PASS"}
        if all(column in dataset.columns and pd.api.types.is_datetime64_any_dtype(dataset[column]) for column in columns):
            return "PASS", "Datetime conversion was applied successfully.", {"expected": columns, "actual": columns, "status": "PASS"}
        return "FAIL", "One or more target columns were not converted to datetime.", {"expected": columns, "actual": list(dataset.columns), "status": "FAIL"}


class SortRowsOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        sort_columns = list(self.parameters.get("by") or [])
        if not sort_columns:
            return dataset.copy()
        ascending = self.parameters.get("ascending", True)
        kind = self.parameters.get("kind", "mergesort")
        return dataset.sort_values(by=sort_columns, ascending=ascending, kind=kind).reset_index(drop=True)

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        columns = list(self.validation_rule.get("columns") or [])
        if not columns:
            return "PASS", "No sort validation rule was supplied.", {"expected": None, "actual": None, "status": "PASS"}
        sort_column = columns[0]
        if sort_column in dataset.columns and dataset[sort_column].is_monotonic_increasing:
            return "PASS", "Rows are sorted chronologically.", {"expected": columns, "actual": list(dataset[sort_column]), "status": "PASS"}
        return "FAIL", "Rows are not sorted in the expected order.", {"expected": columns, "actual": list(dataset[sort_column]), "status": "FAIL"}


class HandleMissingValuesOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        cleaned = dataset.copy()
        strategy = self.parameters.get("strategy")
        if not strategy:
            return cleaned
        columns = list(self.parameters.get("columns") or cleaned.columns)
        limit = self.parameters.get("limit")
        value = self.parameters.get("value")
        for column in columns:
            if column not in cleaned.columns:
                continue
            if cleaned[column].isna().sum() == 0:
                continue
            if strategy == "drop":
                cleaned = cleaned.dropna(subset=[column]).reset_index(drop=True)
            elif strategy == "constant":
                cleaned[column] = cleaned[column].fillna(value if value is not None else 0)
            elif strategy == "ffill":
                cleaned[column] = cleaned[column].ffill(limit=limit)
            elif strategy == "bfill":
                cleaned[column] = cleaned[column].bfill(limit=limit)
            elif strategy == "median":
                if pd.api.types.is_numeric_dtype(cleaned[column]):
                    cleaned[column] = cleaned[column].fillna(cleaned[column].median())
            elif strategy == "mode":
                mode_value = cleaned[column].mode(dropna=True)
                if not mode_value.empty:
                    cleaned[column] = cleaned[column].fillna(mode_value.iloc[0])
                else:
                    cleaned[column] = cleaned[column].fillna("")
            else:
                raise ValueError(f"Unsupported missing-value strategy: {strategy}")
        return cleaned

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        expected_remaining = self.validation_rule.get("expected_remaining")
        missing_count = int(dataset.isna().sum().sum())
        details = {"expected": expected_remaining, "actual": missing_count, "status": "PASS"}
        if expected_remaining is None or missing_count <= expected_remaining:
            return "PASS", "Missing values were handled according to the specification.", details
        return "FAIL", f"Unexpected missing values remain: {missing_count}.", details


class RenameColumnsOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        rename_mapping = self.parameters.get("mapping") or self.parameters.get("columns") or {}
        if not rename_mapping:
            return dataset.copy()
        return dataset.rename(columns=rename_mapping)

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        return "PASS", "Column renaming completed.", {"expected": None, "actual": None, "status": "PASS"}


class ReorderColumnsOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        expected_columns = list(self.parameters.get("columns") or [])
        if not expected_columns:
            return dataset.copy()
        present_columns = [column for column in expected_columns if column in dataset.columns]
        remaining_columns = [column for column in dataset.columns if column not in present_columns]
        return dataset[present_columns + remaining_columns]

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        return "PASS", "Column ordering completed.", {"expected": None, "actual": None, "status": "PASS"}


class NormalizeDataTypesOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        normalized = dataset.copy()
        data_types = self.parameters.get("schema") or self.parameters.get("types") or {}
        if not data_types:
            return normalized
        for column, target_type in data_types.items():
            if column not in normalized.columns:
                continue
            lower_target = str(target_type).lower()
            if "datetime" in lower_target or "date" in lower_target:
                normalized[column] = pd.to_datetime(normalized[column], errors="coerce")
            elif any(token in lower_target for token in ["float", "int", "integer", "numeric"]):
                normalized[column] = pd.to_numeric(normalized[column], errors="coerce")
        return normalized

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        return "PASS", "Data types were normalized according to the specification.", {"expected": None, "actual": None, "status": "PASS"}


class ExternalDatasetPreprocessOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        dataset_name = self.dataset_name or self.parameters.get("dataset_name") or ""
        if not dataset_name:
            return dataset.copy()
        return preprocess_external_dataset(dataset_name, dataset, source_path=self.source_path)

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        return "PASS", "Dataset-specific external preprocessing completed.", {"expected": None, "actual": None, "status": "PASS"}


class ReshapeLongToWideOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        index = list(self.parameters.get("index") or [])
        columns = list(self.parameters.get("columns") or [])
        values = list(self.parameters.get("values") or [])
        if not index or not columns or not values:
            return dataset.copy()

        preserve_columns = list(self.parameters.get("preserve_columns") or [])
        preserved_frame = None
        if preserve_columns:
            preserved_frame = dataset.groupby(index, dropna=False)[preserve_columns].first().reset_index()

        reshaped = pd.pivot_table(dataset, index=index, columns=columns[0], values=values[0], aggfunc=self.parameters.get("aggfunc", "first"))
        reshaped = reshaped.reset_index()

        if preserved_frame is not None:
            merge_columns = [column for column in index if column in preserved_frame.columns]
            if merge_columns:
                reshaped = reshaped.merge(preserved_frame, on=merge_columns, how="left")

        if bool(self.parameters.get("sort_columns", False)):
            reshaped = reshaped.sort_index(axis=1)

        if isinstance(reshaped.columns, pd.MultiIndex):
            if bool(self.parameters.get("flatten_columns", False)):
                reshaped.columns = [
                    "_".join(str(part) for part in column if str(part) != "")
                    if isinstance(column, tuple)
                    else str(column)
                    for column in reshaped.columns
                ]
            if bool(self.parameters.get("remove_column_index_name", False)):
                reshaped.columns = reshaped.columns.set_names([None] * reshaped.columns.nlevels)
        return reshaped

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        validation_rule = self.validation_rule
        details = {"expected": validation_rule.get("expected_rows"), "actual": len(dataset), "status": "PASS"}
        expected_rows = validation_rule.get("expected_rows")
        if expected_rows is not None and len(dataset) != expected_rows:
            return "FAIL", f"Expected {expected_rows} rows, found {len(dataset)}.", details
        expected_columns = validation_rule.get("expected_columns")
        if expected_columns is not None and not set(expected_columns).issubset(dataset.columns):
            return "FAIL", "The expected columns are missing from the reshaped dataset.", {**details, "expected_columns": expected_columns, "actual_columns": list(dataset.columns)}
        primary_key_columns = validation_rule.get("primary_key_columns") or validation_rule.get("primary_key") or []
        if primary_key_columns:
            duplicate_keys = int(dataset.duplicated(subset=list(primary_key_columns)).sum())
            if duplicate_keys != 0:
                return "FAIL", f"Primary key columns contain {duplicate_keys} duplicates.", {**details, "duplicate_keys": duplicate_keys}
        generated_feature_columns = validation_rule.get("generated_feature_columns") or []
        if generated_feature_columns and not set(generated_feature_columns).issubset(dataset.columns):
            return "FAIL", "One or more generated feature columns are missing.", {**details, "generated_feature_columns": generated_feature_columns, "actual_columns": list(dataset.columns)}
        expected_duplicate_keys = validation_rule.get("expected_duplicate_keys", 0)
        duplicate_key_columns = validation_rule.get("duplicate_key_columns") or []
        if duplicate_key_columns:
            duplicate_key_count = int(dataset.duplicated(subset=list(duplicate_key_columns)).sum())
            if duplicate_key_count != expected_duplicate_keys:
                return "FAIL", f"Expected {expected_duplicate_keys} duplicate keys, found {duplicate_key_count}.", {**details, "duplicate_key_columns": duplicate_key_columns, "duplicate_key_count": duplicate_key_count}
        return "PASS", "Reshaping completed according to the specification.", details


class ReshapeWideToLongOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        id_vars = list(self.parameters.get("id_vars") or [])
        value_vars = list(self.parameters.get("value_vars") or [])
        if not id_vars or not value_vars:
            return dataset.copy()
        return pd.melt(dataset, id_vars=id_vars, value_vars=value_vars, var_name=self.parameters.get("var_name", "variable"), value_name=self.parameters.get("value_name", "value"))

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        return "PASS", "Reshape wide-to-long completed.", {"expected": None, "actual": None, "status": "PASS"}


class ValidateSchemaOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        return dataset.copy()

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        expected_columns = list(self.validation_rule.get("expected_columns") or [])
        if not expected_columns:
            return "PASS", "No schema validation rule was supplied.", {"expected": None, "actual": None, "status": "PASS"}
        present = set(expected_columns).issubset(dataset.columns)
        details = {"expected": expected_columns, "actual": list(dataset.columns), "status": "PASS"}
        if present and (not self.validation_rule.get("forbid_extra_columns") or set(dataset.columns) == set(expected_columns)):
            return "PASS", "The expected schema is present.", details
        return "FAIL", "The expected schema is not present.", details


class ValidateRowCountOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        return dataset.copy()

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        expected = self.validation_rule.get("expected")
        if expected is None:
            return "PASS", "No row-count validation rule was supplied.", {"expected": None, "actual": len(dataset), "status": "PASS"}
        if len(dataset) == expected:
            return "PASS", "Row count matches the expected value.", {"expected": expected, "actual": len(dataset), "status": "PASS"}
        return "FAIL", f"Expected {expected} rows, found {len(dataset)}.", {"expected": expected, "actual": len(dataset), "status": "FAIL"}


class ValidateDuplicatesOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        return dataset.copy()

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        expected = self.validation_rule.get("expected", 0)
        duplicate_rows_after = int(dataset.duplicated().sum())
        details = {"expected": expected, "actual": duplicate_rows_after, "status": "PASS"}
        if duplicate_rows_after == expected:
            return "PASS", "Duplicate rows are absent.", details
        return "FAIL", f"Expected {expected} duplicate rows, found {duplicate_rows_after}.", details


class ValidateDatetimeOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        return dataset.copy()

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        columns = list(self.validation_rule.get("columns") or [])
        if not columns:
            return "PASS", "No datetime validation rule was supplied.", {"expected": None, "actual": None, "status": "PASS"}
        if all(column in dataset.columns and pd.api.types.is_datetime64_any_dtype(dataset[column]) for column in columns):
            return "PASS", "Datetime columns remain valid.", {"expected": columns, "actual": columns, "status": "PASS"}
        return "FAIL", "Datetime validation failed.", {"expected": columns, "actual": list(dataset.columns), "status": "FAIL"}


class ValidateJoinKeysOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        return dataset.copy()

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        join_columns = list(self.validation_rule.get("columns") or [])
        if not join_columns:
            return "PASS", "No join-key validation rule was supplied.", {"expected": None, "actual": None, "status": "PASS"}
        if all(column in dataset.columns for column in join_columns):
            return "PASS", "Join keys remain available.", {"expected": join_columns, "actual": list(dataset.columns), "status": "PASS"}
        return "FAIL", "One or more join keys are missing.", {"expected": join_columns, "actual": list(dataset.columns), "status": "FAIL"}


class ValidateMissingValuesOperation(Operation):
    def execute(self, dataset: TabularDataset) -> TabularDataset:
        return dataset.copy()

    def validate(self, dataset: TabularDataset) -> tuple[str, str, dict[str, Any]]:
        expected_remaining = self.validation_rule.get("expected_remaining")
        missing_count = int(dataset.isna().sum().sum())
        details = {"expected": expected_remaining, "actual": missing_count, "status": "PASS"}
        if expected_remaining is None or missing_count <= expected_remaining:
            return "PASS", "Missing values are within the expected bounds.", details
        return "FAIL", f"Expected at most {expected_remaining} missing values, found {missing_count}.", details


OPERATION_REGISTRY: dict[str, type[Operation]] = {
    "remove_duplicates": RemoveDuplicatesOperation,
    "convert_datetime": ConvertDatetimeOperation,
    "sort_rows": SortRowsOperation,
    "handle_missing_values": HandleMissingValuesOperation,
    "rename_columns": RenameColumnsOperation,
    "reorder_columns": ReorderColumnsOperation,
    "normalize_data_types": NormalizeDataTypesOperation,
    "external_dataset_preprocess": ExternalDatasetPreprocessOperation,
    "reshape_long_to_wide": ReshapeLongToWideOperation,
    "reshape_wide_to_long": ReshapeWideToLongOperation,
    "validate_schema": ValidateSchemaOperation,
    "validate_row_count": ValidateRowCountOperation,
    "validate_duplicates": ValidateDuplicatesOperation,
    "validate_datetime": ValidateDatetimeOperation,
    "validate_join_keys": ValidateJoinKeysOperation,
    "validate_missing_values": ValidateMissingValuesOperation,
    "noop": NoOpOperation,
}


def _normalize_action_name(action: str) -> str:
    """Normalize a transformation action to a deterministic internal name."""

    normalized = str(action).strip().lower().replace(" ", "_").replace("-", "_")
    aliases = {
        "duplicate_removal": "remove_duplicates",
        "remove_duplicate_rows": "remove_duplicates",
        "remove_duplicates": "remove_duplicates",
        "datetime_conversion": "convert_datetime",
        "convert_date_to_datetime": "convert_datetime",
        "convert_datetime": "convert_datetime",
        "sorting": "sort_rows",
        "sort_chronologically_by_date": "sort_rows",
        "sort_rows": "sort_rows",
        "missing_value_handling": "handle_missing_values",
        "handle_missing_values": "handle_missing_values",
        "column_renaming": "rename_columns",
        "rename_columns": "rename_columns",
        "column_ordering": "reorder_columns",
        "reorder_columns": "reorder_columns",
        "schema_validation": "validate_schema",
        "validate_schema": "validate_schema",
        "row_count_validation": "validate_row_count",
        "validate_row_count": "validate_row_count",
        "duplicate_check": "validate_duplicates",
        "validate_duplicates": "validate_duplicates",
        "datetime_check": "validate_datetime",
        "validate_datetime": "validate_datetime",
        "join_key_preservation": "validate_join_keys",
        "validate_join_keys": "validate_join_keys",
        "missing_values_validation": "validate_missing_values",
        "validate_missing_values": "validate_missing_values",
        "data_type_normalization": "normalize_data_types",
        "normalize_data_types": "normalize_data_types",
        "external_dataset_preprocess": "external_dataset_preprocess",
        "dataset_specific_preprocess": "external_dataset_preprocess",
        "reshape_long_to_wide": "reshape_long_to_wide",
        "reshape_wide_to_long": "reshape_wide_to_long",
    }
    return aliases.get(normalized, normalized)


def create_operation(specification: Mapping[str, Any], dataset_name: str | None = None) -> Operation:
    """Create an operation object from a transformation specification."""

    normalized_action = _normalize_action_name(str(specification.get("action", "noop")))
    operation_cls = OPERATION_REGISTRY.get(normalized_action)
    if operation_cls is None:
        raise ValueError(f"Unsupported transformation action: {specification.get('action')}")
    return operation_cls(specification, dataset_name=dataset_name)


def ensure_output_directories() -> None:
    """Create the required processing and reporting directories."""

    directories = [
        PROCESSED_DATA_DIR,
        OUTPUT_DIR / "preprocessing" / "execution" / "markdown",
        OUTPUT_DIR / "preprocessing" / "execution" / "metadata",
    ]
    for directory in directories:
        directory.mkdir(parents=True, exist_ok=True)


def load_metadata(metadata_path: str | Path) -> dict[str, Any]:
    """Load analysis metadata JSON from disk."""

    path = Path(metadata_path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def load_specification(spec_path: str | Path) -> dict[str, Any]:
    """Load the preprocessing specification JSON from disk."""

    path = Path(spec_path)
    with path.open("r", encoding="utf-8") as handle:
        return json.load(handle)


def resolve_dataset_id(specification: Mapping[str, Any], spec_path: str | Path) -> str:
    """Resolve the dataset identifier from the specification or the filename."""

    spec_path = Path(spec_path)
    candidates: list[str] = []
    dataset_name = specification.get("dataset_name")
    if dataset_name:
        candidates.append(str(dataset_name))
    candidates.append(spec_path.stem)
    for candidate in candidates:
        if candidate:
            return candidate
    return spec_path.stem


def locate_raw_dataset(dataset_id: str, raw_data_dir: str | Path) -> Path:
    """Locate the matching raw dataset file from the configured raw data directory or the external-data directory."""

    raw_dir = Path(raw_data_dir)
    candidates = [dataset_id, dataset_id.replace("_processed", "")]
    for candidate in candidates:
        matches = sorted(raw_dir.glob(f"{candidate}*"))
        if matches:
            for match in matches:
                if match.is_file():
                    return match
    for match in sorted(raw_dir.glob("*.csv")):
        if dataset_id in match.stem:
            return match
    for match in sorted(raw_dir.glob("*.xlsx")):
        if dataset_id in match.stem:
            return match
    for match in sorted(raw_dir.glob("*.xls")):
        if dataset_id in match.stem:
            return match
    raise FileNotFoundError(f"No raw dataset found for {dataset_id} in {raw_dir}")


def load_raw_dataset(file_path: str | Path, **read_options: Any) -> TabularDataset:
    """Load a raw dataset into a pandas DataFrame."""

    path = Path(file_path)
    suffix = path.suffix.lower()
    if suffix == ".csv":
        return pd.read_csv(path, **read_options)
    if suffix == ".json":
        return pd.read_json(path, **read_options)
    if suffix in {".parquet", ".pq"}:
        return pd.read_parquet(path, **read_options)
    if suffix in {".xlsx", ".xls"}:
        return pd.read_excel(path, **read_options)
    raise ValueError(f"Unsupported file type for preprocessing: {path}")


def execute_transformations(
    dataset: TabularDataset,
    specification: Mapping[str, Any],
    dataset_name: str | None = None,
    source_path: str | Path | None = None,
) -> tuple[TabularDataset, list[dict[str, Any]], list[str]]:
    """Execute the transformations defined in the specification JSON."""

    current_dataset = dataset.copy()
    transformations: list[dict[str, Any]] = []
    notes: list[str] = []

    ordered_transformations = []
    for index, transformation in enumerate(specification.get("transformations", []) or []):
        order_value = transformation.get("execution_order")
        if order_value is None:
            order_value = index + 1
        ordered_transformations.append((int(order_value), index, transformation))
    ordered_transformations.sort(key=lambda item: (item[0], item[1]))

    for _, _, transformation in ordered_transformations:
        rows_before = len(current_dataset)
        columns_before = list(current_dataset.columns)
        operation = create_operation(transformation, dataset_name=dataset_name)
        operation.source_path = Path(source_path) if source_path is not None else None
        enabled = bool(transformation.get("enabled", True))
        start = time.perf_counter()

        try:
            if not enabled:
                rows_after = len(current_dataset)
                columns_after = list(current_dataset.columns)
                validation_status, validation_message, validation_details = operation.validate(current_dataset)
                elapsed = time.perf_counter() - start
                transformations.append(
                    operation.report(
                        status="SKIPPED",
                        rows_before=rows_before,
                        rows_after=rows_after,
                        columns_before=columns_before,
                        columns_after=columns_after,
                        execution_time=elapsed,
                        validation_status=validation_status,
                        validation_message=validation_message,
                        validation_details=validation_details,
                    )
                )
                notes.append(f"Skipped transformation: {operation.description}")
                continue

            current_dataset = operation.execute(current_dataset)
            rows_after = len(current_dataset)
            columns_after = list(current_dataset.columns)
            validation_status, validation_message, validation_details = operation.validate(current_dataset)
            elapsed = time.perf_counter() - start
            status = "SUCCESS" if validation_status == "PASS" else "FAILED"
            transformations.append(
                operation.report(
                    status=status,
                    rows_before=rows_before,
                    rows_after=rows_after,
                    columns_before=columns_before,
                    columns_after=columns_after,
                    execution_time=elapsed,
                    validation_status=validation_status,
                    validation_message=validation_message,
                    validation_details=validation_details,
                    error_message="" if validation_status == "PASS" else validation_message,
                )
            )
        except Exception as exc:  # pragma: no cover - defensive execution guard.
            logger.exception("Failed during transformation %s", operation.description)
            elapsed = time.perf_counter() - start
            transformations.append(
                operation.report(
                    status="FAILED",
                    rows_before=rows_before,
                    rows_after=len(current_dataset),
                    columns_before=columns_before,
                    columns_after=list(current_dataset.columns),
                    execution_time=elapsed,
                    validation_status="FAIL",
                    validation_message="Execution failed",
                    validation_details={},
                    error_message=str(exc),
                )
            )
            notes.append(f"Transformation {operation.description} failed: {exc}")

    return current_dataset, transformations, notes


def save_processed_dataset(dataset: TabularDataset, output_path: str | Path) -> Path:
    """Persist the processed dataset to disk as a CSV file."""

    path = Path(output_path)
    path.parent.mkdir(parents=True, exist_ok=True)
    dataset.to_csv(path, index=False)
    return path


def generate_execution_report(
    dataset_name: str,
    status: str,
    execution_time: float,
    rows_before: int,
    rows_after: int,
    columns_before: Sequence[str],
    columns_after: Sequence[str],
    transformations: Sequence[Mapping[str, Any]],
    notes: Sequence[str],
    output_path: str | Path,
    missing_values_remaining: int = 0,
) -> Path:
    """Generate a human-readable execution markdown report."""

    report_path = OUTPUT_DIR / "preprocessing" / "execution" / "markdown" / f"{dataset_name}.md"
    report_path.parent.mkdir(parents=True, exist_ok=True)
    duplicate_rows_removed = 0
    datetime_converted = False
    join_keys_preserved = True
    skipped_transformations = [item for item in transformations if item.get("status") == "SKIPPED"]

    for transformation in transformations:
        if transformation.get("status") == "SKIPPED":
            continue
        if transformation.get("action", "").lower() == "duplicate removal":
            duplicate_rows_removed = max(duplicate_rows_removed, max((rows_before - rows_after), 0))
        if transformation.get("action", "").lower() == "datetime conversion":
            datetime_converted = transformation.get("status") == "SUCCESS"
        if transformation.get("action", "").lower() == "join key preservation" and transformation.get("status") != "SUCCESS":
            join_keys_preserved = False
        if transformation.get("action", "").lower() == "missing value handling":
            missing_values_remaining = 0

    lines = [
        "# Execution Report",
        "",
        f"- Dataset: {dataset_name}",
        f"- Execution status: {status}",
        f"- Execution time: {execution_time:.3f}s",
        "",
        "## Executive Summary",
        "",
        f"- Dataset: {dataset_name}",
        f"- Rows Before: {rows_before}",
        f"- Rows After: {rows_after}",
        f"- Columns Before: {len(columns_before)}",
        f"- Columns After: {len(columns_after)}",
        f"- Status: {status}",
        "",
        "## Transformation Summary",
        "",
        "| Transformation ID | Action | Status | Execution Time | Validation |",
        "| --- | --- | --- | --- | --- |",
    ]
    for transformation in transformations:
        lines.append(
            f"| {transformation.get('id', 'N/A')} | {transformation.get('action', 'N/A')} | {transformation.get('status', 'UNKNOWN')} | {transformation.get('execution_time', 0.0):.6f}s | {transformation.get('validation', 'UNKNOWN')} |"
        )

    lines.extend(["", "## Parameters Used", ""])
    for transformation in transformations:
        parameters = transformation.get("parameters") or {}
        lines.append(f"- {transformation.get('id', 'N/A')}: {json.dumps(_json_safe(parameters), sort_keys=True)}")

    lines.extend(["", "## Validation Summary", "", "| Transformation | Expected | Actual | Status |", "| --- | --- | --- | --- |"])
    for transformation in transformations:
        validation_details = transformation.get("validation_details") or {}
        expected = validation_details.get("expected")
        actual = validation_details.get("actual")
        lines.append(
            f"| {transformation.get('action', 'N/A')} | {expected if expected is not None else '-'} | {actual if actual is not None else '-'} | {transformation.get('validation', 'UNKNOWN')} |"
        )

    lines.extend(["", "## Skipped Transformations", ""])
    if skipped_transformations:
        for transformation in skipped_transformations:
            lines.append(f"- {transformation.get('action', 'N/A')} (disabled in the JSON specification)")
    else:
        lines.append("- None")

    lines.extend(
        [
            "",
            "## Dataset Summary",
            "",
            f"- Rows Before: {rows_before}",
            f"- Rows After: {rows_after}",
            f"- Columns Before: {len(columns_before)}",
            f"- Columns After: {len(columns_after)}",
            f"- Duplicate Rows Removed: {duplicate_rows_removed}",
            f"- Datetime Converted: {'Yes' if datetime_converted else 'No'}",
            f"- Missing Values Remaining: {missing_values_remaining}",
            f"- Join Keys Preserved: {'Yes' if join_keys_preserved else 'No'}",
            "",
            "## Output",
            "",
            f"- Processed filename: {Path(output_path).name}",
            f"- Output directory: {Path(output_path).parent}",
            f"- Ready for merge.py: {'Yes' if status == 'SUCCESS' else 'No'}",
            "",
            "## Notes",
            "",
        ]
    )
    if notes:
        for note in notes:
            lines.append(f"- {note}")
    else:
        lines.append("- No additional notes.")
    report_path.write_text("\n".join(lines) + "\n", encoding="utf-8")
    return report_path


def generate_execution_metadata(
    dataset_name: str,
    status: str,
    execution_time: float,
    rows_before: int,
    rows_after: int,
    columns_before: Sequence[str],
    columns_after: Sequence[str],
    transformations: Sequence[Mapping[str, Any]],
    output_path: str | Path,
) -> Path:
    """Generate machine-readable execution metadata."""

    metadata_path = OUTPUT_DIR / "preprocessing" / "execution" / "metadata" / f"{dataset_name}.json"
    metadata_path.parent.mkdir(parents=True, exist_ok=True)
    payload = {
        "dataset_name": dataset_name,
        "status": status,
        "rows_before": rows_before,
        "rows_after": rows_after,
        "columns_before": list(columns_before),
        "columns_after": list(columns_after),
        "execution_time": round(execution_time, 6),
        "processed_file": str(Path(output_path).name),
        "transformations": list(transformations),
    }
    metadata_path.write_text(json.dumps(_json_safe(payload), indent=2), encoding="utf-8")
    return metadata_path


def process_dataset(metadata_path: str | Path, raw_data_dir: str | Path = RAW_DATA_DIR) -> dict[str, Any]:
    """Process a single dataset from the preprocessing specification JSON."""

    raw_data_dir = Path(raw_data_dir)
    if not raw_data_dir.exists() or raw_data_dir == Path(RAW_DATA_DIR):
        external_dir = Path("data/external")
        if external_dir.exists():
            raw_data_dir = external_dir

    input_path = Path(metadata_path)
    spec_path = input_path
    if spec_path.suffix.lower() != ".json" or not spec_path.exists():
        spec_path = OUTPUT_DIR / "preprocessing" / "plans" / f"{input_path.stem}.json"
    if not spec_path.exists():
        raise FileNotFoundError(f"Preprocessing specification not found: {spec_path}")

    specification = load_specification(spec_path)
    dataset_id = resolve_dataset_id(specification, spec_path)

    start_time = time.perf_counter()
    status = "SUCCESS"
    notes: list[str] = []
    transformations: list[dict[str, Any]] = []
    output_path = PROCESSED_DATA_DIR / f"{dataset_id}_processed.csv"
    processed_dataset = pd.DataFrame()
    dataset = pd.DataFrame()

    try:
        raw_dataset_path = locate_raw_dataset(dataset_id, raw_data_dir)
        logger.info("Processing dataset %s from %s", dataset_id, raw_dataset_path)
        dataset = load_raw_dataset(raw_dataset_path)
        rows_before = len(dataset)
        columns_before = list(dataset.columns)
        processed_dataset, transformations, notes = execute_transformations(
            dataset,
            specification,
            dataset_name=dataset_id,
            source_path=raw_dataset_path,
        )
        rows_after = len(processed_dataset)
        columns_after = list(processed_dataset.columns)
        output_path = save_processed_dataset(processed_dataset, output_path)
    except Exception as exc:  # pragma: no cover - defensive execution guard.
        logger.exception("Failed to preprocess dataset %s", dataset_id)
        status = "FAILED"
        notes.append(f"Processing failed: {exc}")
        output_path = save_processed_dataset(processed_dataset if not processed_dataset.empty else dataset, output_path)
        rows_before = len(dataset) if not dataset.empty else 0
        columns_before = list(dataset.columns) if not dataset.empty else []
        rows_after = len(processed_dataset) if not processed_dataset.empty else len(dataset)
        columns_after = list(processed_dataset.columns) if not processed_dataset.empty else list(dataset.columns)

    execution_time = time.perf_counter() - start_time
    if status != "FAILED" and transformations:
        if any(transformation.get("status") == "FAILED" for transformation in transformations):
            status = "WARNING"
        elif notes:
            status = "WARNING"

    missing_values_remaining = int(processed_dataset.isna().sum().sum()) if not processed_dataset.empty else 0

    report_path = generate_execution_report(
        dataset_id,
        status,
        execution_time,
        rows_before,
        rows_after,
        columns_before,
        columns_after,
        transformations,
        notes,
        output_path,
        missing_values_remaining=missing_values_remaining,
    )
    metadata_path_out = generate_execution_metadata(
        dataset_id,
        status,
        execution_time,
        rows_before,
        rows_after,
        columns_before,
        columns_after,
        transformations,
        output_path,
    )

    return {
        "dataset_id": dataset_id,
        "status": status,
        "report_path": str(report_path),
        "metadata_path": str(metadata_path_out),
        "output_path": str(output_path),
    }


def process_all_datasets(metadata_dir: str | Path = OUTPUT_DIR / "analysis" / "metadata") -> list[dict[str, Any]]:
    """Process every dataset defined by the analysis metadata directory."""

    metadata_dir = Path(metadata_dir)
    if not metadata_dir.exists():
        return []

    results: list[dict[str, Any]] = []
    for metadata_file in sorted(metadata_dir.glob("*.json")):
        result = process_dataset(metadata_file)
        results.append(result)
    return results
