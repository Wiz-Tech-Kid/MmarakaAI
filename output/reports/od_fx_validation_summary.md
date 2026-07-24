# od_fx_validation_summary

- final_dataset_shape: (288, 67)
- expected_row_count: 288
- date_range: 2000-01-01 to 2023-12-01
- duplicate_date_count: 0
- original_od_column_count: 47
- number_of_fx_columns_added: 20
- fx_columns_retained: USD_mean, USD_median, USD_std, USD_range, USD_pct_change, ZAR_mean, ZAR_median, ZAR_std, ZAR_range, ZAR_pct_change, EUR_mean, EUR_median, EUR_std, EUR_range, EUR_pct_change, GBP_mean, GBP_median, GBP_std, GBP_range, GBP_pct_change
- fx_columns_excluded: SDR_mean, SDR_median, SDR_std, SDR_range, SDR_pct_change, YEN_mean, YEN_median, YEN_std, YEN_range, YEN_pct_change
- missing_value_counts_for_each_fx_column: {
  "USD_mean": 12,
  "USD_median": 12,
  "USD_std": 12,
  "USD_range": 12,
  "USD_pct_change": 12,
  "ZAR_mean": 12,
  "ZAR_median": 12,
  "ZAR_std": 12,
  "ZAR_range": 12,
  "ZAR_pct_change": 12,
  "EUR_mean": 12,
  "EUR_median": 12,
  "EUR_std": 12,
  "EUR_range": 12,
  "EUR_pct_change": 12,
  "GBP_mean": 12,
  "GBP_median": 12,
  "GBP_std": 12,
  "GBP_range": 12,
  "GBP_pct_change": 12
}
- source_dataset_contribution: data/merged/od_merged.csv + data/processed/bank-of-botswana-exchange-rates_processed.csv
- target_column_verification: food_price_inflation present exactly once = 1
- fx_temporal_audit_earliest_fx_month: 2001-01-01
- fx_temporal_audit_latest_fx_month: 2026-07-01
- fx_temporal_audit_number_of_monthly_observations: 307
- fx_temporal_audit_missing_months: 0
- fx_temporal_audit_duplicate_months: 0
- fx_temporal_audit_usd_availability: yes
- fx_temporal_audit_zar_availability: yes
- fx_temporal_audit_eur_availability: yes
- fx_temporal_audit_gbp_availability: yes