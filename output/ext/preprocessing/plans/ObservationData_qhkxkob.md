# Preprocessing Plan (P1)

Dataset Name: ObservationData_qhkxkob

Pipeline Position:
Raw Dataset
→ Structural Transformation
→ Data Cleaning
→ Datetime Normalization
→ Frequency Alignment
→ Domain Filtering
→ Merge Pipeline
→ Feature Engineering
→ Machine Learning Models

Purpose of this document:

This document defines the engineering specification for preprocessing the ObservationData_qhkxkob dataset before it enters merge.py and the downstream modelling pipeline.

Unlike the analysis report, which only summarizes metadata, this document specifies every preprocessing operation that preprocessing.py must implement. The objective is to transform the raw livestock production dataset into a standardized monthly time-series dataset compatible with every other economic indicator used within the MmarakaAI modelling pipeline.

This preprocessing stage prepares the dataset for merging only. It deliberately excludes feature engineering, scaling, encoding, lag generation, rolling statistics and machine learning transformations.

---

# Executive Summary

Dataset Name

ObservationData_qhkxkob

Original Dataset Characteristics

• 165 rows

• 8 columns

• Long-format statistical dataset

• Annual observations

• Livestock-related indicators

• Administrative and demographic attributes

Transformation Risk

MEDIUM

Unlike the Producer Price Index dataset, this dataset is already stored in a machine-readable long format.

The primary preprocessing challenge is therefore not structural reconstruction but temporal alignment. Since most economic indicators used by MmarakaAI are monthly, this annual dataset must be transformed into a monthly representation while preserving its statistical meaning.

Expected Output

A cleaned monthly livestock production dataset suitable for merging with all other monthly economic datasets.

Expected structure

Date

Indicator

District

Value

---

# Dataset Overview

ObservationData_qhkxkob is a long-format statistical dataset where each row represents one recorded observation.

The dataset already follows a relational structure and therefore does not require publication-table reconstruction.

Its variables include

• district

• indicator

• sex

• age-group

• marital-status

• Unit

• Date

• Value

Unlike spreadsheet publications produced by Statistics Botswana, these fields already represent analytical variables rather than formatting artefacts.

The preprocessing objective is therefore to improve temporal consistency, remove unnecessary analytical dimensions where appropriate, and prepare the dataset for monthly alignment with the remaining datasets used by MmarakaAI.

No reshaping from wide-to-long format is required because the dataset is already normalized.

---

# Planned Transformations

| ID | Stage | Transformation | Priority |
|----|---------|---------------|----------|
| P001 | Structural Validation | Verify analytical schema | High |
| P002 | Cleaning | Remove duplicate observations if discovered | Medium |
| P003 | Cleaning | Remove invalid records | High |
| P004 | Datetime | Convert annual dates into datetime objects | Critical |
| P005 | Frequency Alignment | Expand annual observations into monthly records | Critical |
| P006 | Domain Filtering | Remove non-food indicators if present | High |
| P007 | Validation | Verify monthly continuity | High |
| P008 | Validation | Verify merge compatibility | Critical |

---

# Structural Changes

## 1. Structural Validation

Unlike publication spreadsheets, ObservationData_qhkxkob already follows a normalized relational design.

Therefore preprocessing shall verify rather than reconstruct the schema.

The expected analytical variables are

District

Indicator

Sex

Age Group

Marital Status

Unit

Date

Value

Unexpected columns shall trigger validation warnings.

---

## 2. Cleaning

Although analysis.py reports no missing values and no duplicate observations, preprocessing.py shall still perform integrity checks.

Cleaning operations include

• remove duplicated rows if encountered

• remove records with invalid dates

• remove records with missing indicator names

• remove rows with invalid measurement units

• trim leading and trailing whitespace

• standardize text capitalization where required

Cleaning should never modify valid measurement values.

---

## 3. Datetime Normalization

The Date field currently represents annual observations.

It shall be converted into pandas datetime format.

Examples

2015

↓

2015-01-01

2016

↓

2016-01-01

The first day of January represents the annual observation.

Datetime normalization ensures compatibility with merge.py.

---

## 4. Frequency Alignment

This dataset is annual.

The remainder of the MmarakaAI economic datasets are monthly.

Interpolation shall NOT be used.

Interpolation would create artificial livestock production values that never existed.

Instead, each annual observation shall be replicated across every month of the corresponding year.

Example

2019
Value = 8450

becomes

2019-01

8450

2019-02

8450

2019-03

8450

...

2019-12

8450

This preserves the reported annual value while allowing monthly alignment with CPI, FAO Food Price Index, imports and exchange rate datasets.

---

## 5. Domain Filtering

Only livestock-related indicators relevant to food inflation modelling shall be retained.

Examples include

Cattle

Goats

Sheep

Poultry

Livestock Production

Animal Products

Meat Production

Milk Production

Egg Production

Indicators unrelated to food production should be removed if they appear in future releases.

The objective is to retain only economically meaningful predictors for food inflation.

---

## 6. Administrative Dimensions

The dataset contains demographic and administrative attributes such as

District

Sex

Age Group

Marital Status

These variables should be preserved during preprocessing unless the downstream merge strategy requires aggregation.

No aggregation should occur during preprocessing.

Aggregation decisions belong to feature engineering.

---

# Validation Plan

preprocessing.py shall validate every transformation before exporting the cleaned dataset.

Validation 1

Verify all expected columns remain present.

Validation 2

Verify Date has dtype datetime64.

Validation 3

Verify every annual observation expands into exactly twelve monthly records.

Validation 4

Verify replicated monthly values remain identical to the original annual value.

Validation 5

Verify no duplicate

Date + Indicator + District

records exist.

Validation 6

Verify chronological ordering.

Validation 7

Verify livestock indicators remain intact.

Validation 8

Verify merge compatibility with monthly datasets.

Validation 9

Verify row counts after annual expansion equal

Original Annual Records × 12

Validation 10

Verify Value remains numeric after every transformation.

---

# Expected Output Dataset

The output dataset should remain normalized while becoming fully compatible with the monthly modelling pipeline.

Expected schema

Date

District

Indicator

Sex

Age Group

Marital Status

Unit

Value

Data Types

Date

datetime64[ns]

District

string

Indicator

string

Sex

string

Age Group

string

Marital Status

string

Unit

string

Value

float64

Granularity

One observation

per indicator

per district

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

This preprocessing stage enables annual livestock production data to participate in monthly food inflation modelling without introducing artificial estimates.

By replicating annual observations instead of interpolating them, the economic meaning of the dataset is preserved while achieving temporal compatibility with

Consumer Price Index

Producer Price Index

Food Price Index

Exchange Rates

Imports

Agricultural Production

The resulting dataset can then be merged directly using the Date field.

Feature engineering may later compute growth rates, rolling averages or lag variables.

Those operations are intentionally excluded from preprocessing.

---

# Notes

Engineering Assumptions

This dataset already exists in analytical long format.

Structural reconstruction is therefore unnecessary.

The principal engineering task is temporal alignment.

Transformations intentionally NOT performed

• Structural reshaping

• Interpolation

• Feature engineering

• Lag generation

• Rolling averages

• Moving averages

• Scaling

• Standardization

• Encoding

• PCA

• Outlier clipping

• Model-specific preprocessing

Implementation Notes

Recommended execution sequence

load_dataset()

↓

validate_schema()

↓

clean_dataset()

↓

normalize_datetime()

↓

expand_annual_to_monthly()

↓

filter_domain()

↓

validate_dataset()

↓

export_clean_dataset()

The exported dataset becomes the livestock production input consumed directly by merge.py.