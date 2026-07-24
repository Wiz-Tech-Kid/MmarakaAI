# MmarakaAI

This repository is the MmarakaAI food price forecasting project. It documents the full pipeline from raw data ingestion through preprocessing, controlled dataset construction, feature engineering, benchmark notebooks, and the current Stage C optimization/backtesting workflow.

## Full repository history and current state

### 1. Raw data ingestion

The repo began with raw economic datasets in `data/raw/`.
These raw files were analyzed, audited, and then processed into cleaned monthly inputs in `data/processed/`.

Key raw to processed transformations include:
- `01_baltic_dry_index_daily.csv` → `01_baltic_dry_index_daily_processed.csv`
- `02_brent_crude_monthly.csv` → `02_brent_crude_monthly_processed.csv`
- `03_botswana_policy_rate.csv` → `03_botswana_policy_rate_processed.csv`
- `04_fao_botswana_prices.csv` → `04_fao_botswana_prices_processed.csv`
- `05_human_capital_project.csv` → `05_human_capital_project_processed.csv`
- `bank-of-botswana-exchange-rates.csv` → `bank-of-botswana-exchange-rates_processed.csv`

These processing steps were implemented in `src/preprocessing.py` and `src/external_preprocessing.py` using specification-driven operations, including:
- datetime conversion and normalization
- duplicate row detection and removal
- missing-value handling
- schema validation
- dataset-specific transformations for publications and exchange-rate series

Validation artifacts are stored under `output/preprocessing/` and `output/ext/preprocessing/`, including execution reports and audit plans for each dataset.

### 2. Merging and modeling panel creation

The canonical merged modeling panel is produced by `src/merge.py`.
This script creates `data/merged/merged_modeling_dataset.csv` by joining cleaned monthly inputs on the normalized `Date` field.

The merge pipeline uses:
- `data/processed/04_fao_botswana_prices_processed.csv` as the master dataset
- left joins with monthly economic series from:
  - `02_brent_crude_monthly_processed.csv`
  - `03_botswana_policy_rate_processed.csv`
  - `01_baltic_dry_index_monthly_processed.csv`
  - `bank-of-botswana-exchange-rates_processed.csv`
  - `output/processed/Botswana Consumer Price Index_processed.csv`
- external expanded datasets from `output/ext/processed/` including food price indices, producer price index, livestock/production tables, and imports

The merge script ensures each join is Date-aligned, supports column renaming where needed, and rejects duplicate output columns to preserve a clean modeling panel.

### 3. Original Data control dataset (`od_merged.csv`)

A strict Original Data benchmark dataset was created in `data/merged/od_merged.csv`.
This file preserves only original challenge data and official panel features:
- all BDI-derived monthly statistical predictors
- monthly Brent crude price
- Botswana policy rate
- FAO food and general price indices
- human capital project comparators for selected countries
- the target `food_price_inflation`

The dataset shape is:
- rows: 288
- columns: 47
- date range: 2000-01-01 through 2023-12-01
- duplicate date count: 0

Provenance and validation are documented in `output/reports/original_data_provenance_report.md` and `output/reports/original_data_validation_summary.md`.

### 4. Controlled FX dataset (`od_fx_merged.csv`)

A second controlled dataset was created as `data/merged/od_fx_merged.csv`.
It preserves the full `od_merged.csv` panel and adds only selected FX predictors from `data/processed/bank-of-botswana-exchange-rates_processed.csv`.

Added FX variables are exactly:
- `USD_mean`, `USD_median`, `USD_std`, `USD_range`, `USD_pct_change`
- `ZAR_mean`, `ZAR_median`, `ZAR_std`, `ZAR_range`, `ZAR_pct_change`
- `EUR_mean`, `EUR_median`, `EUR_std`, `EUR_range`, `EUR_pct_change`
- `GBP_mean`, `GBP_median`, `GBP_std`, `GBP_range`, `GBP_pct_change`

Excluded from the FX augmentation are all SDR and YEN features, plus any other external dataset columns.

Validation shows:
- final shape: 288 rows × 67 columns
- duplicate date count: 0
- missing FX values only in the first 12 rows for the FX series due to limited source coverage

This controlled FX dataset is documented in `output/reports/od_fx_provenance_report.md` and `output/reports/od_fx_validation_summary.md`.

### 5. Feature engineering stages

Feature engineering is implemented in `src/features.py` and produces the cleaned feature matrix `data/features/mmarakai_clean_feature_matrix.csv`.
The feature pipeline is intentionally staged and documented:

- Stage 1: lag features (`stage1_lag_features.csv`)
  - generates historical lag columns such as `*_lag1`, `*_lag2`, `*_lag3`, `*_lag6`, `*_lag12`
- Stage 2: percentage-change features (`stage2_percentage_change_features.csv`)
  - computes month-over-month percentage changes from merged predictors
- Stage 3: rolling statistics (`stage3_rolling_statistics.csv`)
  - adds moving averages, volatility, and trend signals over 3-, 6-, and 12-month windows
- Stage 4: calendar and seasonal features (`stage4_seasonal_features.csv`)
  - creates deterministic date-based signals such as month, quarter, and sinusoidal month terms
- Stage 5: trend-difference features (`stage5_trend_features.csv`)
  - constructs first-difference trend predictors from selected economic series
- Stage 6: interaction features (`stage6_interaction_features.csv`)
  - creates a compact set of economically motivated interactions from original predictors

The final feature matrix preserves one copy of the merged modeling dataset and appends only the engineered columns from these stages.

A Stage A feature-cleaning pass is implemented in `src/feature_selection.py`.
This pass removes structural issues from the raw feature matrix and produces `data/features/mmarakai_clean_feature_matrix.csv`.
The output was audited in `data/features/feature_selection_stageA_report.md`.

### 6. Benchmark notebooks and modeling workflow

The repository contains separate notebooks for benchmark and optimization workflows.
This is deliberate: the original data benchmark is isolated from the expanded Stage C optimization pipeline.

#### `notebooks/original_data_forecast.ipynb`
- uses `data/merged/od_merged.csv`
- runs a lightweight benchmark for 2021–2023 origins
- compares simple baseline models using only original challenge data

#### `notebooks/original_data_fx_forecast.ipynb`
- uses `data/merged/od_fx_merged.csv`
- mirrors the original benchmark workflow
- tests the controlled FX-augmented dataset only

#### `notebooks/Model_Optimization.ipynb`
- Stage C optimization and annual backtesting workflow
- uses `data/features/mmarakai_clean_feature_matrix.csv` as the shared feature store
- separates `official_only` from `expanded` feature groups for ablation
- evaluates multiple models, feature selections, and horizons
- generates final production selection based on annual 12-month backtest candidates

### 7. Stage C backtest fix and actual vs predicted output

A critical correction was implemented in `notebooks/Model_Optimization.ipynb`:
- full annual backtesting must use the entire 12-month test window for each origin
- the previous logic permitted shorter-than-12-month horizons to be treated as annual evaluation
- the notebook now enforces `horizon == 12` for annual candidate selection and backtest output

The updated workflow now saves:
- `output/optimization/backtests/historical_actual_vs_predicted_2020_2023.csv`
- `output/optimization/backtests/historical_actual_vs_predicted_2020_2023.png`

The notebook also saves diagnostics and residual analysis under:
- `output/optimization/residual_diagnostics/`
- `output/optimization/tables/`
- `output/optimization/figures/`
- `output/optimization/optuna_studies/`

### 8. Validation and documented fixes

This README no longer hides the operational history.
The repo includes detailed validation and provenance reports for each data artifact,
including source contributions, missing-value audits, duplicate-date checks, and dataset-specific processing rules.

Important documented fixes:
- controlled FX dataset creation restricted to selected USD/ZAR/EUR/GBP variables only
- `od_merged.csv` preserved as the original-data-only control dataset
- Stage C notebook patched to enforce annual 2020–2023 pseudo-future backtests
- diagnostics updated so the final production candidate is selected from full-year annual candidates

## Directory layout

```text
├── data/
│   ├── raw/                     # raw source datasets
│   ├── processed/               # cleaned monthly inputs and processed external datasets
│   └── merged/                  # modeling panels including od_merged.csv and od_fx_merged.csv
├── data/features/               # engineered feature artifacts and clean feature matrix
├── models/                      # trained model artifacts and optimization outputs
├── notebooks/                   # benchmark and optimization notebooks
├── output/                      # reports, preprocessing execution artifacts, backtests, figures, diagnostics
├── src/                         # pipeline code for preprocessing, merging, feature engineering, evaluation, and prediction
├── tests/                       # unit tests for preprocessing, features, and dataset construction
├── requirements.txt             # Python dependency list
└── README.md                    # this document
```

## How to run

From the repository root:

```bash
python -m compileall src
python -m pip install -r requirements.txt
```

To inspect benchmarks:

```bash
jupyter notebook notebooks/original_data_forecast.ipynb
jupyter notebook notebooks/original_data_fx_forecast.ipynb
jupyter notebook notebooks/Model_Optimization.ipynb
```

## What each notebook does

- `notebooks/original_data_forecast.ipynb`
  - evaluates the pure original data benchmark using `od_merged.csv`
- `notebooks/original_data_fx_forecast.ipynb`
  - evaluates the controlled FX-augmented benchmark using `od_fx_merged.csv`
- `notebooks/Model_Optimization.ipynb`
  - performs Stage C optimization, selects a final candidate from annual 12-month backtests, and produces a 2020–2023 actual vs predicted backtest table and chart
- `notebooks/classic_ml.ipynb`
  - classic Stage B baseline experiments using the cleaned feature matrix
- `notebooks/feature_selection.ipynb` and `notebooks/features.ipynb`
  - investigate the feature engineering pipeline and validate derived predictors

## Notes on data provenance

- `od_merged.csv` is the strict original-data control dataset. It does not contain added foreign exchange, external CPI, imports, or livestock features.
- `od_fx_merged.csv` is a controlled ablation dataset that extends `od_merged.csv` only with selected FX predictors from `bank-of-botswana-exchange-rates_processed.csv`.
- The FX augmentation deliberately excludes SDR and YEN features and does not introduce any additional external datasets.

## Validation artifacts

Check these files for a full audit trail:
- `output/reports/original_data_provenance_report.md`
- `output/reports/original_data_validation_summary.md`
- `output/reports/od_fx_provenance_report.md`
- `output/reports/od_fx_validation_summary.md`
- `output/reports/model_optimization_report.md`
- `output/preprocessing/execution/markdown/`
- `output/ext/preprocessing/execution/markdown/`

## Current status summary

- Original data benchmark: available and reproducible from `od_merged.csv`
- Controlled FX benchmark: available from `od_fx_merged.csv`
- Stage C annual 2020–2023 backtesting: patched and functional in `notebooks/Model_Optimization.ipynb`
- Diagnostics and selection artifacts: stored under `output/optimization/`
- Validation and provenance: tracked through `output/reports/`

If you want, I can also add a provenance section that lists every data source and processing file in exact execution order.
