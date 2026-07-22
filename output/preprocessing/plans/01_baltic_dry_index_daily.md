# Preprocessing Plan (P1)

Dataset Name: 01_baltic_dry_index_daily

Pipeline Position: Raw audit metadata -> preprocessing implementation -> merge and modeling workflow

Purpose of this document: This engineering plan translates the findings captured by analysis.py into a concrete preprocessing execution blueprint for preprocessing.py. It explains what was observed, why the transformation is required, what will change, and how success will be verified.

## Executive Summary

- Dataset Name: 01_baltic_dry_index_daily
- Rows: 5992
- Columns: 4
- Current Dataset Structure: Rectangular tabular data
- Candidate Join Keys: Not Available
- Number of Planned Transformations: 8
- Transformation Risk: High
- Expected Output Dataset: A cleaned and structurally consistent dataset prepared for downstream merge and modeling steps.

## Dataset Overview

For 01_baltic_dry_index_daily, the metadata already confirms 5992 rows, 4 columns, 0.0% missing values, and a rectangular tabular data layout with Not Available as the merge-relevant key. The preprocessing layer should use those exact observations as the authoritative basis for implementation rather than re-deriving assumptions from the raw files.

- Current schema: Date (object); BDI_Close (float64); BDI_High (float64); BDI_Low (float64)
- Detected structure: Standard rectangular dataset
- Time-series characteristics: Business-day-like
- Duplicate observations: 3
- Missing values: 0.0% missing overall
- Join keys: Not Available
- Observed data quality: 0.0 missing share, with duplicate and datetime considerations captured directly in the metadata.
- Panel structure: No long-format panel transformation is indicated by the metadata.
- Analysis evidence references: boxplot=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/01_baltic_dry_index_daily_boxplot.png, correlation=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/01_baltic_dry_index_daily_correlation.png, histogram=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/01_baltic_dry_index_daily_histogram.png, missing=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/01_baltic_dry_index_daily_missing.png, time_series=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/01_baltic_dry_index_daily_timeseries.png

## Planned Transformations

The following table captures each preprocessing action that should be implemented in preprocessing.py. Each row records the engineering rationale, priority, expected effect, and the validation condition that should be checked after execution.

| Transformation ID | Category | Action | Reason | Priority | Risk | Expected Effect | Expected Validation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P001 | Duplicate_Removal | Remove duplicate rows | The audit recorded 3 duplicated rows in 01_baltic_dry_index_daily, so removing them is required to preserve the intended observation grain before merge or modeling. | High | Medium | The cleaned table should shrink from 5992 rows to 5989 rows and avoid repeated observations. | Verify the cleaned dataset has 0 duplicate rows and a final row count of 5989. |
| P002 | Datetime | Convert Date to datetime | The metadata shows Date is still typed as object and the audit also found 3 duplicate date values with a Business-day-like cadence, so conversion to datetime is necessary for chronological ordering and joins. | High | Medium | Date will become a proper datetime field and the table will be usable for date-based sorting, lag features, and time-aware merges. | Verify Date parses as datetime and retains the same earliest and latest values after conversion. |
| P003 | Sorting | Sort chronologically by Date | The audit reports a Business-day-like temporal cadence and a monotonic order was not preserved in the metadata, so the table should be ordered chronologically before downstream work. | Medium | Medium | The rows will be arranged from earliest to latest Date, creating a stable time series for feature generation and merging. | Verify the rows are ordered chronologically by Date after preprocessing. |
| P004 | Duplicate_Checks | Verify duplicate removal | The metadata records 3 duplicate rows, so preprocessing should confirm that these redundancies have been removed before the dataset is passed onward. | Medium | Medium | The duplicate check will confirm that the dataset now carries a clean one-row-per-observation grain. | Verify the cleaned dataset reports 0 duplicate rows and no duplicate Date values remain. |
| P005 | Datetime_Checks | Verify datetime conversion | The analysis metadata tracks Date as a date-like field and the dataset-specific checks rely on consistent date parsing, so this verification step should confirm the conversion was successful. | Medium | Medium | The preprocessing pipeline will confirm that Date is consistently parsed and ready for time-based joins and feature engineering. | Verify Date is datetime-typed and that the parsed values still match the recorded date range. |
| P006 | Schema_Checks | Verify expected columns | The audit exposes a schema of Date (object); BDI_Close (float64); BDI_High (float64); BDI_Low (float64), so preprocessing should confirm that the expected columns remain present and correctly typed. | Medium | Medium | The cleaned dataset will preserve the expected column set and avoid schema drift before merge.py consumes it. | Verify the expected columns Date, BDI_Close, BDI_High, BDI_Low remain in the output schema after preprocessing. |
| P007 | Row_Count_Checks | Verify row counts | The source metadata reports 5992 rows and 3 duplicate rows, so row-count validation is required to ensure the cleaned dataset still reflects the intended grain. | Medium | Medium | The preprocessing step will confirm the table is not unexpectedly inflated or reduced during cleaning. | Verify the output row count is 5989 when duplicates are removed and no other rows are lost. |
| P008 | Join Keys | Preserve and validate merge keys | The audit metadata identifies Date as the alignment key for downstream joins, so preprocessing must preserve that key in a consistent form. | Medium | Medium | Merge.py will be able to align this dataset with the other time-series tables using Date without schema ambiguity. | Verify Date remains present and consistent after preprocessing. |

## Structural Changes

For 01_baltic_dry_index_daily, the structural changes are driven by the specific audit findings for this table rather than a generic cleaning checklist.

- Schema transition: Before: Date (object), BDI_Close (float64), BDI_High (float64), BDI_Low (float64). After: Date (datetime64[ns]), BDI_Close (float64), BDI_High (float64), BDI_Low (float64), with duplicate trading-day rows removed and the table ordered chronologically.
- Datetime normalization: The date-like column should be converted into a consistent datetime dtype so that time-based joins, sorting, and feature generation are reliable.
- Duplicate handling: Duplicate rows should be removed so that the final dataset reflects the intended grain of observation, reducing row-level redundancy and preventing duplicate records from affecting downstream metrics.
- Merge-key preservation: The join-key columns should remain explicit and stable so that merge.py can align this dataset with the other input tables without ambiguity.

## Validation Plan

Preprocessing.py should validate each transformation immediately after implementation so that failures surface before the dataset reaches merge.py or the modeling stack.

- P001 (Duplicate_Removal): Verify the cleaned dataset has 0 duplicate rows and a final row count of 5989.
- P002 (Datetime): Verify Date parses as datetime and retains the same earliest and latest values after conversion.
- P003 (Sorting): Verify the rows are ordered chronologically by Date after preprocessing.
- P004 (Duplicate_Checks): Verify the cleaned dataset reports 0 duplicate rows and no duplicate Date values remain.
- P005 (Datetime_Checks): Verify Date is datetime-typed and that the parsed values still match the recorded date range.
- P006 (Schema_Checks): Verify the expected columns Date, BDI_Close, BDI_High, BDI_Low remain in the output schema after preprocessing.
- P007 (Row_Count_Checks): Verify the output row count is 5989 when duplicates are removed and no other rows are lost.
- P008 (Join Keys): Verify Date remains present and consistent after preprocessing.

## Expected Output Dataset

For 01_baltic_dry_index_daily, the expected output is a cleaned and schema-stable artifact that preserves the metadata-defined identity and merge structure while removing the issues flagged by the audit.

- Expected filename: Not Available in metadata
- Expected directory: Not Available in metadata
- Expected structure: Rectangular tabular structure
- Expected key: Not Available
- Expected schema: Before: Date (object), BDI_Close (float64), BDI_High (float64), BDI_Low (float64). After: Date (datetime64[ns]), BDI_Close (float64), BDI_High (float64), BDI_Low (float64), with duplicate trading-day rows removed and the table ordered chronologically.
- Expected row count: 5989
- Expected column count: 4
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

This dataset contains daily observations of the Baltic Dry Index, while the target variable for this project, Botswana Food Price Inflation, is reported at a monthly frequency. Therefore, preprocessing shall not only perform structural cleaning, but shall also transform the dataset into a statistically representative monthly dataset suitable for downstream integration and modelling.

Preprocessing shall begin by identifying duplicate observations using the complete observation composed of Date, BDI_Close, BDI_High, and BDI_Low. Duplicate detection shall use the complete row rather than the Date column alone. The first occurrence of every duplicated observation shall be retained while all subsequent duplicates shall be removed. The preprocessing stage shall validate that all duplicate observations have been successfully removed.

The Date column shall then be converted from an object datatype to a standardized datetime datatype using automatic format detection. Invalid dates shall be handled according to the preprocessing policy. Following conversion, the dataset shall be sorted in ascending chronological order to ensure a consistent temporal sequence for subsequent processing.

Following structural cleaning, preprocessing shall perform Temporal Statistical Aggregation. Daily observations shall first be partitioned into calendar weeks using the Date column. Weekly aggregation shall preserve the behaviour of the original daily time series and shall become the primary statistical representation of the dataset. Under no circumstances shall the daily observations be reduced directly to simple monthly averages, as doing so would discard valuable information regarding short-term market behaviour and intra-month variability.

For every calendar week, preprocessing shall compute the following statistical features independently for each numerical variable (BDI_Close, BDI_High, and BDI_Low):

Mean
Median
Standard Deviation
Range (Maximum − Minimum)
Percentage Change

These weekly statistical summaries shall preserve the central tendency, volatility, price spread, and directional movement observed during each week.

Once weekly statistical summaries have been generated, preprocessing shall construct the final monthly feature representation. The monthly dataset shall be derived from the weekly statistical summaries rather than directly from the raw daily observations. This approach preserves substantially more information from the original time series while producing a dataset that is fully compatible with the monthly frequency of the remaining project datasets.

The final output dataset shall contain one observation per calendar month. Each monthly observation shall contain the statistical features derived from the weekly summaries together with a standardized monthly Date field suitable for downstream merging.

Preprocessing shall validate that every month represented in the original dataset is preserved in the transformed dataset. Validation shall further confirm that all generated statistical features are numeric, free from missing values, and internally consistent. The resulting monthly dataset shall be considered the authoritative version for feature engineering, dataset integration, and machine learning.

