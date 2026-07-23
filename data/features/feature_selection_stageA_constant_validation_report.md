# Stage A Constant Feature Validation: PI101164 and PI101444

## Objective

Validate whether `PI101164` and `PI101444` were true constants in the original source data or became constant because of preprocessing, pivoting, merging, date alignment, feature engineering, or Stage A cleaning.

## Source Trace

| Variable | Raw source row | Raw non-null period | Raw non-null count | Raw unique non-null values | Conclusion |
| --- | --- | --- | ---: | --- | --- |
| `PI101164` | Agriculture - Food: Sugar cane | 2000-01 to 2007-12 | 96 | `[0.0]` | Constant in raw source |
| `PI101444` | Other raw animal products | 2008-01 to 2012-12 | 60 | `[175.0]` | Constant in raw source |

The raw workbook contains one row for each code. No duplicate source rows were found for either `PI101164` or `PI101444`.

## Pipeline Evidence

| Stage | `PI101164` evidence | `PI101444` evidence |
| --- | --- | --- |
| Raw Excel | 96 non-null values, all `0.0` | 60 non-null values, all `175.0` |
| Rebuilt preprocessing output | Matches saved processed file exactly | Matches saved processed file exactly |
| `Producer Price Index 2000_processed.csv` | 156 rows, 96 non-null, 1 unique value: `0.0` | 156 rows, 60 non-null, 1 unique value: `175.0` |
| `merged_modeling_dataset.csv` | 288 rows, 96 non-null, 1 unique value: `0.0` | 288 rows, 60 non-null, 1 unique value: `175.0` |
| Stage 1 lags | Lag features remain constant where non-missing | Lag features remain constant where non-missing |
| Stage 2 pct change | `PI101164_pct_change` is 100% missing because `(0 - 0) / 0` is undefined | `PI101444_pct_change` is constant `0.0` where non-missing |
| Stage 3 rolling stats | Rolling means and standard deviations are constant where non-missing | Rolling means are `175.0`; rolling standard deviations are `0.0` |
| Stage 5 trend | Constant `0.0` where non-missing | Constant `0.0` where non-missing |
| Stage 6 interactions | `PI101164*x*general_index` is constant `0.0` and duplicate-like | `PI101444*x*general_index` is non-constant because `general_index` changes |
| Stage A cleaned matrix | All `PI101164` family columns removed | Base and constant derived columns removed; `PI101444*x*general_index` retained |

## Decision

`PI101164` and `PI101444` are true constants in the original raw source data. They did not become constant because of preprocessing, pivoting, merging, date alignment, or feature engineering.

Stage A removal was correct and requires no pipeline fix. The current `mmarakai_clean_feature_matrix.csv` is approved for Stage B feature selection.
