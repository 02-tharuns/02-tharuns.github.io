---
id: canalyse
section: projects
title: CANalyse Edge
type: project
date: 2026-08
status: In progress
repo: https://github.com/02-tharuns/CANalyse-Edge
domain: automotive
---

## CANalyse Edge overview
CANalyse Edge is a CAN signal decoding and diagnostic validation service, currently in progress. Stack: Python, python-can, cantools, scikit-learn, FastAPI, pytest, GitHub Actions.

## CANalyse Edge decoding pipeline
Engineered a CAN and CAN-FD diagnostic pipeline decoding raw frames into named engineering signals through DBC mapping. Records timing, DLC, and signal-range checks as data-quality evidence on every validation run.

## CANalyse Edge model and evaluation
Derived rolling signal-window features feeding a Random Forest component-condition model. Held out 3 unseen recording sessions of 6, so neighbouring windows never leak across the evaluation split. This session-level holdout is the point: random splits on windowed sensor data leak, and the resulting accuracy is fiction.

## CANalyse Edge diagnostic API
Exposed results through a SOVD-inspired FastAPI service serving entity, component-health, fault, data, and operation resources, with a dashboard supporting issue triage and root-cause inspection.

## CANalyse Edge testing and datasets
Automated a pytest regression suite in continuous integration. Curated a public dataset registry covering ReCAN, ROAD, Scania Component X, and Q-Motion, under a validation protocol that reports simulator output as synthetic smoke tests rather than as real results.
