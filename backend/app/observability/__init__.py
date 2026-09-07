"""Observability: a trace per /ask call (one span per pipeline stage),
external AI-SRE-agent events, and eval-run history — all backed by one
SQLite file so the frontend's observability and evals dashboards have
something durable to poll instead of an in-memory buffer that resets on
every deploy.
"""
