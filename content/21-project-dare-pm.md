---
id: darepm
section: projects
title: DARE-PM
type: project
date: 2026-04
repo: https://github.com/02-tharuns/dare-pm
domain: automotive, industrial
---

## DARE-PM overview
DARE-PM is drift-aware edge predictive maintenance with out-of-distribution monitoring, completed April 2026. Stack: Python, scikit-learn, One-Class SVM, ADWIN, MQTT, Docker, InfluxDB, Grafana. Built as coursework for CIS 489 Edge Computing at the University of Michigan-Dearborn.

## DARE-PM feature extraction
Constructed an edge predictive-maintenance system extracting 14 time-domain and frequency-domain features every 0.1 seconds from vibration and acoustic streams, on-device.

## DARE-PM drift detection
Applied One-Class SVM novelty detection, an out-of-distribution detector fitted on nominal data alone, combined with ADWIN concept-drift diagnosis. The ADWIN stage separates true distribution shift from benign environmental variation, which prevents needless retraining.

## DARE-PM results
Cut false model adaptations from 49.87 percent to under 1 percent while sustaining F1 up to 0.80. That false-alarm rate is the characteristic failure mode of naive drift detectors. Reached 88.4 percent data reduction and 3.8 millisecond inference latency, validated across 48 controlled experiments.

## DARE-PM deployment
Deployed containerized Docker and MQTT services with continuous performance monitoring through InfluxDB and Grafana.

## DARE-PM buzz squeak and rattle reframe
Reframed under faculty mentorship toward vehicle buzz, squeak and rattle detection. The extension replaces single-detector drift with a multi-signal arbitration layer: per-feature ADWIN, rolling confidence, and cross-sensor majority voting. The reason is that ADWIN alone cannot distinguish a genuine fault from a benign environmental shift, so a second signal is needed to arbitrate before anything reaches the controller.
