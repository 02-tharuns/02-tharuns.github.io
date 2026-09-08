---
id: datascience
section: skills
title: General applied machine learning and data science fit
type: domain
date: 2026-09
domain: data-science, ai
---

## Why general applied machine learning and data science roles fit
Four projects sit outside the sensor and edge focus and demonstrate general
tabular and time-series modelling: Credit Card Fraud Prediction (XGBoost
with Bayesian hyperparameter tuning and SMOTE class-imbalance handling, 97
percent precision at 89 percent recall), the Supply Chain Risk pipeline
(leakage-safe feature engineering over 180,000 orders, late-risk recall
raised from 57.5 to 78.8 percent through decision-threshold tuning),
Forecasting Used Car Prices (stacked regression lifting R-squared from 0.68
to 0.80), and the Automated ML Pipeline and Model Recommendation Platform (a
reusable system spanning classification, regression, clustering and
time-series workflows). Together they cover the standard applied machine
learning loop end to end: data cleaning, leakage-safe feature engineering,
model selection, threshold and decision tuning, and evaluation reported
honestly rather than optimistically.

## Business-outcome framing, not just model metrics
Two of these projects were explicitly tuned against a business trade-off
rather than a raw accuracy number: the supply-chain model's decision
threshold was set at 0.40 specifically because a missed late shipment costs
more than a false alarm someone can dismiss, and the used-car pricing
dashboards were delivered to 8 stakeholders to support real pricing
decisions rather than left as a notebook metric. The same discipline —
reporting a metric downward whenever a higher figure cannot be defended —
carries over from his sensor and edge work.

## Feature engineering and dimensionality
The supply-chain pipeline is the clearest case of that discipline showing up
on tabular data instead of sensor data: reduced one-hot encoded
dimensionality from over 64,000 features to 339 through high-cardinality
feature optimisation, a data-modelling decision rather than a library
default.
