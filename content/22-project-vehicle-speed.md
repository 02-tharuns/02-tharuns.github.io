---
id: vehicle
section: projects
title: Vehicle Type and Speed Pattern Recognition
type: project
date: 2025-04
repo: https://github.com/02-tharuns/Vehicle_Type_and_Speed_Pattern-Recognition
domain: automotive
---

## Vehicle Type and Speed Pattern Recognition overview
A traffic perception pipeline for vehicle detection, tracking, four-class classification, and calibrated speed estimation, completed April 2025. Stack: Python, OpenCV, TensorFlow and Keras, convolutional neural networks.

## Vehicle recognition training and split
Trained convolutional neural networks on 17,760 labelled vehicle crops under a group-level split by video, so that no same-vehicle frames were shared across training and validation. Reached approximately 85 percent binary accuracy and above 79 percent multi-class validation accuracy.

## Vehicle tracking and speed estimation
Implemented MOG2 background subtraction, contour filtering, centroid tracking, and multi-frame voting to stabilize vehicle identities. Estimated speed from centroid displacement, frame rate, and lane-width calibration.
