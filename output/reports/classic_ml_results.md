# MmarakaAI Stage B Classical ML Results

## What the notebook did

The notebook used the cleaned feature matrix, sorted observations by date, and reserved the most recent 20% for a held-out test. The earlier 80% was used for feature ranking and time-aware cross-validation.

- Total observations: 288
- Training observations: 230
- Held-out test observations: 58
- Training period: 2000-01-01 to 2019-02-01
- Test period: 2019-03-01 to 2023-12-01
- Target: `food_price_inflation`
- Candidate models: Random Forest and LightGBM

## Main result

- Best model: **LightGBMRegressor**
- Best feature subset: **top 100 features**
- Cross-validation RMSE: **3.3555**
- Cross-validation MAE: **2.7377**
- Held-out test RMSE: **4.2954**
- Held-out test MAE: **2.8506**
- Held-out test R-squared: **0.2720**

## What those numbers mean

### RMSE: 4.2954

RMSE is an error score. It measures how far predictions are from the actual food-price-inflation values, while penalizing large errors more heavily. Lower is better. The model's typical error is roughly 4.30 target units under this measure.

### MAE: 2.8506

MAE is the average absolute prediction error. It is easier to interpret because every error contributes linearly. The predictions were off by about 2.85 target units on average in the held-out test period.

### R-squared: 0.2720

R-squared compares the model with a simple baseline that always predicts the average value. A value of 1 is perfect, 0 means no improvement over that baseline, and a negative value is worse than that baseline. A value of 0.272 means the model explains about 27.2% of the variation in the held-out period. That is useful signal, but it is still a modest forecasting result rather than a highly accurate model.

## Generalization

The test RMSE of 4.2954 is higher than the cross-validation RMSE of 3.3555. That means the latest test period was harder for the model than the earlier validation periods. This difference is worth monitoring and may indicate changing economic conditions or some overfitting to earlier periods.

## Feature importance

The feature-importance table ranks variables used by the Random Forest feature-ranking step. A high ranking means the model found that feature useful for reducing prediction error. It does **not** prove that the feature causes inflation, and it is not a percentage contribution to inflation.

The highest-ranked features in the completed run included:

1. `food_index_std12`
2. `BDI_High_median_std12`
3. `BDI_Close_variance_std12`
4. `BDI_High_std_std12`
5. `BDI_Low_median_std12`
6. `BDI_High_variance_std12`
7. `PI201135_std12`
8. `BDI_Low_variance_std12`
9. `BDI_Close_last_std12`
10. `BDI_Low_std_std12`

Names ending in `std12`, `roll12`, or similar are engineered features based on a 12-month rolling window. They describe historical variability or trend rather than a single monthly observation.

## Files produced by the notebook

- Model artifact: `models/stageB_best_classic_ml_model.joblib`
- Feature ranking: `output/feature_importance.csv`
- Model comparison: `output/model_comparison.csv`
- Selected features: `output/selected_features.csv`
- Figures: `output/analysis/figures/ml/`
- Generated report in Colab: `/content/MmarakaAI/output/reports/classic_ml_results.md`

## Bottom line

The experiment produced a working baseline. LightGBM using the top 100 ranked features performed best among the tested combinations. However, the held-out R-squared of 0.2720 shows that much of the variation remains unexplained. The model is suitable for comparison and further development, but it should not yet be treated as a dependable production forecasting system.
