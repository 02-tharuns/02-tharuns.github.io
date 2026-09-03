---
id: llm
section: projects
title: LLM, generative AI and retrieval work
type: project
date: 2026-08
domain: ai
---

## Chappie, the retrieval system running on this site
Chappie is a retrieval-augmented generation system Tharun built over his own CV, projects, education and skills. It runs entirely in the visitor's browser on GitHub Pages, with no server, no API key and no cold start. Retrieval is Okapi BM25 over a prebuilt index, with query expansion and same-document damping, and a full question is answered in roughly five milliseconds.

## How Chappie is guarded
Six gates run in order of cost: input hygiene, prompt-injection screening, out-of-distribution scope detection, an evidence floor applied after retrieval, and citation integrity checked on the way out. Answering is extractive, meaning sentences are quoted from the indexed source rather than paraphrased by a generative model, which makes a fabricated claim structurally impossible rather than merely unlikely.

## How Chappie is evaluated
A 69-case evaluation suite across four groups runs in headless Chromium against the real page on every push, and blocks the deployment on regression. It reports attack success rate and false refusal rate, the second being the measure most projects skip. Both currently sit at zero.

## The generative answering path and LLM API integration
The generative path is implemented and ships disabled by default. A FastAPI service deployable to Azure Container Apps holds the model key server-side, receives the question together with the already-retrieved passages, and returns a generated answer that may cite only passages that were actually retrieved. Citation validation runs on both the server and the client, so a hallucinated source is rejected rather than displayed.

## Ingestion pipeline behind the retrieval system
An offline Python pipeline chunks Markdown source documents on their headings, tokenises and stems them with a stemmer mirrored exactly in the browser, computes BM25 term statistics, and emits a single static index file. Continuous integration fails the build if the committed index has drifted out of date with the source documents.

## Generative AI and LLM tooling
Tharun's AI framework skills are Hugging Face Transformers, LangChain and LlamaIndex, and he lists OpenAI and Anthropic among the LLM tooling he works with. He is working through a self-directed generative AI and LLM track covering Hugging Face, LangChain and retrieval-augmented generation.
