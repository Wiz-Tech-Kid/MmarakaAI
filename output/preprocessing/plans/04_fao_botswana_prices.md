# Preprocessing Plan (P1)

Dataset Name: 04_fao_botswana_prices

Pipeline Position: Raw audit metadata -> preprocessing implementation -> merge and modeling workflow

Purpose of this document: This engineering plan translates the findings captured by analysis.py into a concrete preprocessing execution blueprint for preprocessing.py. It explains what was observed, why the transformation is required, what will change, and how success will be verified.

## Executive Summary

- Dataset Name: 04_fao_botswana_prices
- Rows: 852
- Columns: 4
- Current Dataset Structure: Long-format panel data
- Candidate Join Keys: Date + Item Code
- Number of Planned Transformations: 6
- Transformation Risk: High
- Expected Output Dataset: A cleaned and structurally consistent dataset prepared for downstream merge and modeling steps.

## Dataset Overview

For 04_fao_botswana_prices, the metadata already confirms 852 rows, 4 columns, 0.0% missing values, and a long-format panel data layout with Date + Item Code as the merge-relevant key. The preprocessing layer should use those exact observations as the authoritative basis for implementation rather than re-deriving assumptions from the raw files.

- Current schema: Date (object); Item Code (int64); Item (object); Value (float64)
- Detected structure: Panel/long-format dataset
- Time-series characteristics: MS
- Duplicate observations: 0
- Missing values: 0.0% missing overall
- Join keys: Date + Item Code
- Observed data quality: 0.0 missing share, with duplicate and datetime considerations captured directly in the metadata.
- Panel structure: Long-format identity columns are present and should be preserved during reshaping.
- Analysis evidence references: boxplot=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/04_fao_botswana_prices_boxplot.png, histogram=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/04_fao_botswana_prices_histogram.png, missing=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/04_fao_botswana_prices_missing.png, time_series=/home/nickel/Documents/New Folder/MmarakaAI/output/analysis/figures/04_fao_botswana_prices_timeseries.png

## Planned Transformations

The following table captures each preprocessing action that should be implemented in preprocessing.py. Each row records the engineering rationale, priority, expected effect, and the validation condition that should be checked after execution.

| Transformation ID | Category | Action | Reason | Priority | Risk | Expected Effect | Expected Validation |
| --- | --- | --- | --- | --- | --- | --- | --- |
| P001 | Reshape | Pivot Long to Wide | The metadata classifies the dataset as long-format panel data with repeated rows for the same temporal and identifier dimensions, so reshaping is required to create a model-ready layout. | High | Medium | The output table will use a stable rectangular structure with explicit identifiers and one measurement value per intended observation. | Verify the reshaped table preserves the long-format identity columns and that each record still maps to the correct date and identifier combination. |
| P002 | Column_Management | Rename indicator columns | The audit exposes a schema of Date (object); Item Code (int64); Item (object); Value (float64), so preprocessing should confirm that the expected columns remain present and correctly typed. | Medium | Medium | The cleaned dataset will preserve the expected column set and avoid schema drift before merge.py consumes it. | Verify the expected columns Date, Item Code, Item, Value remain in the output schema after preprocessing. |
| P003 | Datetime_Checks | Verify datetime conversion | The analysis metadata tracks Date as a date-like field and the dataset-specific checks rely on consistent date parsing, so this verification step should confirm the conversion was successful. | Medium | Medium | The preprocessing pipeline will confirm that Date is consistently parsed and ready for time-based joins and feature engineering. | Verify Date is datetime-typed and that the parsed values still match the recorded date range. |
| P004 | Schema_Checks | Verify expected columns | The audit exposes a schema of Date (object); Item Code (int64); Item (object); Value (float64), so preprocessing should confirm that the expected columns remain present and correctly typed. | Medium | Medium | The cleaned dataset will preserve the expected column set and avoid schema drift before merge.py consumes it. | Verify the expected columns Date, Item Code, Item, Value remain in the output schema after preprocessing. |
| P005 | Row_Count_Checks | Verify row counts | The source metadata reports 852 long-format rows and the reshaped output should contain 288 rows, one row per unique Date, so row-count validation is required to ensure the cleaned dataset still reflects the intended grain. | Medium | Medium | The preprocessing step will confirm the table is not unexpectedly inflated or reduced during cleaning. | Verify the output row count is 852 when duplicates are removed and no other rows are lost. |
| P006 | Datetime | Convert date-like columns to datetime | The metadata shows Date is still typed as object and the audit also found 564 duplicate date values with a MS cadence, so conversion to datetime is necessary for chronological ordering and joins. | High | Medium | Date will become a proper datetime field and the table will be usable for date-based sorting, lag features, and time-aware merges. | Verify Date parses as datetime and retains the same earliest and latest values after conversion. |
| P007 | Join Keys | Preserve and validate merge keys | The audit metadata identifies Date + Item Code as the alignment key for downstream joins, so preprocessing must preserve that key in a consistent form. | Medium | Medium | Merge.py will be able to align this dataset with the other time-series tables using Date + Item Code without schema ambiguity. | Verify Date + Item Code remains present and consistent after preprocessing. |

## Structural Changes

For 04_fao_botswana_prices, the structural changes are driven by the specific audit findings for this table rather than a generic cleaning checklist.

- Schema transition: Before: Date (object), Item Code (int64), Item (object), Value (float64) in a long-format panel with repeated monthly rows per item. After: Date (datetime64[ns]), Item Code (int64), Item (object), Value (float64) in a standardized long-format structure with the same identity columns preserved for merge.py.
- Long-format handling: The plan should preserve the panel identity columns and reshape the measurement values into a structure that can be consumed by merge.py and model training code.
- Datetime normalization: The date-like column should be converted into a consistent datetime dtype so that time-based joins, sorting, and feature generation are reliable.
- Merge-key preservation: The join-key columns should remain explicit and stable so that merge.py can align this dataset with the other input tables without ambiguity.

## Validation Plan

Preprocessing.py should validate each transformation immediately after implementation so that failures surface before the dataset reaches merge.py or the modeling stack.

- P001 (Reshape): Verify the reshaped table preserves the long-format identity columns and that each record still maps to the correct date and identifier combination.
- P002 (Column_Management): Verify the expected columns Date, Item Code, Item, Value remain in the output schema after preprocessing.
- P003 (Datetime_Checks): Verify Date is datetime-typed and that the parsed values still match the recorded date range.
- P004 (Schema_Checks): Verify the expected columns Date, Item Code, Item, Value remain in the output schema after preprocessing.
- P005 (Row_Count_Checks): Verify the output row count is 852 when duplicates are removed and no other rows are lost.
- P006 (Datetime): Verify Date parses as datetime and retains the same earliest and latest values after conversion.
- P007 (Join Keys): Verify Date + Item Code remains present and consistent after preprocessing.

## Expected Output Dataset

For 04_fao_botswana_prices, the expected output is a cleaned and schema-stable artifact that preserves the metadata-defined identity and merge structure while removing the issues flagged by the audit.

- Expected filename: Not Available in metadata
- Expected directory: Not Available in metadata
- Expected structure: Long-format panel data will be reshaped where required
- Expected key: Date + Item Code
- Expected schema: Before: Date (object), Item Code (int64), Item (object), Value (float64) in a long-format panel with repeated monthly rows per item. After: Date (datetime64[ns]), Item Code (int64), Item (object), Value (float64) in a standardized long-format structure with the same identity columns preserved for merge.py.
- Expected row count: 288 (one row per unique Date after reshaping)
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

This dataset represents multiple consumer price indicators recorded for the same monthly observation and therefore the repeated monthly rows are expected characteristics of the long format rather than duplicate observations. The dataset shall be reshaped from long format into wide format so that each monthly observation occupies a single row and each consumer price indicator becomes an independent feature column.

The preprocessing stage shall first convert Date into datetime using automatic format detection before performing the reshape. The pivot operation shall use Date as the row index, Item as the source of the new feature columns, Value as the measurement values and the first aggregation method whenever duplicate Date and Item combinations are encountered. The Item Code column shall be used only for validation during preprocessing and shall not become part of the final modelling table unless explicitly required elsewhere in the pipeline.

After reshaping there shall be exactly one observation for every Date. Each indicator represented within the Item column shall become a separate feature column. The resulting columns shall be sorted consistently so that future datasets produce identical schemas regardless of the order of the raw observations.

The preprocessing stage shall validate that the number of unique monthly observations before reshaping equals the number of rows after reshaping. It shall further validate that every indicator has been converted into a feature column and that no measurement values were lost during the pivot operation.

The completed dataset shall contain one observation per unique Date, a datetime Date column, individual CPI indicator columns, zero duplicate monthly observations, zero missing values introduced by preprocessing, chronological ordering and a structure immediately compatible with merge.py.

