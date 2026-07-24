# MmarakaAI Stage C Hyperparameter Optimization Report

## Objective

Stage C extended the Stage B classical ML notebook without changing preprocessing, feature engineering, chronological train/test splitting, or the original Random Forest feature-selection baseline. The fixed Stage B reference is LightGBMRegressor using the top 100 Random-Forest-ranked features.

## Feature-selection comparison

Stage C added LightGBM feature importance as a second ranking method and compared Random Forest and LightGBM rankings across these top-N subset sizes: [25, 50, 100, 200, 500].

The best feature set chosen for LightGBM was `RandomForestImportance_top_100` using `RandomForestImportance`.

The best feature set chosen for Random Forest was `LightGBMImportance_top_25` using `LightGBMImportance`.

Top feature-selection runs:

```text
 stagec_feature_selection_rank                 model                 feature_subset  n_features    mae  mae_std   rmse  rmse_std      r2  r2_std  training_time_seconds         ranking_method  requested_top_n
                             1     LightGBMRegressor RandomForestImportance_top_100         100 2.7377   1.3900 3.3555    1.8544 -0.2316  0.4292                 0.5579 RandomForestImportance              100
                             2     LightGBMRegressor RandomForestImportance_top_200         200 2.9651   1.6739 3.5424    2.0977 -0.5352  1.1073                 1.7451 RandomForestImportance              200
                             3     LightGBMRegressor  RandomForestImportance_top_50          50 2.8850   1.2322 3.5546    1.7147 -0.4628  0.5056                 0.3494 RandomForestImportance               50
                             4     LightGBMRegressor      LightGBMImportance_top_25          25 2.8414   1.3979 3.5610    1.8667 -0.6356  1.2628                 0.2724     LightGBMImportance               25
                             5     LightGBMRegressor     LightGBMImportance_top_100         100 3.0060   1.5395 3.7172    1.9080 -0.8236  1.4738                 0.6458     LightGBMImportance              100
                             6     LightGBMRegressor      LightGBMImportance_top_50          50 2.9926   1.3809 3.7395    1.8408 -0.6959  0.9566                 0.4159     LightGBMImportance               50
                             7     LightGBMRegressor  RandomForestImportance_top_25          25 3.0667   1.2367 3.7525    1.6932 -0.8263  1.2259                 0.2857 RandomForestImportance               25
                             8 RandomForestRegressor      LightGBMImportance_top_25          25 3.2727   1.2473 3.9577    1.6436 -1.0372  0.9072                 2.6424     LightGBMImportance               25
                             9     LightGBMRegressor     LightGBMImportance_top_200         200 3.3876   1.9889 4.1122    2.2090 -1.7210  3.1809                 1.1206     LightGBMImportance              200
                            10 RandomForestRegressor  RandomForestImportance_top_25          25 3.5333   1.5268 4.1728    1.9194 -1.3400  1.2807                 3.5982 RandomForestImportance               25
```

## Hyperparameter optimization result

Best tuned model: **RandomForestRegressor**

Best search stage: **focused_grid_search**

Selected feature ranking: **LightGBMImportance**

Selected feature subset: **LightGBMImportance_top_25**

Best hyperparameters:

```json
{
  "bootstrap": false,
  "max_depth": 6,
  "max_features": 1.0,
  "min_samples_leaf": 2,
  "min_samples_split": 15,
  "n_estimators": 200
}
```

## Baseline versus tuned model

```text
 stagec_rank                    version                 model        search_stage         ranking_method                 feature_subset  n_features  cv_rmse  cv_rmse_std  cv_mae  cv_mae_std   cv_r2  cv_r2_std  train_rmse  test_rmse  test_mae  test_r2  training_time_seconds
           1 StageC_focused_grid_search RandomForestRegressor focused_grid_search     LightGBMImportance      LightGBMImportance_top_25          25   3.1327       1.0847  2.4996      0.8381 -0.3311     0.8026      0.8947     4.4356    3.2511   0.2237                44.2380
           2   StageC_randomized_search RandomForestRegressor   randomized_search     LightGBMImportance      LightGBMImportance_top_25          25   3.2868       1.2045  2.7346      0.9932 -0.5185     1.1217      0.7400     3.3535    2.4023   0.5563                99.5977
           3   StageC_randomized_search     LightGBMRegressor   randomized_search RandomForestImportance RandomForestImportance_top_100         100   3.2911       1.8794  2.6781      1.4165 -0.1758     0.4602      0.7288     4.1334    2.7066   0.3259                67.4358
           4 StageC_focused_grid_search     LightGBMRegressor focused_grid_search RandomForestImportance RandomForestImportance_top_100         100   3.2911       1.8794  2.6781      1.4165 -0.1758     0.4602      0.7288     4.1334    2.7066   0.3259                32.6768
           5           StageB_reference     LightGBMRegressor  baseline_reference RandomForestImportance                        top_100         100   3.3555       1.8544  2.7377      1.3900 -0.2316     0.4292         NaN     4.2954    2.8506   0.2720                 0.2773
```

Held-out test improvements relative to Stage B reference:

- RMSE delta: -0.1402 (-3.26%)
- MAE delta: -0.4005 (-14.05%)
- R-squared delta: -0.0483

Positive RMSE and MAE deltas mean the tuned model reduced error. Positive R-squared delta means the tuned model explained more held-out variation.

## Hyperparameters with the greatest observed effect

The table below ranks hyperparameters by the range in mean cross-validated RMSE observed during the broad randomized search. A larger range means the model was more sensitive to that hyperparameter in this experiment.

```text
                model    hyperparameter  rmse_effect_range best_value_by_mean_rmse  best_mean_cv_rmse  worst_mean_cv_rmse  values_tested
    LightGBMRegressor         reg_alpha             1.4813                  1.0000             3.5349              5.0162              6
    LightGBMRegressor min_child_samples             1.3656                  5.0000             3.4402              4.8058              5
    LightGBMRegressor  colsample_bytree             0.8750                  0.9500             3.4885              4.3634              5
    LightGBMRegressor     learning_rate             0.8545                  0.0800             3.4364              4.2909              6
RandomForestRegressor      max_features             0.8039                  1.0000             3.3477              4.1517              6
    LightGBMRegressor      n_estimators             0.7650                    1200             3.6240              4.3890              6
    LightGBMRegressor        num_leaves             0.7187                 31.0000             3.6236              4.3423              6
    LightGBMRegressor         subsample             0.6488                  0.7500             3.6086              4.2575              5
    LightGBMRegressor        reg_lambda             0.5581                  0.0100             3.6535              4.2116              6
RandomForestRegressor  min_samples_leaf             0.5361                  2.0000             3.5604              4.0966              5
```

## Overfitting check

Stage B CV-to-test RMSE gap: 0.9399

Stage C CV-to-test RMSE gap: 1.3028

The tuned model did not reduce the CV-to-test RMSE gap; the latest period remains harder than the validation windows.

## Residual behavior

Stage B lag-1 residual autocorrelation: 0.8982

Stage C lag-1 residual autocorrelation: 0.7686

Stage B residual-time correlation: 0.4110

Stage C residual-time correlation: -0.3548

The tuned model has lower absolute lag-1 residual autocorrelation, so its residuals are more random over time by this diagnostic.

## Statistical and practical comparison

Paired bootstrap improvements on the held-out test period:

```text
metric  mean_delta_improvement  ci95_lower  ci95_upper  probability_stageC_better
  rmse                 -0.1424     -1.5191      1.2396                     0.4320
   mae                 -0.4304     -1.5683      0.7592                     0.2485
    r2                 -0.0767     -0.7423      0.3444                     0.4155
```

The paired bootstrap interval for RMSE improvement crosses zero, so the Stage C RMSE gain is not statistically conclusive on the held-out period.

The RMSE and MAE improvements are below 5%, so any practical improvement should be treated as modest.

## Outputs

- Best tuned model: `/content/MmarakaAI/models/stageC_best_model.joblib`
- Best hyperparameters: `/content/MmarakaAI/output/best_hyperparameters.json`
- Feature rankings: `/content/MmarakaAI/output/stageC_feature_rankings.csv`
- Feature-selection comparison: `/content/MmarakaAI/output/stageC_feature_selection_comparison.csv`
- Hyperparameter search results: `/content/MmarakaAI/output/stageC_hyperparameter_search_results.csv`
- Tuned model comparison: `/content/MmarakaAI/output/stageC_model_comparison.csv`
- Test predictions: `/content/MmarakaAI/output/stageC_test_predictions.csv`
- Figures: `/content/MmarakaAI/output/analysis/figures/ml`

## Conclusion

Stage C should be accepted over Stage B only if it improves cross-validation metrics and the held-out test period without increasing residual structure or overfitting. The ranked comparison table and bootstrap intervals above provide the evidence for that decision.
