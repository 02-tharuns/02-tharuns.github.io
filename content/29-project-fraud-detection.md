---
id: fraud
section: projects
title: Credit Card Fraud Prediction
type: project
date: 2023-10
domain: data-science
---

## Credit card fraud detection overview
A fraud classification project over 284,000 transactions with a 0.17 percent fraud rate, built August to October 2023. Earlier applied machine learning work, predating the sensor and edge focus.

## Fraud detection modelling
Optimised XGBoost with Bayesian hyperparameter tuning, reaching 97 percent precision at 89 percent recall. Applied SMOTE balancing to lift minority-class recall by 20 percent without degrading precision. Benchmarked against logistic regression, Random Forest and a multilayer perceptron, which validated XGBoost as the strongest model on this data.

## Fraud detection deployment and impact
Deployed the model as a Dockerised Flask API serving predictions under 200 milliseconds in a test environment. The associated 1.2 million dollar annual loss figure is a simulated estimate from the dataset, not a measured business outcome.
