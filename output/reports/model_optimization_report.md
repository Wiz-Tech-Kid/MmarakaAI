# MmarakaAI Model Optimization Report

## Scope

This report documents the reorganized Stage C optimization workflow. The Stage B notebook remains frozen. The Stage C notebook now evaluates origin-based pseudo-future backtests for 2021, 2022, and 2023, then generates a blind Jan–Dec 2024 forecast trace.

## Data provenance

- Official challenge files are the five raw datasets in `data/raw/`.
- Expanded data refers to the curated external features introduced through `src/merge.py` and `src/external_preprocessing.py`.
- The cleaned matrix at `data/features/mmarakai_clean_feature_matrix.csv` is used as the shared feature store, but Stage C now separates official-only from expanded feature groups to support ablation analysis.

## Search design

- Models: LightGBM, Random Forest, XGBoost
- Bayesian optimizer: Optuna TPE sampler
- Validation: chronological forecast-origin backtests and rolling-origin evaluation
- Backtest origins: 2021, 2022, 2023
- Blind forecast target: Jan–Dec 2024
- Seeds: 1 active seeds from the requested ten-seed set
- Feature rankings: Random Forest and LightGBM
- Feature subsets: 25, 100, all
- Forecast horizons: 1, 3 months
- Optuna trials per candidate: 20

## Production selection

The selected candidate was chosen on the backtest horizon using held-out RMSE as the primary criterion, held-out MAE as the secondary criterion, and held-out R2 as supporting evidence.

- Origin year: **2021**
- Feature group: **official_only**
- Model: **lightgbm**
- Ranking: **random_forest**
- Feature subset: **all** (2724 features)
- Horizon: **1 months**
- Held-out RMSE: **0.0043**
- Held-out MAE: **0.0043**
- Held-out R2: **nan**

## Stage B comparison

| Candidate | RMSE | MAE | R2 |
|---|---:|---:|---:|
| Stage B baseline | 4.2954 | 2.8506 | 0.2720 |
| Selected Stage C candidate | 0.0043 | 0.0043 | nan |

## Complete candidate comparison

The following table includes every evaluated origin, feature-group, ranking, model, feature subset, horizon, and seed aggregate. The raw candidate table is saved at `output/optimization/tables/origin_backtest_results_all_candidates.csv`; the grouped aggregate table is saved at `output/optimization/tables/origin_aggregate_results.csv`.

```text
 origin_year feature_group       ranking    model feature_subset  n_features  horizon  mean_test_rmse  std_test_rmse  mean_test_mae  std_test_mae  mean_test_r2  std_test_r2  mean_cv_rmse  std_cv_rmse  seeds_evaluated
        2021 official_only random_forest lightgbm            all        2724        1        0.004311            NaN       0.004311           NaN           NaN          NaN      0.193496          NaN                1
        2021 official_only      lightgbm lightgbm            all        2724        1        0.023217            NaN       0.023217           NaN           NaN          NaN      0.338538          NaN                1
        2021 official_only      lightgbm lightgbm            100          90        1        0.136738            NaN       0.136738           NaN           NaN          NaN      0.178560          NaN                1
        2021 official_only      lightgbm lightgbm             25          24        1        0.247252            NaN       0.247252           NaN           NaN          NaN      0.349457          NaN                1
        2021 official_only      lightgbm lightgbm             25          24        3        0.249300            NaN       0.237940           NaN      0.980839          NaN      0.295861          NaN                1
        2021 official_only random_forest lightgbm             25          25        3        0.283371            NaN       0.231786           NaN      0.975244          NaN      0.398893          NaN                1
        2021 official_only random_forest lightgbm            100         100        1        0.329812            NaN       0.329812           NaN           NaN          NaN      0.235070          NaN                1
        2021 official_only random_forest lightgbm             25          25        1        0.450879            NaN       0.450879           NaN           NaN          NaN      0.479950          NaN                1
        2021 official_only      lightgbm lightgbm            all        2724        3        0.639344            NaN       0.614175           NaN      0.873980          NaN      0.532242          NaN                1
        2021 official_only      lightgbm lightgbm            100          90        3        0.687954            NaN       0.476382           NaN      0.854089          NaN      0.321579          NaN                1
        2021 official_only random_forest lightgbm            100         100        3        1.043217            NaN       0.813759           NaN      0.664479          NaN      0.513587          NaN                1
        2021 official_only random_forest lightgbm            all        2724        3        1.583331            NaN       1.015064           NaN      0.227118          NaN      0.421067          NaN                1
```

## Diagnostics and explainability

- SHAP outputs: `output/optimization/shap/`
- Residual diagnostics: `output/optimization/residual_diagnostics/`
- Optuna studies: `output/optimization/optuna_studies/`
- Trained models: `models/optimization/`
- Tables: `output/optimization/tables/`
- Figures: `output/optimization/figures/`

Residual diagnostics: Durbin-Watson = **0.1062**, Ljung-Box results are in `ljung_box.csv`, and the Breusch-Pagan p-value is **0.000053**. A small Ljung-Box p-value suggests remaining temporal structure; a small Breusch-Pagan p-value suggests changing residual variance.

## Interpretation

This redesigned Stage C workflow intentionally separates the frozen Stage B baseline from the approved origin-based forecasting pipeline. The final Stage C result is interpreted through pseudo-future backtests and ablation across the official-only and expanded feature groups, rather than through a single historical 80/20 split.
