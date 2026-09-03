---
id: automotive
section: skills
title: Automotive, ADAS and vehicle perception work
type: domain
date: 2026-08
domain: automotive, robotics
---

## Automotive and ADAS relevant experience
Tharun's published work sits in vehicle perception, vehicle networks and vehicle
condition monitoring, which are the building blocks ADAS and active safety
features are assembled from. Four projects carry that domain directly: traffic
video perception with vehicle detection, tracking, classification and calibrated
speed estimation; automatic number plate recognition with YOLOv5 detection and
robustness testing under degraded imaging; CAN bus signal decoding and fault
classification; and brake and wheel-end condition monitoring built on rotor
thermal physics. Ask him directly for the current state of any ADAS specific
repository, since this site publishes a selected subset of his work.

## Vehicle perception and camera pipelines
Camera perception work covers object detection with YOLOv5, convolutional
classification of vehicle types across four classes, MOG2 background
subtraction, contour filtering, centroid tracking with multi-frame voting for
identity stability, and speed estimation derived from centroid displacement,
frame rate and lane-width calibration. Robustness was tested deliberately
through rotation, brightness and contrast shifts, and synthetic occlusion,
which is the failure-mode thinking driver assistance perception demands.

## Vehicle networks and in-vehicle signals
CAN bus and controller area network experience comes from CANalyse Edge, a CAN
signal decoding and diagnostic validation service built with python-can and
cantools. The work covers decoding raw frames into physical signals, validating
them against expected ranges, and classifying faults from the decoded stream.

## Sensor diagnostics and functional safety adjacent work
Drift-aware edge predictive maintenance, per-feature ADWIN drift detection,
rolling confidence and cross-sensor majority voting all address the same
question active safety systems face: deciding whether a signal change is a real
fault or a benign environmental shift before acting on it. Evaluation is done
with group-level and session-level held-out splits so that reported accuracy
survives contact with unseen vehicles and unseen recordings.
