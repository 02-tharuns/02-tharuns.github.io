---
id: anpr
section: projects
title: Automatic Number Plate Recognition
type: project
date: 2024-03
domain: automotive
---

## Automatic Number Plate Recognition overview
A perception pipeline and robustness testing project for automatic number plate recognition, completed March 2024. Stack: YOLOv5, PyTorch, OpenCV, Tesseract, Albumentations, Docker, AWS EC2.

## ANPR dataset and robustness testing
Curated more than 12,000 annotated images from the OpenALPR Benchmark and Kaggle. Generated perturbed variants through rotation, brightness and contrast shifts, and synthetic occlusion, to test detection robustness under degraded imaging conditions.

## ANPR detection and OCR
Fine-tuned YOLOv5 for plate detection, reaching 95 percent mAP. Assembled an OCR stage from OpenCV preprocessing, a Keras convolutional character segmenter with pytesseract, and regular-expression correction.

## ANPR deployment and results
Containerized detection and OCR in Docker and deployed a Flask service on AWS EC2 through a CI/CD pipeline. Sustained inference under 50 milliseconds per image at 89 percent end-to-end accuracy, cutting manual logging effort by 85 percent.
