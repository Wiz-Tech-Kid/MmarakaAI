# Preprocessing Plan (P1)

Dataset Name: 02_brent_crude_monthly

Pipeline Position: Raw audit metadata -> preprocessing implementation -> merge and modeling workflow

Purpose of this document: This engineering plan translates the findings captured by analysis.py into a concrete preprocessing execution blueprint for preprocessing.py. It explains what was observed, why the transformation is required, what will change, and how success will be verified.

## Executive Summary

- Dataset Name: 02_brent_crude_monthly
- Rows: 288
- Columns: 2
- Current Dataset Structure: Rectangular tabular data
- Candidate Join Keys: Date
- Number of Planned Transformations: 6
- Transformation Risk: High
- Expected Output Dataset: A cleaned and structurally consistent dataset prepared for downstream merge and modeling steps.

## Dataset Overview

For 02_brent_crude_monthly, the metadata already confirms 288 rows, 2 columns, 0.0% missing values, and a rectangular tabular data layout with Date as the merge-relevant key. The preprocessing layer should use those exact observations as the authoritative basis for implementation rather than re-deriving assumptions from the raw files.

- Current schema: Date (object); Brent_USD_per_barrel (float64)
- Detected structure: Standard rectangular dataset
- Time-series characteristics: Monthly-like
- Duplicate observations: 0
- Missing values: 0.0% missing overall
- Join keys: Date
- Observed data quality: 0.0 missing share, with duplicate and datetime considerations captured directly in the metadata.
- Panel structure: No long-format panel transformation is indicated by the metadata.
- Analysis evidence references: boxplot=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/02_brent_crude_monthly_boxplot.png, histogram=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/02_brent_crude_monthly_histogram.png, missing=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/02_brent_crude_monthly_missing.png, time_series=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/02_brent_crude_monthly_timeseries.png

## Planned Transformations

The following table captures each preprocessing action that should be implemented in preprocessing.py. Each row records the engineering rationale, priority, expected effect, and the validation condition that should be checked after execution.

| Transformation ID | Category | Action | Reason | Priority | Risk | Expected Effect | Expected Validation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P001 | Datetime | Convert Date to datetime | The metadata shows Date is still typed as object and the audit also found 0 duplicate date values with a Monthly-like cadence, so conversion to datetime is necessary for chronological ordering and joins. | High | Medium | Date will become a proper datetime field and the table will be usable for date-based sorting, lag features, and time-aware merges. | Verify Date parses as datetime and retains the same earliest and latest values after conversion. |
| P002 | Datetime_Checks | Verify datetime conversion | The analysis metadata tracks Date as a date-like field and the dataset-specific checks rely on consistent date parsing, so this verification step should confirm the conversion was successful. | Medium | Medium | The preprocessing pipeline will confirm that Date is consistently parsed and ready for time-based joins and feature engineering. | Verify Date is datetime-typed and that the parsed values still match the recorded date range. |
| P003 | Schema_Checks | Verify expected columns | The audit exposes a schema of Date (object); Brent_USD_per_barrel (float64), so preprocessing should confirm that the expected columns remain present and correctly typed. | Medium | Medium | The cleaned dataset will preserve the expected column set and avoid schema drift before merge.py consumes it. | Verify the expected columns Date, Brent_USD_per_barrel remain in the output schema after preprocessing. |
| P004 | Row_Count_Checks | Verify row counts | The source metadata reports 288 rows and 0 duplicate rows, so row-count validation is required to ensure the cleaned dataset still reflects the intended grain. | Medium | Medium | The preprocessing step will confirm the table is not unexpectedly inflated or reduced during cleaning. | Verify the output row count is 288 when duplicates are removed and no other rows are lost. |
| P005 | Row_Count_Checks | Verify row counts | The source metadata reports 288 rows and 0 duplicate rows, so row-count validation is required to ensure the cleaned dataset still reflects the intended grain. | Medium | Medium | The preprocessing step will confirm the table is not unexpectedly inflated or reduced during cleaning. | Verify the output row count is 288 after preprocessing. |
| P006 | Join Keys | Preserve and validate merge keys | The audit metadata identifies Date as the alignment key for downstream joins, so preprocessing must preserve that key in a consistent form. | Medium | Medium | Merge.py will be able to align this dataset with the other time-series tables using Date without schema ambiguity. | Verify Date remains present and consistent after preprocessing. |

## Structural Changes

For 02_brent_crude_monthly, the structural changes are driven by the specific audit findings for this table rather than a generic cleaning checklist.

- Schema transition: Before: Date (object); Brent_USD_per_barrel (float64). After: Date (object); Brent_USD_per_barrel (float64)
- Datetime normalization: The date-like column should be converted into a consistent datetime dtype so that time-based joins, sorting, and feature generation are reliable.
- Merge-key preservation: The join-key columns should remain explicit and stable so that merge.py can align this dataset with the other input tables without ambiguity.

## Validation Plan

Preprocessing.py should validate each transformation immediately after implementation so that failures surface before the dataset reaches merge.py or the modeling stack.

- P001 (Datetime): Verify Date parses as datetime and retains the same earliest and latest values after conversion.
- P002 (Datetime_Checks): Verify Date is datetime-typed and that the parsed values still match the recorded date range.
- P003 (Schema_Checks): Verify the expected columns Date, Brent_USD_per_barrel remain in the output schema after preprocessing.
- P004 (Row_Count_Checks): Verify the output row count is 288 when duplicates are removed and no other rows are lost.
- P005 (Join Keys): Verify Date remains present and consistent after preprocessing.

## Expected Output Dataset

For 02_brent_crude_monthly, the expected output is a cleaned and schema-stable artifact that preserves the metadata-defined identity and merge structure while removing the issues flagged by the audit.

- Expected filename: Not Available in metadata
- Expected directory: Not Available in metadata
- Expected structure: Rectangular tabular structure
- Expected key: Date
- Expected schema: Before: Date (object); Brent_USD_per_barrel (float64). After: Date (object); Brent_USD_per_barrel (float64)
- Expected row count: 288
- Expected column count: 2
- Expected readiness for merge.py: Yes, provided the join keys remain intact

## Pipeline Impact

This preprocessing plan is intended to improve the downstream execution path without changing the repository architecture or introducing new data dependencies.

- merge.py: Cleaner row-level structure and preserved join keys will make merges more deterministic and less error-prone.
- feature engineering: Standardized datetime and schema handling will make lag, rolling, and time-based feature generation more reliable.
- classic ML: Duplicate removal and schema stability will reduce leakage risks and improve model training consistency.
- deep learning: A cleaner and more consistent input matrix will make training batches more predictable and easier to debug.
- evaluation: Fewer duplicate or malformed records will lead to more trustworthy model evaluation metrics.

##  Notes

These notes capture the non-functional assumptions and implementation boundaries that should remain explicit while preprocessing.py is implemented.

- Assumptions: The plan is derived strictly from the analysis metadata generated by analysis.py and does not rely on raw-data inspection.
- Transformations intentionally not performed: No feature generation, outlier clipping, or domain-specific imputation is inferred here because the metadata does not provide enough evidence for those steps.
- Transformations deferred to preprocessing.py: Final output naming, serialization format, and any implementation-specific missing-data policy should be decided inside preprocessing.py.
- Manual review: If the metadata indicates ambiguous join keys or edge-case business rules, those cases should be reviewed before implementation.

---

## Detailed Execution Specification

This dataset does not require reshaping because it already exists as a rectangular monthly time series. Preprocessing shall convert the Date column from object to datetime using automatic format detection while preserving every recorded monthly observation. Invalid dates shall be handled according to the preprocessing policy without silently modifying valid observations.

After datetime conversion the dataset shall be sorted chronologically in ascending order using Date. Since the analysis detected no duplicate observations and no missing values, preprocessing shall validate rather than modify these properties. Duplicate validation shall confirm zero duplicated observations and missing value validation shall confirm that no null values exist after preprocessing.

The dataset schema shall remain unchanged. The columns Date and Brent_USD_per_barrel shall remain in their existing order and datatype except for Date becoming datetime. No columns shall be renamed, removed or generated during preprocessing.

The completed dataset shall contain 288 observations, two columns, chronological monthly ordering, zero duplicates, zero missing values and a datetime Date column suitable for downstream merging and feature engineering.

