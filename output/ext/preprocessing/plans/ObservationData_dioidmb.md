# Preprocessing Plan (P1)

Dataset Name: ObservationData_dioidmb

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

This document defines the engineering specification for preprocessing the ObservationData_dioidmb dataset before it enters merge.py and the downstream modelling workflow.

Unlike the analysis report, which only summarizes metadata discovered by analysis.py, this document specifies the complete preprocessing implementation that preprocessing.py must perform. The objective is to transform annual crop production observations into a standardized monthly dataset that aligns temporally with all remaining economic indicators used by MmarakaAI.

This preprocessing stage prepares the dataset for integration into the modelling pipeline. It intentionally excludes feature engineering, normalization, scaling, encoding, rolling statistics, lag generation and machine learning transformations.

---

# Executive Summary

Dataset Name

ObservationData_dioidmb

Original Dataset Characteristics

• 886 rows

• 8 columns

• Long-format statistical dataset

• Annual observations

• Agricultural production indicators

• Administrative attributes

Transformation Risk

MEDIUM

The dataset is already stored as an analytical long-format table.

Unlike Botswana statistical publications, no publication reconstruction is required.

The major preprocessing challenge is converting annual agricultural observations into a monthly representation that allows direct integration with CPI, Producer Price Index, FAO Food Price Index, imports and exchange rate datasets.

Analysis.py detected duplicate observations, therefore integrity checking and duplicate removal become mandatory preprocessing steps before temporal alignment.

Expected Output

A cleaned monthly agricultural production dataset.

Expected structure

Date

District

Indicator

Value

---

# Dataset Overview

ObservationData_dioidmb contains agricultural production statistics recorded in long-format.

Each row already represents an analytical observation rather than spreadsheet formatting information.

The primary variables include

• district

• indicator

• sex

• age-group

• marital-status

• Unit

• Date

• Value

Unlike publication spreadsheets, these columns should not be reconstructed.

Instead, preprocessing focuses on validating data integrity, eliminating duplicate observations, standardizing temporal representation and preparing the dataset for monthly alignment.

The dataset represents annual agricultural production values rather than monthly measurements.

Therefore preprocessing must preserve the reported statistics without generating artificial production estimates.

---

# Planned Transformations

| ID | Stage | Transformation | Priority |
|----|---------|---------------|----------|
| P001 | Structural Validation | Verify analytical schema | High |
| P002 | Cleaning | Remove duplicate observations | Critical |
| P003 | Cleaning | Remove invalid records | High |
| P004 | Datetime | Convert annual dates into datetime objects | Critical |
| P005 | Frequency Alignment | Replicate annual observations across monthly timeline | Critical |
| P006 | Domain Filtering | Retain food crop indicators | Critical |
| P007 | Validation | Verify chronological consistency | High |
| P008 | Validation | Verify merge compatibility | Critical |

---

# Structural Changes

## 1. Structural Validation

ObservationData_dioidmb already conforms to a relational long-format structure.

Structural reconstruction is unnecessary.

Instead preprocessing.py shall validate that the expected analytical variables remain available.

Expected variables include

District

Indicator

Sex

Age Group

Marital Status

Unit

Date

Value

Unexpected columns shall trigger validation warnings rather than automatic deletion.

---

## 2. Duplicate Removal

Analysis.py identified duplicate observations within this dataset.

Duplicate records must be removed before any temporal processing occurs.

Duplicates shall be evaluated using all identifying fields rather than Date alone.

Recommended uniqueness definition

Date

District

Indicator

Sex

Age Group

Marital Status

Unit

Value

Only exact duplicate observations should be removed.

Legitimate repeated annual values representing different indicators must remain.

The objective is to preserve the intended statistical grain while eliminating redundant records.

---

## 3. Cleaning

General cleaning shall include

• removal of duplicate observations

• trimming whitespace

• correcting inconsistent capitalization

• removing empty text values

• validating numeric Value fields

• validating Unit entries

• verifying indicator names

Cleaning shall never modify reported production quantities.

---

## 4. Datetime Normalization

Annual observations shall be converted into pandas datetime format.

Examples

2017

↓

2017-01-01

2018

↓

2018-01-01

The annual observation shall always correspond to the first day of January.

This provides a standardized monthly anchor for merge operations.

---

## 5. Frequency Alignment

Crop production statistics are annual.

The majority of datasets within MmarakaAI are monthly.

Interpolation shall NOT be used.

Agricultural production cannot be assumed to change smoothly each month.

Interpolation would create synthetic production values unsupported by official statistics.

Instead every annual observation shall be replicated across the twelve months of the corresponding calendar year.

Example

2020

Maize Production

Value = 45 600 tonnes

becomes

2020-01

45600

2020-02

45600

...

2020-12

45600

This preserves the original agricultural statistic while enabling direct monthly joins.

---

## 6. Domain Filtering

Only agricultural indicators that contribute directly or indirectly to Botswana food inflation should remain.

Examples include

Maize

Sorghum

Millet

Beans

Groundnuts

Vegetables

Fruit

Wheat

Rice

Oil Crops

Horticulture

Food Crop Production

Indicators unrelated to food production should be excluded if encountered.

Examples include

Forestry

Industrial Crops

Non-food cash crops

Experimental categories unrelated to consumer food markets

This filtering reduces unnecessary dimensionality while improving model relevance.

---

## 7. Administrative Variables

District

Sex

Age Group

Marital Status

should remain unchanged during preprocessing.

These dimensions may later support regional or demographic feature engineering.

No aggregation shall occur during preprocessing.

Aggregation belongs to feature engineering.

---

# Validation Plan

preprocessing.py shall perform validation immediately after every transformation.

Validation 1

Verify duplicate observations have been removed.

Validation 2

Verify Date is datetime64.

Validation 3

Verify every annual record expands into exactly twelve monthly observations.

Validation 4

Verify replicated monthly values equal the original annual statistic.

Validation 5

Verify all agricultural indicators remain valid.

Validation 6

Verify no duplicate

Date + District + Indicator

records remain.

Validation 7

Verify chronological ordering.

Validation 8

Verify merge compatibility with monthly datasets.

Validation 9

Verify Value remains numeric after every preprocessing stage.

Validation 10

Verify row counts after expansion equal

Clean Annual Records × 12

---

# Expected Output Dataset

The processed dataset should preserve the original agricultural statistics while becoming fully compatible with monthly economic datasets.

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

per crop indicator

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

This preprocessing stage converts annual agricultural production data into a temporally compatible monthly dataset while preserving the integrity of the original official statistics.

The resulting dataset can be merged directly with

Consumer Price Index

Producer Price Index

FAO Food Price Index

Imports

Exchange Rates

Livestock Production

Inflation Indicators

using the Date field.

Because interpolation is intentionally avoided, the statistical meaning of the agricultural data remains unchanged.

Subsequent feature engineering may derive

rolling means

growth rates

lag variables

seasonal indicators

or trend features.

These operations are intentionally excluded from preprocessing.

---

# Notes

Engineering Assumptions

ObservationData_dioidmb already exists in analytical long format.

No publication reconstruction is required.

Annual values represent official reported agricultural statistics and must remain unchanged throughout preprocessing.

Transformations intentionally NOT performed

• Structural reshaping

• Interpolation

• Feature engineering

• Lag generation

• Rolling averages

• Growth-rate calculations

• Scaling

• Standardization

• Encoding

• PCA

• Outlier clipping

• Model-specific preprocessing

Implementation Notes

Recommended preprocessing sequence

load_dataset()

↓

validate_schema()

↓

remove_duplicates()

↓

clean_dataset()

↓

normalize_datetime()

↓

expand_annual_to_monthly()

↓

filter_food_crop_indicators()

↓

validate_dataset()

↓

export_clean_dataset()

The exported dataset becomes the agricultural production input consumed directly by merge.py.