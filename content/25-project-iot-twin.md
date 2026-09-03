---
id: iottwin
section: projects
title: Edge Sensing Pipeline and Serverless Digital Twin
type: project
date: 2025-12
domain: industrial
---

## Edge sensing pipeline overview
An end-to-end telemetry chain running on physical Raspberry Pi hardware. DHT sensors publish over a Mosquitto MQTT broker to a Python subscriber, are persisted to storage, and are visualised for trend inspection.

## Serverless digital twin and alerting
Extended the pipeline into a serverless digital twin on AWS IoT Core, routing threshold breaches through Lambda to SES email alerting, running against real hardware rather than a simulator.

## Lessons from deploying on real hardware
Each layer was validated independently, sensor to broker to subscriber to storage to alert, before end-to-end testing, because going straight to integration doubles the time spent locating which link broke. Real failure modes encountered: silent region mismatches between IoT Core, Lambda and SES; certificate filename drift in authentication scripts; and a unit-conversion error that tripped every threshold while passing casual tests.
