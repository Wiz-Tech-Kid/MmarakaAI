# Preprocessing Plan (P1)

Dataset Name: Producer Price Index 2000

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

This document defines the engineering specification for preprocessing the Producer Price Index dataset before it enters merge.py and the downstream modelling pipeline.

Unlike the analysis report, which only describes the dataset, this document specifies every preprocessing operation that preprocessing.py must implement. The objective is to transform the published Botswana Statistics Producer Price Index spreadsheet into a normalized monthly time-series dataset suitable for food inflation forecasting.

The preprocessing stage is responsible only for preparing reliable data. It is intentionally separated from feature engineering, scaling, encoding, lag generation and machine learning.

---

# Executive Summary

Dataset Name:
Producer Price Index 2000

Original Dataset Characteristics

• 651 rows

• 164 columns

• Publication spreadsheet

• Monthly observations

• Multiple industries presented as columns

• Human-readable statistical publication

Transformation Risk

HIGH

This dataset is not a machine-ready analytical dataset.

Although analysis.py classified it as a rectangular table, inspection shows that the spreadsheet is primarily a publication document containing report titles, merged headers, metadata rows and multiple industrial categories spread across numerous columns.

Consequently the largest preprocessing effort is structural reconstruction rather than cleaning.

Expected Output

A normalized monthly Producer Price Index dataset containing only industries relevant to Botswana food inflation modelling.

Expected structure:

Date

Industry

Producer Price Index

---

# Dataset Overview

The Producer Price Index dataset originates from Statistics Botswana publications rather than an operational database.

The spreadsheet was designed for human interpretation.

Its structure includes:

• publication titles

• section headings

• merged cells

• blank spacer rows

• explanatory notes

• grouped industrial sectors

• year/month columns

• wide cross-tab layout

Although analysis.py reports a rectangular dataset with 164 columns, these columns do not represent analytical variables.

Instead they represent multiple industrial sectors distributed horizontally across the spreadsheet.

The preprocessing objective is therefore to reconstruct the publication into a normalized relational dataset.

No assumptions should be made from column names such as

Unnamed:0

Unnamed:1

Unnamed:2

because these are artefacts of spreadsheet import rather than meaningful variables.

---

# Planned Transformations

| ID | Stage | Transformation | Priority |
|----|---------|---------------|----------|
| P001 | Structural Transformation | Remove publication metadata | Critical |
| P002 | Structural Transformation | Detect actual table header | Critical |
| P003 | Structural Transformation | Promote header row | Critical |
| P004 | Structural Transformation | Remove empty rows and columns | High |
| P005 | Structural Transformation | Convert wide industrial table into long format | Critical |
| P006 | Cleaning | Remove duplicated observations | Medium |
| P007 | Cleaning | Remove repeated header rows | High |
| P008 | Datetime | Convert monthly period into datetime | Critical |
| P009 | Domain Filtering | Retain only food-related industries | Critical |
| P010 | Validation | Verify chronological continuity | High |

---

# Structural Changes

## 1. Publication Reconstruction

The spreadsheet should first be treated as a statistical publication rather than a dataset.

preprocessing.py shall remove

• report titles

• publication numbers

• explanatory paragraphs

• footnotes

• copyright text

• empty rows

• separator rows

• repeated headers

None of these contribute to modelling.

---

## 2. Header Detection

The imported dataframe contains numerous unnamed columns.

The preprocessing stage must automatically detect the first row containing the real industrial category names.

Once detected

that row becomes the dataframe header.

All rows above it are discarded.

---

## 3. Wide-to-Long Transformation

The current publication stores industries horizontally.

Example

            Jan2000 Feb2000 ...

Agriculture

Food Products

Textiles

Mining

etc.

This structure cannot be merged with the remaining monthly datasets.

The preprocessing pipeline must reshape the table into

Date

Industry

PPI

Each row must represent one observation.

This transformation is mandatory.

---

## 4. Datetime Normalization

Month labels shall be converted into proper pandas datetime objects.

Accepted examples

2000M01

Jan-2000

2000-01

must all become

2000-01-01

The first day of each month shall represent the monthly observation.

Datetime conversion must occur before merge.py.

---

## 5. Domain Filtering

The objective of MmarakaAI is forecasting food inflation.

Therefore preprocessing shall retain only Producer Price Index categories that influence food prices.

Examples include

Agriculture

Crop Production

Livestock

Food Manufacturing

Meat Products

Dairy Products

Grain Milling

Fruit Processing

Vegetable Processing

Beverage Manufacturing

Sugar

Edible Oils

Fishing

Food-related Wholesale Production

Industries unrelated to food economics shall be removed.

Examples include

Mining

Construction

Textiles

Transport Equipment

Chemicals

Metals

Electrical Equipment

Furniture

Publishing

Telecommunications

These sectors increase dimensionality without improving food inflation prediction.

Filtering therefore reduces model complexity while improving economic relevance.

---

## 6. Duplicate Handling

Duplicates should be evaluated after restructuring.

Duplicate publication rows

duplicate industry/date pairs

and repeated headers must all be removed.

Only unique

(Date, Industry)

records should remain.

---

# Validation Plan

preprocessing.py shall perform validation after every major transformation.

Validation 1

Verify publication metadata has been removed.

Validation 2

Verify header promotion produced meaningful column names.

Validation 3

Verify no unnamed analytical columns remain except where unavoidable.

Validation 4

Verify every record contains

Date

Industry

Producer Price Index.

Validation 5

Verify every Date value is datetime64.

Validation 6

Verify months are sorted chronologically.

Validation 7

Verify each Industry-Date pair is unique.

Validation 8

Verify only approved food-related industries remain.

Validation 9

Verify no duplicated monthly observations exist.

Validation 10

Verify the reshaped dataset can merge directly with CPI, FAO and import datasets using Date.

---

# Expected Output Dataset

The final dataset should no longer resemble the publication spreadsheet.

Expected schema

Date

Industry

Producer_Price_Index

Data Types

Date

datetime64[ns]

Industry

string

Producer_Price_Index

float64

Granularity

One row

per industry

per month.

Output Frequency

Monthly.

Output Structure

Long-format relational dataset.

Ready for merge.py

Yes.

Ready for feature engineering

Yes.

---

# Pipeline Impact

This preprocessing stage is one of the most important transformations within MmarakaAI.

Without structural reconstruction the Producer Price Index cannot be merged with

Food CPI

FAO Food Price Index

Imports

Agricultural Production

Livestock Production

or Inflation datasets.

Successful preprocessing produces a consistent monthly dataset that aligns with the remainder of the economic indicators.

Feature engineering can subsequently generate rolling averages, lag variables, growth rates and volatility measures without additional restructuring.

No feature engineering shall occur during preprocessing.

---

# Notes

Engineering Assumptions

This dataset originates from a Statistics Botswana publication and therefore requires publication reconstruction before analytical processing.

Structural transformation precedes all cleaning activities.

Cleaning begins only after the analytical table has been reconstructed.

Transformations intentionally NOT performed

• Feature engineering

• Rolling statistics

• Lag generation

• Moving averages

• Scaling

• Standardization

• Normalization

• PCA

• Encoding

• Outlier clipping

• Model-specific preprocessing

These belong to later pipeline stages.

Implementation Notes

The preprocessing implementation should be modular.

Recommended execution order

load_dataset()

↓

structural_transformation()

↓

clean_dataset()

↓

normalize_datetime()

↓

filter_food_industries()

↓

validate_dataset()

↓

export_clean_dataset()

This output becomes the Producer Price Index input consumed directly by merge.py.