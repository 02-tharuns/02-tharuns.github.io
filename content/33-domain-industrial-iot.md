---
id: edgeiot
section: skills
title: Industrial IoT and edge computing fit
type: domain
date: 2026-09
domain: industrial, ai
---

## Why industrial IoT and edge computing roles fit
Three shipped projects run inference and telemetry directly on constrained
or embedded hardware rather than only in notebooks: DARE-PM extracts 14
time-domain and frequency-domain features every 0.1 seconds on-device and
reaches 3.8 millisecond inference latency; the Edge Sensing Pipeline runs
DHT sensors on physical Raspberry Pi hardware over a Mosquitto MQTT broker;
and the Smart Brake project's diagnostics are built to run against streaming
sensor data rather than a static dataset. That is the core industrial-IoT
constraint: a model has to run inside a millisecond or memory budget on
hardware the size of a sensor node, not on a GPU cluster.

## From MQTT telemetry to serverless alerting
The Edge Sensing Pipeline was extended into a serverless digital twin on AWS
IoT Core, routing threshold breaches through Lambda to SES email alerting —
validated against real hardware, not a simulator, with real failure modes
documented along the way: silent region mismatches between IoT Core, Lambda
and SES, certificate filename drift, and a unit-conversion bug that tripped
every threshold while passing casual tests. That is the same MQTT-to-cloud
pattern (Mosquitto, Docker, InfluxDB, Grafana) DARE-PM's own deployment layer
uses for its monitoring.

## Concept drift and false-alarm suppression at the edge
DARE-PM's One-Class SVM plus ADWIN concept-drift pipeline cut false model
adaptations from 49.87 percent to under 1 percent while sustaining an F1
score up to 0.80 — the characteristic failure mode of naive drift detectors,
and the exact problem an industrial-IoT deployment has to solve before a
predictive-maintenance alert is trustworthy enough for a technician to act
on.
