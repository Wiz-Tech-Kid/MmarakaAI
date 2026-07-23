# Preprocessing Plan (P1)

Dataset Name: food_price_indices_data

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

This document defines the engineering specification for preprocessing the FAO Food Price Indices dataset before it enters merge.py and the downstream modelling workflow.

Unlike the analysis report, which only summarizes the spreadsheet characteristics, this document specifies every preprocessing operation that preprocessing.py shall perform. The objective is to transform the FAO publication spreadsheet into a normalized monthly analytical dataset that integrates directly with the remaining economic datasets used within MmarakaAI.

The preprocessing stage is responsible only for preparing reliable analytical data. Feature engineering, lag creation, rolling statistics, scaling, encoding, dimensionality reduction and machine learning preprocessing are intentionally excluded.

---

# Executive Summary

Dataset Name

food_price_indices_data

Original Dataset Characteristics

• 441 rows

• 66 columns

• FAO publication spreadsheet

• Monthly observations

• Multiple commodity price indices

• Human-readable statistical publication

Transformation Risk

HIGH

Although analysis.py reports this dataset as a rectangular table, the spreadsheet is actually a publication designed for human interpretation rather than analytical processing.

The majority of preprocessing effort therefore consists of reconstructing the publication into a normalized relational dataset before any cleaning or validation begins.

Expected Output

A normalized monthly FAO Food Price Index dataset.

Expected structure

Date

Commodity

Food_Price_Index

---

# Dataset Overview

The FAO Food Price Indices dataset is distributed as a statistical publication rather than a transactional database.

The spreadsheet contains

• publication headings

• explanatory text

• merged cells

• blank separator rows

• metadata

• notes

• commodity categories

• monthly observations distributed across columns

Although analysis.py identified 66 columns, many of these columns are not analytical variables.

Instead they represent spreadsheet formatting produced for publication.

The preprocessing objective is therefore to reconstruct the publication into a normalized monthly dataset.

The reported high percentage of missing values is expected because blank formatting cells within the publication are interpreted as missing data by spreadsheet import tools.

These cells should not be treated as genuine missing observations until the publication structure has been reconstructed.

---

# Planned Transformations

| ID | Stage | Transformation | Priority |
|----|---------|---------------|----------|
| P001 | Structural Transformation | Remove publication metadata | Critical |
| P002 | Structural Transformation | Detect and promote true header row | Critical |
| P003 | Structural Transformation | Remove empty rows and columns | Critical |
| P004 | Structural Transformation | Convert wide commodity table into long format | Critical |
| P005 | Cleaning | Remove publication artefacts | High |
| P006 | Datetime | Normalize monthly dates | Critical |
| P007 | Domain Filtering | Retain relevant food commodity indices | Critical |
| P008 | Validation | Verify monthly continuity | High |
| P009 | Validation | Verify merge compatibility | Critical |

---

# Structural Changes

## 1. Publication Reconstruction

This spreadsheet shall initially be treated as a statistical publication instead of a dataset.

preprocessing.py shall remove

• publication titles

• report numbers

• explanatory paragraphs

• copyright notices

• footnotes

• notes

• blank rows

• blank columns

• repeated headers

These elements are required for human reading but have no analytical value.

Structural reconstruction must be completed before any cleaning operations begin.

---

## 2. Header Detection

The imported dataframe contains numerous unnamed columns that resulted from spreadsheet formatting.

The preprocessing pipeline shall automatically identify the first row containing the actual commodity names and monthly observations.

That row shall become the dataframe header.

Every preceding row shall be discarded.

Column names shall then be standardized into descriptive analytical names.

No "Unnamed" columns should remain after reconstruction unless absolutely unavoidable.

---

## 3. Wide-to-Long Transformation

The publication stores commodity indices horizontally.

Example

```
Commodity      Jan2000   Feb2000   Mar2000
Meat
Dairy
Cereals
Vegetable Oils
Sugar
```

This structure cannot be merged with the remainder of the modelling datasets.

The preprocessing pipeline shall reshape the publication into

Date

Commodity

Food_Price_Index

Each row shall represent one commodity measured during one month.

This transformation is mandatory.

---

## 4. Cleaning

Cleaning begins only after structural reconstruction has been completed.

Cleaning operations include

• remove duplicated commodity records

• remove repeated publication headers

• remove empty observations

• trim whitespace

• standardize commodity names

• validate numerical price index values

Publication formatting artefacts shall never be interpreted as analytical observations.

---

## 5. Datetime Normalization

Monthly labels shall be converted into pandas datetime format.

Accepted examples include

Jan-2000

2000M01

2000-01

All representations shall become

2000-01-01

The first day of each month represents the monthly observation.

This standardization ensures compatibility with every other monthly dataset.

---

## 6. Domain Filtering

The FAO publication contains several commodity indices.

Only food-related commodity indices relevant to Botswana food inflation modelling shall be retained.

Examples include

Overall Food Price Index

Meat

Dairy

Cereals

Vegetable Oils

Sugar

These indices represent internationally recognised food price benchmarks and are expected to influence domestic food prices through imports and trade.

Non-food variables, metadata fields and publication descriptors shall be removed.

---

## 7. Missing Value Assessment

Analysis.py reports a high percentage of missing values.

These missing values shall not automatically trigger imputation.

Instead preprocessing.py shall first determine whether the apparent missing values originate from

• blank publication formatting

• merged spreadsheet cells

• intentionally empty separators

Only genuine analytical missing observations should remain after structural reconstruction.

If genuine missing observations exist, they shall be documented rather than automatically imputed.

---

# Validation Plan

preprocessing.py shall validate each transformation immediately after implementation.

Validation 1

Verify publication metadata has been removed.

Validation 2

Verify the promoted header contains analytical variable names.

Validation 3

Verify no unnecessary unnamed columns remain.

Validation 4

Verify every observation contains

Date

Commodity

Food_Price_Index.

Validation 5

Verify Date has dtype datetime64.

Validation 6

Verify commodity names are standardized.

Validation 7

Verify monthly chronology is continuous.

Validation 8

Verify duplicate commodity-date observations do not exist.

Validation 9

Verify numerical price indices remain unchanged after restructuring.

Validation 10

Verify the dataset merges correctly with CPI, Producer Price Index, imports and exchange rate datasets.

---

# Expected Output Dataset

The final dataset shall no longer resemble the original publication spreadsheet.

Expected schema

Date

Commodity

Food_Price_Index

Data Types

Date

datetime64[ns]

Commodity

string

Food_Price_Index

float64

Granularity

One observation

per commodity

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

The FAO Food Price Index dataset is one of the principal international leading indicators used by MmarakaAI.

Following preprocessing, the dataset can be merged directly with

Consumer Price Index

Producer Price Index

Exchange Rates

Imports

Agricultural Production

Livestock Production

Inflation Indicators

using the standardized monthly Date field.

The resulting dataset provides internationally observed food commodity price movements that complement Botswana's domestic economic indicators.

Feature engineering may later derive

commodity growth rates

rolling averages

volatility indicators

lag variables

seasonal effects

These operations are intentionally excluded from preprocessing.

---

# Notes

Engineering Assumptions

The source spreadsheet is a publication document rather than an analytical database.

Structural reconstruction must therefore precede all cleaning activities.

Cleaning shall begin only after the publication has been converted into an analytical table.

Transformations intentionally NOT performed

• Feature engineering

• Rolling averages

• Lag generation

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

structural_transformation()

↓

detect_headers()

↓

reshape_wide_to_long()

↓

clean_dataset()

↓

normalize_datetime()

↓

filter_food_indices()

↓

validate_dataset()

↓

export_clean_dataset()

The exported dataset becomes the FAO Food Price Index input consumed directly by merge.py.