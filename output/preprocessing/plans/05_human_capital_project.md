# Preprocessing Plan (P1)

Dataset Name: 05_human_capital_project

Pipeline Position: Raw audit metadata -> preprocessing implementation -> merge and modeling workflow

Purpose of this document: This engineering plan translates the findings captured by analysis.py into a concrete preprocessing execution blueprint for preprocessing.py. It explains what was observed, why the transformation is required, what will change, and how success will be verified.

## Executive Summary

- Dataset Name: 05_human_capital_project
- Rows: 4320
- Columns: 6
- Current Dataset Structure: Long-format panel data
- Candidate Join Keys: Date + REF_AREA + INDICATOR
- Number of Planned Transformations: 8
- Transformation Risk: High
- Expected Output Dataset: A cleaned and structurally consistent dataset prepared for downstream merge and modeling steps.

## Dataset Overview

For 05_human_capital_project, the metadata already confirms 4320 rows, 6 columns, 0.23% missing values, and a long-format panel data layout with Date + REF_AREA + INDICATOR as the merge-relevant key. The preprocessing layer should use those exact observations as the authoritative basis for implementation rather than re-deriving assumptions from the raw files.

- Current schema: Date (object); REF_AREA (object); REF_AREA_LABEL (object); INDICATOR (object); INDICATOR_LABEL (object); Value (float64)
- Detected structure: Panel/long-format dataset
- Time-series characteristics: MS
- Duplicate observations: 0
- Missing values: 0.23% missing overall
- Join keys: Date + REF_AREA + INDICATOR
- Observed data quality: 0.23 missing share, with duplicate and datetime considerations captured directly in the metadata.
- Panel structure: Long-format identity columns are present and should be preserved during reshaping.
- Analysis evidence references: boxplot=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/05_human_capital_project_boxplot.png, histogram=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/05_human_capital_project_histogram.png, missing=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/05_human_capital_project_missing.png, time_series=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/05_human_capital_project_timeseries.png

## Planned Transformations

The following table captures each preprocessing action that should be implemented in preprocessing.py. Each row records the engineering rationale, priority, expected effect, and the validation condition that should be checked after execution.

| Transformation ID | Category | Action | Reason | Priority | Risk | Expected Effect | Expected Validation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P001 | Reshape | Pivot indicator rows into columns | The audit exposes a schema of Date (object); REF_AREA (object); REF_AREA_LABEL (object); INDICATOR (object); INDICATOR_LABEL (object); Value (float64), so preprocessing should confirm that the expected columns remain present and correctly typed. | High | Medium | The cleaned dataset will preserve the expected column set and avoid schema drift before merge.py consumes it. | Verify the expected columns Date, REF_AREA, REF_AREA_LABEL, INDICATOR, INDICATOR_LABEL, Value remain in the output schema after preprocessing. |
| P002 | Column_Management | Preserve Country and Date columns | The audit exposes a schema of Date (object); REF_AREA (object); REF_AREA_LABEL (object); INDICATOR (object); INDICATOR_LABEL (object); Value (float64), so preprocessing should confirm that the expected columns remain present and correctly typed. | High | Medium | The cleaned dataset will preserve the expected column set and avoid schema drift before merge.py consumes it. | Verify the expected columns Date, REF_AREA, REF_AREA_LABEL, INDICATOR, INDICATOR_LABEL, Value remain in the output schema after preprocessing. |
| P003 | Datetime_Checks | Verify datetime conversion | The analysis metadata tracks Date as a date-like field and the dataset-specific checks rely on consistent date parsing, so this verification step should confirm the conversion was successful. | Medium | Medium | The preprocessing pipeline will confirm that Date is consistently parsed and ready for time-based joins and feature engineering. | Verify Date is datetime-typed and that the parsed values still match the recorded date range. |
| P004 | Schema_Checks | Verify expected columns | The audit exposes a schema of Date (object); REF_AREA (object); REF_AREA_LABEL (object); INDICATOR (object); INDICATOR_LABEL (object); Value (float64), so preprocessing should confirm that the expected columns remain present and correctly typed. | Medium | Medium | The cleaned dataset will preserve the expected column set and avoid schema drift before merge.py consumes it. | Verify the expected columns Date, REF_AREA, REF_AREA_LABEL, INDICATOR, INDICATOR_LABEL, Value remain in the output schema after preprocessing. |
| P005 | Row_Count_Checks | Verify row counts | The source metadata reports 4320 long-format rows and the reshaped output should contain 1440 rows, one row per unique Date and REF_AREA, so row-count validation is required to ensure the cleaned dataset still reflects the intended grain. | Medium | Medium | The preprocessing step will confirm the table is not unexpectedly inflated or reduced during cleaning. | Verify the output row count is 4320 when duplicates are removed and no other rows are lost. |
| P006 | Datetime | Convert date-like columns to datetime | The metadata shows Date is still typed as object and the audit also found 4032 duplicate date values with a MS cadence, so conversion to datetime is necessary for chronological ordering and joins. | High | Medium | Date will become a proper datetime field and the table will be usable for date-based sorting, lag features, and time-aware merges. | Verify Date parses as datetime and retains the same earliest and latest values after conversion. |
| P007 | Join Keys | Preserve and validate merge keys | The audit metadata identifies Date + REF_AREA + INDICATOR as the alignment key for downstream joins, so preprocessing must preserve that key in a consistent form. | Medium | Medium | Merge.py will be able to align this dataset with the other time-series tables using Date + REF_AREA + INDICATOR without schema ambiguity. | Verify Date + REF_AREA + INDICATOR remains present and consistent after preprocessing. |
| P008 | Missing Values | Review and resolve missing values | The audit recorded 0.23% missing values, concentrated in Value, so missing-value handling is required before modeling. | Medium | Medium | The cleaned dataset will avoid null-driven distortions in downstream statistics and model training. | Verify missing values are handled consistently and that no unexpected nulls are introduced during the transformation. |

## Structural Changes

For 05_human_capital_project, the structural changes are driven by the specific audit findings for this table rather than a generic cleaning checklist.

- Schema transition: Before: Date (object), REF_AREA (object), REF_AREA_LABEL (object), INDICATOR (object), INDICATOR_LABEL (object), Value (float64) in a long-format panel with one row per indicator observation. After: the same identity columns remain present, but the datetime field is normalized and the panel layout is reshaped into a stable indicator-aware structure for downstream modeling.
- Long-format handling: The plan should preserve the panel identity columns and reshape the measurement values into a structure that can be consumed by merge.py and model training code.
- Datetime normalization: The date-like column should be converted into a consistent datetime dtype so that time-based joins, sorting, and feature generation are reliable.
- Merge-key preservation: The join-key columns should remain explicit and stable so that merge.py can align this dataset with the other input tables without ambiguity.
- Missing-value handling: Any missing values should be addressed in a controlled way so that downstream statistics and model training are not skewed by nulls.

## Validation Plan

Preprocessing.py should validate each transformation immediately after implementation so that failures surface before the dataset reaches merge.py or the modeling stack.

- P001 (Reshape): Verify the expected columns Date, REF_AREA, REF_AREA_LABEL, INDICATOR, INDICATOR_LABEL, Value remain in the output schema after preprocessing.
- P002 (Column_Management): Verify the expected columns Date, REF_AREA, REF_AREA_LABEL, INDICATOR, INDICATOR_LABEL, Value remain in the output schema after preprocessing.
- P003 (Datetime_Checks): Verify Date is datetime-typed and that the parsed values still match the recorded date range.
- P004 (Schema_Checks): Verify the expected columns Date, REF_AREA, REF_AREA_LABEL, INDICATOR, INDICATOR_LABEL, Value remain in the output schema after preprocessing.
- P005 (Row_Count_Checks): Verify the output row count is 4320 when duplicates are removed and no other rows are lost.
- P006 (Datetime): Verify Date parses as datetime and retains the same earliest and latest values after conversion.
- P007 (Join Keys): Verify Date + REF_AREA + INDICATOR remains present and consistent after preprocessing.
- P008 (Missing Values): Verify missing values are handled consistently and that no unexpected nulls are introduced during the transformation.

## Expected Output Dataset

For 05_human_capital_project, the expected output is a cleaned and schema-stable artifact that preserves the metadata-defined identity and merge structure while removing the issues flagged by the audit.

- Expected filename: Not Available in metadata
- Expected directory: Not Available in metadata
- Expected structure: Long-format panel data will be reshaped where required
- Expected key: Date + REF_AREA + INDICATOR
- Expected schema: Before: Date (object), REF_AREA (object), REF_AREA_LABEL (object), INDICATOR (object), INDICATOR_LABEL (object), Value (float64) in a long-format panel with one row per indicator observation. After: the same identity columns remain present, but the datetime field is normalized and the panel layout is reshaped into a stable indicator-aware structure for downstream modeling.
- Expected row count: 1440 (one row per unique Date and REF_AREA after reshaping)
- Expected column count: 6
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

This dataset is a longitudinal panel dataset containing multiple development indicators measured for each country and reporting period. The long format is appropriate for storage but not for downstream machine learning and therefore preprocessing shall reshape the dataset into a wide panel where every observation represents a unique country and reporting period while each indicator becomes an independent feature column.

The preprocessing stage shall first convert Date into datetime using automatic format detection. The reshaping operation shall then use Date together with REF_AREA as the observation identifier while REF_AREA_LABEL shall be retained as descriptive metadata. The INDICATOR column shall define the names of the generated feature columns and the Value column shall populate the values of those features. Whenever duplicate combinations of Date, REF_AREA and INDICATOR are encountered the first valid observation shall be retained.

The preprocessing stage shall validate that every Date and REF_AREA combination appears exactly once after reshaping and that every unique indicator has been transformed into an independent feature column. Country identifiers shall be preserved throughout preprocessing and shall never be modified or inferred.

Missing values shall be handled only within the generated feature columns using the preprocessing policy selected for the project. Identity columns including Date, REF_AREA and REF_AREA_LABEL shall never be imputed or altered.

The completed dataset shall contain one observation for every Date and REF_AREA combination, a datetime Date column, preserved country identifiers, one feature column for every development indicator, chronological ordering, structural consistency across all reporting periods and a schema ready for merge.py and downstream modelling.

