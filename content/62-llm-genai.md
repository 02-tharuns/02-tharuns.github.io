---
id: llm
section: projects
title: LLM, generative AI and retrieval work
type: project
date: 2026-08
domain: ai
---

## Chappie, the retrieval and generation system running on this site
Chappie is a hybrid retrieval-augmented generation system Tharun built over his own CV, projects, education and skills. The frontend is React, TypeScript and Vite deployed on Vercel; the backend is a FastAPI service deployed on Render. Retrieval combines BM25 lexical search with Qdrant Cloud dense vector search, fused with reciprocal rank fusion and reranked with a cross-encoder before an answer is generated.

<!-- display:
I built Chappie as a hybrid retrieval-augmented generation system over my own CV, projects, education and skills. The frontend is React, TypeScript and Vite deployed on Vercel; the backend is a FastAPI service deployed on Render. Retrieval combines BM25 lexical search with Qdrant Cloud dense vector search, fused with reciprocal rank fusion and reranked with a cross-encoder before an answer is generated.
-->

## How Chappie is guarded
The guardrail gates run as a sequence ported gate-for-gate from an earlier browser-only build: input hygiene, prompt-injection screening, out-of-distribution scope detection, an evidence floor applied after retrieval, and citation integrity checked after generation. The evidence floor blocks generation entirely when nothing clears a calibrated confidence score, and citation validation runs on both the server and the client, rejecting any answer that cites a passage it did not actually retrieve.

<!-- display:
The guardrail gates run as a sequence I ported gate-for-gate from an earlier browser-only build: input hygiene, prompt-injection screening, out-of-distribution scope detection, an evidence floor applied after retrieval, and citation integrity checked after generation. The evidence floor blocks generation entirely when nothing clears a calibrated confidence score, and citation validation runs on both the server and the client, rejecting any answer that cites a passage it didn't actually retrieve.
-->

## How Chappie is evaluated
A 97-case evaluation suite across seven groups (golden, adjacent, red-team, deflection, role, retention and completeness) runs against the live backend on every push, and publishes each run, pass/fail counts and every individual case, to the Evals dashboard on this site. It reports attack success rate and false refusal rate, the second being the measure most projects skip. Both currently sit at zero.

<!-- display:
I run a 97-case evaluation suite across seven groups (golden, adjacent, red-team, deflection, role, retention and completeness) against the live backend on every push, and publish each run, pass/fail counts and every individual case, to the Evals dashboard on this site. It reports attack success rate and false refusal rate, the second being the measure most projects skip. Both currently sit at zero.
-->

## The generative answering path and LLM API integration
The FastAPI backend, deployed on Render, holds the Groq API key server-side. It receives a question, runs hybrid retrieval and reranking, then streams a generated answer from a Groq-hosted model back to the browser over server-sent events. The answer may cite only passages that were actually retrieved. Citation validation runs on both the server and the client, so a hallucinated source is rejected rather than displayed. Every stage, gates, retrieval, fusion, reranking and generation, is recorded as a trace span and rendered live on the site's Observability page.

<!-- display:
The FastAPI backend I deployed on Render holds the Groq API key server-side. It receives a question, runs hybrid retrieval and reranking, then streams a generated answer from a Groq-hosted model back to the browser over server-sent events. The answer may cite only passages that were actually retrieved. Citation validation runs on both the server and the client, so a hallucinated source is rejected rather than displayed. Every stage, gates, retrieval, fusion, reranking and generation, is recorded as a trace span and rendered live on the site's Observability page.
-->

## Ingestion pipeline behind the retrieval system
An offline pipeline chunks the Markdown source documents on their headings, tokenises and stems the text, and builds the retrieval index: a shared BM25 vocabulary for lexical scoring plus Qdrant Cloud embeddings for dense search. The same chunking logic is mirrored across the backend, the frontend build step and an earlier browser-only build so all three stay in sync. Continuous integration fails the build if a generated index has drifted out of date with the source documents.

<!-- display:
I built an offline pipeline that chunks the Markdown source documents on their headings, tokenises and stems the text, and builds the retrieval index: a shared BM25 vocabulary for lexical scoring plus Qdrant Cloud embeddings for dense search. I mirror the same chunking logic across the backend, the frontend build step and an earlier browser-only build so all three stay in sync. Continuous integration fails the build if a generated index has drifted out of date with the source documents.
-->

## Generative AI and LLM tooling
Tharun's AI framework skills are Hugging Face Transformers, LangChain and LlamaIndex, and he lists OpenAI and Anthropic among the LLM tooling he works with. He is working through a self-directed generative AI and LLM track covering Hugging Face, LangChain and retrieval-augmented generation.

<!-- display:
My AI framework skills are Hugging Face Transformers, LangChain and LlamaIndex, and I count OpenAI and Anthropic among the LLM tooling I work with. I'm working through a self-directed generative AI and LLM track covering Hugging Face, LangChain and retrieval-augmented generation.
-->
