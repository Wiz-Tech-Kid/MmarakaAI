# Execution Report

- Dataset: 04_fao_botswana_prices
- Execution status: SUCCESS
- Execution time: 0.017s

## Executive Summary

- Dataset: 04_fao_botswana_prices
- Rows Before: 852
- Rows After: 288
- Columns Before: 4
- Columns After: 4
- Status: SUCCESS

## Transformation Summary

| Transformation ID | Action | Status | Execution Time | Validation |
| --- | --- | --- | --- | --- |
| P001 | Convert the Date column to datetime using the parameters supplied in the JSON contract. | SUCCESS | 0.001798s | PASS |
| P002 | Reshape long-format rows into wide format using the JSON-defined pivot parameters. | SUCCESS | 0.007341s | PASS |
| P003 | Validate that the expected reshaped columns are present. | SUCCESS | 0.000135s | PASS |
| P004 | Validate that the reshaped dataset contains one row per unique Date. | SUCCESS | 0.000087s | PASS |
| P005 | Validate that Date remains available for downstream joins. | SUCCESS | 0.000089s | PASS |
| P006 | Validate that Date remains datetime-typed after reshaping. | SUCCESS | 0.000188s | PASS |

## Parameters Used

- P001: {"columns": ["Date"], "errors": "coerce", "format": "auto", "utc": false}
- P002: {"aggfunc": "first", "columns": ["Item"], "flatten_columns": true, "index": ["Date"], "remove_column_index_name": true, "sort_columns": true, "values": ["Value"]}
- P003: {}
- P004: {}
- P005: {}
- P006: {}

## Validation Summary

| Transformation | Expected | Actual | Status |
| --- | --- | --- | --- |
| Convert the Date column to datetime using the parameters supplied in the JSON contract. | ['Date'] | ['Date'] | PASS |
| Reshape long-format rows into wide format using the JSON-defined pivot parameters. | 288 | 288 | PASS |
| Validate that the expected reshaped columns are present. | ['Date', 'Consumer Prices, Food Indices (2015 = 100)', 'Consumer Prices, General Indices (2015 = 100)', 'Food price inflation'] | ['Consumer Prices, Food Indices (2015 = 100)', 'Consumer Prices, General Indices (2015 = 100)', 'Date', 'Food price inflation'] | PASS |
| Validate that the reshaped dataset contains one row per unique Date. | 288 | 288 | PASS |
| Validate that Date remains available for downstream joins. | ['Date'] | ['Consumer Prices, Food Indices (2015 = 100)', 'Consumer Prices, General Indices (2015 = 100)', 'Date', 'Food price inflation'] | PASS |
| Validate that Date remains datetime-typed after reshaping. | ['Date'] | ['Date'] | PASS |

## Skipped Transformations

- None

## Dataset Summary

- Rows Before: 852
- Rows After: 288
- Columns Before: 4
- Columns After: 4
- Duplicate Rows Removed: 0
- Datetime Converted: No
- Missing Values Remaining: 12
- Join Keys Preserved: Yes

## Output

- Processed filename: 04_fao_botswana_prices_processed.csv
- Output directory: /home/nickel/Documents/New Folder/MmarakaAI/data/processed
- Ready for merge.py: Yes

## Notes

- No additional notes.
