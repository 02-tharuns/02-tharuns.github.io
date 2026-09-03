---
id: supplychain
section: projects
title: Supply Chain Risk Data Pipeline and Predictive Analytics
type: project
date: 2026-07
domain: data-science, industrial
---

## Supply chain risk pipeline overview
An end-to-end predictive pipeline over more than 180,000 supply-chain orders across 53 attributes, built May to July 2026. Covers data cleaning, validation, preprocessing and model development. Stack: Python, pandas, NumPy, scikit-learn.

## Supply chain feature engineering
Engineered shipment, temporal, operational and categorical features using leakage-safe preprocessing for late-delivery prediction. Reduced one-hot encoded dimensionality from over 64,000 features to 339 through high-cardinality feature optimisation and data-modelling decisions.

## Supply chain evaluation and threshold tuning
Evaluated precision, recall, F1 and ROC-AUC. Raised late-risk recall from 57.5 percent to 78.8 percent through decision-threshold tuning, settling on a threshold of 0.40 at a precision of 66.1 percent using logistic regression. The trade is deliberate: for a late-delivery warning, a missed late shipment costs more than a false alarm someone can dismiss.
