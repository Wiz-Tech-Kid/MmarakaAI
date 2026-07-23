# Preprocessing Plan (P1)

Dataset Name: ObservationData_bkgkbwg

Pipeline Position:
Raw Dataset
→ Structural Transformation
→ Data Cleaning
→ Datetime Normalization
→ Domain Filtering
→ Merge Pipeline
→ Feature Engineering
→ Machine Learning Models

Purpose of this document:

This document defines the engineering specification for preprocessing the ObservationData_bkgkbwg dataset before it enters merge.py and the downstream modelling workflow.

Unlike the analysis report, which simply describes the dataset, this document specifies every preprocessing operation that preprocessing.py shall implement. The objective is to transform the raw inflation indicator dataset into a standardized monthly time-series dataset that integrates consistently with every other economic dataset within the MmarakaAI pipeline.

This preprocessing stage is responsible only for producing a reliable analytical dataset. Feature engineering, lag generation, rolling statistics, scaling, normalization, encoding and model-specific preprocessing are intentionally excluded.

---

# Executive Summary

Dataset Name

ObservationData_bkgkbwg

Original Dataset Characteristics

• 1108 rows

• 4 columns

• Long statistical time-series

• Monthly observations

• Multiple inflation indicators

• Already machine-readable

Transformation Risk

LOW

Unlike the Producer Price Index or Consumer Price Index publications, this dataset already exists in an analytical format.

The primary preprocessing tasks are therefore validation, datetime normalization, indicator filtering and schema standardization rather than structural reconstruction.

Expected Output

A standardized monthly inflation dataset containing only macroeconomic indicators relevant to Botswana food inflation forecasting.

Expected structure

Date

Indicator

Value

---

# Dataset Overview

ObservationData_bkgkbwg is a normalized statistical dataset containing monthly macroeconomic indicators.

Unlike publication spreadsheets, the dataset already represents analytical observations where each row corresponds to one indicator measured at one point in time.

The dataset contains four variables

Indicator

Unit

Date

Value

No publication formatting artefacts such as merged cells, report titles or explanatory footnotes are present.

Consequently preprocessing focuses on validating temporal consistency, filtering economically relevant indicators and preparing the dataset for integration with the remaining monthly datasets.

Although the dataset is already relatively clean, preprocessing remains necessary to guarantee consistency across every dataset entering merge.py.

---

# Planned Transformations

| ID | Stage | Transformation | Priority |
|----|---------|---------------|----------|
| P001 | Structural Validation | Verify analytical schema | High |
| P002 | Cleaning | Validate measurement values | Medium |
| P003 | Datetime | Normalize monthly dates | Critical |
| P004 | Domain Filtering | Retain food inflation related indicators | Critical |
| P005 | Cleaning | Standardize indicator names | High |
| P006 | Validation | Verify chronological continuity | High |
| P007 | Validation | Verify merge compatibility | Critical |

---

# Structural Changes

## 1. Structural Validation

The dataset already conforms to a normalized analytical structure.

No structural reconstruction shall occur.

Instead preprocessing.py shall verify the existence of the expected analytical variables.

Expected schema

Indicator

Unit

Date

Value

Unexpected columns shall generate validation warnings.

No automatic deletion shall occur unless explicitly configured.

---

## 2. Cleaning

Although analysis.py reports no missing values and no duplicate observations, preprocessing shall still perform standard integrity checks.

Cleaning operations include

• remove leading and trailing whitespace

• standardize capitalization

• remove invisible characters

• verify numeric Value entries

• validate measurement units

• remove invalid indicator labels

Cleaning shall preserve all official statistical values.

---

## 3. Datetime Normalization

The Date variable contains monthly observations.

All dates shall be converted into pandas datetime format.

Examples

2016M01

↓

2016-01-01

2017M08

↓

2017-08-01

Monthly observations shall always use the first day of each month as the canonical timestamp.

This ensures compatibility across every monthly dataset.

---

## 4. Domain Filtering

ObservationData_bkgkbwg contains multiple inflation indicators.

Not every indicator contributes equally to food inflation prediction.

Only economically relevant indicators shall remain.

Examples include

Headline Inflation

Food Inflation

Imported Tradeables Inflation

Core Inflation

Trimmed Mean Inflation

Consumer Inflation

Food and Non Alcoholic Beverages

General CPI

Indicators unrelated to consumer food prices shall be excluded if encountered.

The objective is to reduce dimensionality while retaining the variables most likely to influence Botswana food inflation.

---

## 5. Indicator Standardization

Indicator names should be standardized to eliminate inconsistencies caused by capitalization, spacing or punctuation.

For example

Food inflation

Food Inflation

FOOD INFLATION

shall all become

Food Inflation

Standardized names simplify downstream feature engineering and merge operations.

---

# Validation Plan

preprocessing.py shall validate every preprocessing stage before exporting the cleaned dataset.

Validation 1

Verify expected analytical columns remain present.

Validation 2

Verify Date has dtype datetime64.

Validation 3

Verify chronological ordering.

Validation 4

Verify no duplicate

Date + Indicator

records exist.

Validation 5

Verify Value remains numeric.

Validation 6

Verify only approved inflation indicators remain.

Validation 7

Verify standardized indicator names are unique.

Validation 8

Verify merge compatibility with monthly datasets.

Validation 9

Verify row count changes only because of intentional indicator filtering.

Validation 10

Verify Unit values remain unchanged.

---

# Expected Output Dataset

The processed dataset shall remain a normalized monthly time-series while containing only economically relevant inflation indicators.

Expected schema

Date

Indicator

Unit

Value

Data Types

Date

datetime64[ns]

Indicator

string

Unit

string

Value

float64

Granularity

One observation

per indicator

per month.

Output Frequency

Monthly

Output Structure

Long-format relational dataset

Ready for merge.py

Yes

Ready for feature engineering

Yes

---

# Pipeline Impact

This preprocessing stage provides one of the core macroeconomic datasets used by MmarakaAI.

After preprocessing, the dataset can be merged directly with

Consumer Price Index

Producer Price Index

FAO Food Price Index

Imports

Exchange Rates

Agricultural Production

Livestock Production

using the standardized monthly Date field.

Subsequent feature engineering may derive

monthly growth rates

rolling averages

seasonal trends

lag variables

volatility measures

These operations are intentionally excluded from preprocessing.

---

# Notes

Engineering Assumptions

ObservationData_bkgkbwg already exists in an analytical relational structure.

Structural transformation is unnecessary.

The principal preprocessing objective is ensuring temporal consistency and retaining economically meaningful inflation indicators.

Transformations intentionally NOT performed

• Structural reconstruction

• Wide-to-long reshaping

• Feature engineering

• Lag generation

• Rolling averages

• Growth-rate calculations

• Scaling

• Standardization of numerical values

• PCA

• Encoding

• Outlier clipping

• Model-specific preprocessing

Implementation Notes

Recommended preprocessing sequence

load_dataset()

↓

validate_schema()

↓

clean_dataset()

↓

normalize_datetime()

↓

standardize_indicator_names()

↓

filter_inflation_indicators()

↓

validate_dataset()

↓

export_clean_dataset()

The exported dataset becomes the monthly inflation indicator input consumed directly by merge.py.