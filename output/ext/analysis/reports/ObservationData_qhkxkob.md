# Executive Summary

| Measure | Value |
| --- | --- |
| Dataset Name | ObservationData_qhkxkob.csv |
| Rows | 165 |
| Columns | 8 |
| Date Range | Not detected |
| Detected Frequency | Not detected |
| Missing Values | 0 |
| Duplicate Rows | 0 |
| Duplicate Dates | 0 |
| Outliers Detected | 0 |
| Numeric Columns | 2 |
| Categorical Columns | 6 |
| Memory Usage | 57.72 KB |

## Dataset Overview

| Measure | Value |
| --- | --- |
| Rows | 165 |
| Columns | 8 |
| Memory Usage | 57.72 KB |
| Shape | 165 rows x 8 columns |
| Column Count | 8 |
| Numeric Columns | Date, Value |
| Numeric Column Count | 2 |
| Categorical Columns | district, indicator, sex, age-group, marital-status, Unit |
| Categorical Column Count | 6 |
| Datetime Columns | None |
| Datetime Column Count | 0 |

## Column Profile

| Column | Data Type | Memory Usage | Missing Count | Missing % | Unique Values | Example Value |
| --- | --- | --- | --- | --- | --- | --- |
| district | str | 9.18 KB | 0 | 0 | 1 | Botswana |
| indicator | str | 8.77 KB | 0 | 0 | 5 | Cattle |
| sex | str | 9.83 KB | 0 | 0 | 1 | Total number |
| age-group | str | 9.67 KB | 0 | 0 | 1 | totalnumber |
| marital-status | str | 8.70 KB | 0 | 0 | 1 | Total |
| Unit | str | 8.86 KB | 0 | 0 | 1 | Number |
| Date | int64 | 1.29 KB | 0 | 0 | 33 | 1979 |
| Value | int64 | 1.29 KB | 0 | 0 | 143 | 2840 |

## Preview

### First 5 Rows

| district | indicator | sex | age-group | marital-status | Unit | Date | Value |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Botswana | Cattle | Total number | totalnumber | Total | Number | 1979 | 2840 |
| Botswana | Cattle | Total number | totalnumber | Total | Number | 1980 | 2911 |
| Botswana | Cattle | Total number | totalnumber | Total | Number | 1981 | 2967 |
| Botswana | Cattle | Total number | totalnumber | Total | Number | 1982 | 2979 |
| Botswana | Cattle | Total number | totalnumber | Total | Number | 1983 | 2818 |

### Last 5 Rows

| district | indicator | sex | age-group | marital-status | Unit | Date | Value |
| --- | --- | --- | --- | --- | --- | --- | --- |
| Botswana | Pigs | Total number | totalnumber | Total | Number | 2011 | 5 |
| Botswana | Pigs | Total number | totalnumber | Total | Number | 2012 | 24 |
| Botswana | Pigs | Total number | totalnumber | Total | Number | 2013 | 3 |
| Botswana | Pigs | Total number | totalnumber | Total | Number | 2014 | 11 |
| Botswana | Pigs | Total number | totalnumber | Total | Number | 2015 | 4 |

## Data Quality

| Measure | Value |
| --- | --- |
| Missing values | 0 |
| Missing % | 0 |
| Duplicate rows | 0 |
| Duplicate dates | 0 |
| Infinite values | 0 |
| Zero values | 0 |
| Negative values | 0 |
| Constant columns | district, sex, age-group, marital-status, Unit |
| Near-constant columns | None |
| Potential identifier columns | None |
| Mixed data type columns | None |
| Object columns containing dates | None |

### Numeric Sign Counts

| Column | Zero Values | Negative Values | Positive Values |
| --- | --- | --- | --- |
| Date | 0 | 0 | 165 |
| Value | 0 | 0 | 165 |

## Missing Value Analysis

### Missing Count Per Column

| Column | Missing Count | Missing % |
| --- | --- | --- |
| district | 0 | 0 |
| indicator | 0 | 0 |
| sex | 0 | 0 |
| age-group | 0 | 0 |
| marital-status | 0 | 0 |
| Unit | 0 | 0 |
| Date | 0 | 0 |
| Value | 0 | 0 |

Rows containing missing values: 0 (0.0%)

### Rows Containing Missing Values (First 10)

No records.

Grouped missing-value tables generated: 0

## Duplicate Analysis

Duplicate count: 0

### Preview Duplicate Records

No records.

### Repeated Date Values

No datetime columns detected.

## Numeric Statistics

| Column | Count | Mean | Median | Mode | Minimum | Maximum | Range | Variance | Standard Deviation | Coefficient of Variation | IQR | Skewness | Kurtosis | Zero Count | Negative Count | Positive Count | Outlier Count Using IQR |
| --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- | --- |
| Date | 165 | 1997.18 | 1998 | 1979 | 1979 | 2015 | 36 | 124.479 | 11.157 | 0.00558638 | 20 | -0.0526931 | -1.30149 | 0 | 0 | 165 | 0 |
| Value | 165 | 1090.94 | 961 | 5 | 1 | 3157 | 3156 | 900971 | 949.195 | 0.870071 | 1652 | 0.397875 | -1.1793 | 0 | 0 | 165 | 0 |

## Categorical Statistics

### district

Unique values: 1

| Top 10 Values | Frequency | Frequency % |
| --- | --- | --- |
| Botswana | 165 | 100 |

### indicator

Unique values: 5

| Top 10 Values | Frequency | Frequency % |
| --- | --- | --- |
| Cattle | 33 | 20 |
| Goats | 33 | 20 |
| Sheep | 33 | 20 |
| Chicken | 33 | 20 |
| Pigs | 33 | 20 |

### sex

Unique values: 1

| Top 10 Values | Frequency | Frequency % |
| --- | --- | --- |
| Total number | 165 | 100 |

### age-group

Unique values: 1

| Top 10 Values | Frequency | Frequency % |
| --- | --- | --- |
| totalnumber | 165 | 100 |

### marital-status

Unique values: 1

| Top 10 Values | Frequency | Frequency % |
| --- | --- | --- |
| Total | 165 | 100 |

### Unit

Unique values: 1

| Top 10 Values | Frequency | Frequency % |
| --- | --- | --- |
| Number | 165 | 100 |

## Datetime Analysis

Datetime columns detected: 0

## Join Key Analysis

No candidate join keys detected.

## Correlation Analysis

| Column | Date | Value |
| --- | --- | --- |
| Date | 1 | 0.0132352 |
| Value | 0.0132352 | 1 |

| Measure | Columns | Correlation |
| --- | --- | --- |
| Highest correlation pair | Date \| Value | 0.0132352 |
| Lowest correlation pair | Date \| Value | 0.0132352 |

## Distribution Analysis

![Histograms](../figures/ObservationData_qhkxkob_histogram.png)

![Boxplots](../figures/ObservationData_qhkxkob_boxplot.png)

## Time-Series Diagnostics

Datetime columns detected: 0

- Time Series: Not generated

## Dataset-Specific Checks

Dataset-specific rule: No filename-specific rule matched

| Measure | Value |
| --- | --- |
| Dataset-specific checks generated | 0 |

## Pipeline Impact

| Measured Observation | Measured Value |
| --- | --- |
| Constant columns present | district, sex, age-group, marital-status, Unit |
| Numeric measure-like column names present | Value |
| Dataset-specific rule applied | No filename-specific rule matched |

## Figures

| Figure | Saved File |
| --- | --- |
| Missing-value plot | ObservationData_qhkxkob_missing.png |
| Correlation heatmap | ObservationData_qhkxkob_correlation.png |
| Histograms | ObservationData_qhkxkob_histogram.png |
| Boxplots | ObservationData_qhkxkob_boxplot.png |
| Time-series plot | Not generated |

![Missing Values](../figures/ObservationData_qhkxkob_missing.png)

![Correlation Heatmap](../figures/ObservationData_qhkxkob_correlation.png)
