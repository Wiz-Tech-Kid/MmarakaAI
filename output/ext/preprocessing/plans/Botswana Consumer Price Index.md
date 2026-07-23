# Preprocessing Plan (P1)

Dataset Name: Botswana_Consumer_Price_Index

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

This document defines the engineering specification for preprocessing the Botswana Consumer Price Index (CPI) dataset before it enters merge.py and the downstream modelling workflow.

Unlike the analysis report, which only describes the dataset structure, this document specifies every preprocessing operation that preprocessing.py shall implement. The objective is to transform the CPI statistical publication into a standardized monthly analytical dataset suitable for integration with all other economic datasets within the MmarakaAI pipeline.

This preprocessing stage prepares the dataset exclusively for merging. Feature engineering, lag creation, rolling statistics, scaling, normalization, encoding and model-specific transformations are intentionally excluded.

---

# Executive Summary

Dataset Name

Botswana Consumer Price Index

Original Dataset Characteristics

• Statistical publication spreadsheet

• Monthly observations

• Multiple CPI divisions and categories

• Wide-format publication table

• Human-readable report

Transformation Risk

HIGH

The Botswana CPI dataset is published as a statistical report intended for human interpretation rather than machine learning.

Although spreadsheet software imports the file as a table, much of its structure consists of publication formatting rather than analytical variables.

Consequently, preprocessing focuses primarily on reconstructing the publication into a normalized analytical dataset before any cleaning operations begin.

Expected Output

A normalized monthly Consumer Price Index dataset.

Expected structure

Date

Category

Consumer_Price_Index

---

# Dataset Overview

The Botswana Consumer Price Index dataset is distributed as an official statistical publication.

The workbook typically contains

• report titles

• publication dates

• explanatory notes

• CPI divisions

• CPI groups

• merged cells

• blank formatting rows

• repeated headers

• monthly CPI observations

Although these elements are useful for reading the report, they prevent direct analytical processing.

The preprocessing objective is therefore to reconstruct the publication into a relational time-series dataset that can be merged with Producer Price Index, FAO Food Price Index, Imports, Exchange Rates and Agricultural Production datasets.

The published workbook should never be treated as a machine-ready dataset until structural transformation has been completed.

---

# Planned Transformations

| ID | Stage | Transformation | Priority |
|----|---------|---------------|----------|
| P001 | Structural Transformation | Remove publication formatting | Critical |
| P002 | Structural Transformation | Detect true header row | Critical |
| P003 | Structural Transformation | Remove empty rows and columns | Critical |
| P004 | Structural Transformation | Convert wide CPI table into long format | Critical |
| P005 | Cleaning | Remove publication artefacts | High |
| P006 | Datetime | Normalize monthly dates | Critical |
| P007 | Domain Filtering | Retain inflation indicators relevant to food inflation modelling | Critical |
| P008 | Validation | Verify monthly consistency | High |
| P009 | Validation | Verify merge compatibility | Critical |

---

# Structural Changes

## 1. Publication Reconstruction

The spreadsheet shall first be treated as a statistical publication.

preprocessing.py shall remove

• report titles

• publication metadata

• explanatory paragraphs

• source references

• copyright notices

• footnotes

• notes

• blank separator rows

• blank separator columns

• duplicated headers

These elements are not analytical observations.

Structural reconstruction shall always occur before cleaning.

---

## 2. Header Detection

The imported dataframe may contain numerous unnamed columns resulting from merged spreadsheet cells.

The preprocessing pipeline shall automatically locate the first row containing actual monthly CPI observations.

That row shall become the dataframe header.

Rows above this point shall be discarded.

Unnamed columns shall be removed only after confirming they contain no analytical information.

---

## 3. Wide-to-Long Transformation

The publication commonly stores CPI categories horizontally.

Example

Category

Jan

Feb

Mar

Apr

Food

Transport

Housing

Education

Health

This format prevents efficient merging with other monthly datasets.

The preprocessing pipeline shall reshape the publication into

Date

Category

Consumer_Price_Index

Each row shall represent one CPI category measured during one month.

This normalized structure is required throughout MmarakaAI.

---

## 4. Cleaning

Cleaning begins after publication reconstruction.

Operations include

• remove duplicated observations

• remove repeated headers

• trim whitespace

• standardize category names

• remove empty analytical rows

• validate numerical CPI values

Formatting artefacts shall never be interpreted as missing economic observations.

---

## 5. Datetime Normalization

Monthly labels shall be converted into pandas datetime format.

Examples

Jan-2021

↓

2021-01-01

2021M01

↓

2021-01-01

2021-01

↓

2021-01-01

The first day of each month shall represent every monthly observation.

---

## 6. Domain Filtering

The CPI publication contains many expenditure divisions.

Only categories that directly or indirectly influence food inflation modelling shall be retained.

Examples include

Headline CPI

Food and Non Alcoholic Beverages

Imported Tradeables

Core Inflation

Trimmed Mean CPI

General Consumer Price Index

Food CPI

Other CPI categories unrelated to food price behaviour may be removed if they contribute little predictive value.

Examples include

Education

Recreation

Insurance Services

Miscellaneous Personal Services

where appropriate.

The objective is to maximize predictive relevance while minimizing unnecessary dimensionality.

---

## 7. Missing Value Assessment

Any missing values identified before structural reconstruction shall not immediately be treated as genuine missing observations.

Missing cells may originate from

• merged spreadsheet cells

• publication formatting

• empty separators

• repeated section breaks

Only missing analytical values remaining after reconstruction should be evaluated.

Automatic imputation shall not occur during preprocessing.

---

# Validation Plan

preprocessing.py shall validate every preprocessing stage before exporting the dataset.

Validation 1

Verify publication metadata has been removed.

Validation 2

Verify promoted headers contain analytical variable names.

Validation 3

Verify no unnecessary unnamed columns remain.

Validation 4

Verify every observation contains

Date

Category

Consumer_Price_Index.

Validation 5

Verify Date is datetime64.

Validation 6

Verify chronological monthly ordering.

Validation 7

Verify no duplicate

Date + Category

records exist.

Validation 8

Verify CPI values remain numeric.

Validation 9

Verify retained CPI categories match approved domain filters.

Validation 10

Verify compatibility with merge.py.

---

# Expected Output Dataset

Expected schema

Date

Category

Consumer_Price_Index

Data Types

Date

datetime64[ns]

Category

string

Consumer_Price_Index

float64

Granularity

One observation

per CPI category

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

The Botswana Consumer Price Index is one of the principal target datasets within the MmarakaAI pipeline.

Following preprocessing, the dataset can be merged directly with

Producer Price Index

FAO Food Price Index

Exchange Rates

Imports

Agricultural Production

Livestock Production

Inflation Indicators

using the standardized monthly Date field.

The cleaned dataset provides the primary measure of domestic price movements that will later support food inflation forecasting models.

Feature engineering may later derive

monthly inflation rates

rolling averages

lag variables

seasonal indicators

volatility measures

These operations are intentionally excluded from preprocessing.

---

# Notes

Engineering Assumptions

The Botswana CPI workbook is a statistical publication rather than a machine-learning-ready dataset.

Structural reconstruction shall therefore precede all cleaning operations.

The resulting dataset must be fully normalized before entering merge.py.

Transformations intentionally NOT performed

• Feature engineering

• Lag generation

• Rolling averages

• Growth-rate calculations

• Scaling

• Standardization

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

filter_cpi_categories()

↓

validate_dataset()

↓

export_clean_dataset()

The exported dataset becomes the Botswana Consumer Price Index input consumed directly by merge.py.