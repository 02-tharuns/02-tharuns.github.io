---
id: brake
section: projects
title: Smart Brake and Wheel-End Condition Monitor
type: project
date: 2026-08
status: In progress
repo: https://github.com/02-tharuns/Smart-Brake-and-Tire-Condition-Monitor
domain: automotive
---

## Smart Brake and Wheel-End Condition Monitor overview
A physics-first brake and wheel-end diagnostic system, currently in progress, built with a collaborator. Stack: Python, NumPy, scikit-learn, pytest, ruff, GitHub Actions. Tharun owns the thermal simulation, drag-torque injection and torque-inversion work.

## Brake rotor thermal simulation
Modelled rotor thermal behaviour with a lumped-capacitance simulator incorporating speed-dependent convection and radiation. Injected residual caliper drag torque across four severity levels, over a dual-wheel front-left and front-right configuration.

## Brake torque inversion from cooling curves
Devised a Newtonian cooling-curve feature extractor that inverts drag torque from the cooling asymptote rather than classifying a black-box signature. Recovers torque within roughly 5 percent of ground truth on severe-drag cases. Physical inversion was chosen over classification deliberately: an interpretable torque estimate carries a diagnostic story to a service engineer that a classifier confidence score cannot.

## Brake project testing
Guarded by an 18-test suite gated in continuous integration through ruff, pytest and coverage reporting.
