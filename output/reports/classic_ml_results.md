# MmarakaAI Stage B Classical ML Results

## What this experiment did

The notebook used the cleaned feature matrix, sorted the observations by date, and kept the most recent 20% as a held-out test period. The earlier 80% was used for model training, feature ranking, and time-aware cross-validation.

- Dataset rows: 288
- Training rows: 230
- Held-out test rows: 58
- Training period: 2000-01-01 to 2019-02-01
- Test period: 2019-03-01 to 2023-12-01
- Target: `food_price_inflation`
- Candidate models: Random Forest and LightGBM
- Feature subsets tested: 25, 50, 100, 200, 500 top-ranked features

## Main result

- Best model: **LightGBMRegressor**
- Selected feature subset: **top_100**
- Selected feature count: **100**
- Cross-validation RMSE: **3.3555**
- Cross-validation MAE: **2.7377**
- Held-out test RMSE: **4.2954**
- Held-out test MAE: **2.8506**
- Held-out test R-squared: **0.2720**

## Plain-language interpretation

### RMSE
RMSE is the typical prediction error, with larger errors receiving extra penalty. Lower is better. The held-out RMSE of **4.2954** means the model's prediction errors are approximately this size on the scale of the target, with larger misses affecting the score more strongly.

### MAE
MAE is the average absolute prediction error. Lower is better, and it is easier to interpret than RMSE because it is not as strongly affected by unusually large errors. The held-out MAE is **2.8506**.

### R-squared
R-squared compares the model with a baseline that always predicts the training-period average. A value of 1 is perfect, 0 means no improvement over that constant baseline, and a negative value means the model is worse than that baseline. The test R-squared is **0.2720**. The model explains only a limited share of the variation and should be treated as a baseline.

## Generalization check

The held-out error is noticeably higher than cross-validation error, suggesting possible overfitting or a harder test period.

Cross-validation estimates performance on several earlier validation windows. The held-out test result is the more important final check because it uses the latest observations and was not used to choose the model.

## Top features by Random Forest importance

Feature importance measures how much the fitted Random Forest used each feature to reduce prediction error. It indicates usefulness within this model; it does not prove that a feature causes inflation, and it should not be read as a percentage of inflation caused by that feature.

1. food_index_std12: 0.015292
2. BDI_High_median_std12: 0.015203
3. BDI_Close_variance_std12: 0.014689
4. BDI_High_std_std12: 0.013786
5. BDI_Low_median_std12: 0.012255
6. BDI_High_variance_std12: 0.012148
7. PI201135_std12: 0.011822
8. BDI_Low_variance_std12: 0.011508
9. BDI_Close_last_std12: 0.011252
10. BDI_Low_std_std12: 0.011213

## Model comparison

The table below shows the ten highest-ranked model/subset combinations. Lower RMSE and MAE are better; higher R-squared is better.

```text
 rank                 model feature_subset  n_features   rmse    mae      r2
    1     LightGBMRegressor        top_100         100 3.3555 2.7377 -0.2316
    2     LightGBMRegressor        top_200         200 3.5424 2.9651 -0.5352
    3     LightGBMRegressor         top_50          50 3.5546 2.8850 -0.4628
    4     LightGBMRegressor         top_25          25 3.7525 3.0667 -0.8263
    5 RandomForestRegressor         top_25          25 4.1728 3.5333 -1.3400
    6 RandomForestRegressor        top_100         100 4.2075 3.4110 -1.1293
    7 RandomForestRegressor         top_50          50 4.3172 3.5655 -1.4403
    8 RandomForestRegressor        top_200         200 4.5793 3.8868 -1.7963
    9     LightGBMRegressor        top_500         500 4.8288 4.2637 -3.9783
   10 RandomForestRegressor        top_500         500 5.0292 4.4547 -3.5338
```

## Files produced

- Model artifact: `/content/MmarakaAI/models/stageB_best_classic_ml_model.joblib`
- Feature ranking: `/content/MmarakaAI/output/feature_importance.csv`
- Model comparison: `/content/MmarakaAI/output/model_comparison.csv`
- Selected features: `/content/MmarakaAI/output/selected_features.csv`
- Figures directory: `/content/MmarakaAI/output/analysis/figures/ml`

## Important limitation

This is a baseline forecasting experiment, not proof that the model will perform equally well in the future. The dataset contains engineered lag, rolling, and summary features, so performance should be checked for leakage and stability before using the model operationally.
