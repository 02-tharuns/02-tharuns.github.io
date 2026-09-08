"""Groq chat-completion client — non-streaming and SSE-streaming, ported
from the legacy backend/app.py. A thin httpx wrapper rather than an SDK or
LiteLLM: this service talks to exactly one provider, and the existing
rate-limit/gap-notification/citation-validation machinery around it already
does the job LiteLLM's Router would (see ARCHITECTURE.md's build-plan doc
for why a gateway library wasn't adopted here — the fallback/cost-tracking
value it adds only pays for itself with more than one provider in play)."""

from __future__ import annotations

import json
from typing import AsyncIterator

import httpx

# USD per 1M tokens, (input, output) — Token Cost Tracking's only "instrumentation"
# is arithmetic on the `usage` block Groq's OpenAI-compatible API already returns,
# so a hardcoded table beats a live pricing call: no network dependency, no new
# failure mode, and it costs nothing to keep in sync (one line per model actually
# used). Source: console.groq.com/docs/models + groq.com/pricing, checked 2026-09-07.
PRICING_PER_MILLION_USD: dict[str, tuple[float, float]] = {
    "openai/gpt-oss-20b": (0.075, 0.30),
}


def estimate_cost_usd(model: str, usage: dict | None) -> float | None:
    """None (never 0.0) when the model isn't in the table or usage is missing —
    the dashboard renders that as "n/a" rather than a misleading free answer."""
    if not usage:
        return None
    pricing = PRICING_PER_MILLION_USD.get(model)
    if not pricing:
        return None
    in_price, out_price = pricing
    prompt_tokens = usage.get("prompt_tokens") or 0
    completion_tokens = usage.get("completion_tokens") or 0
    return (prompt_tokens / 1_000_000) * in_price + (completion_tokens / 1_000_000) * out_price


class GroqClient:
    def __init__(self, api_key: str, url: str, model: str):
        self.api_key = api_key
        self.url = url
        self.model = model

    async def complete(
        self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 500
    ) -> tuple[str, dict | None]:
        """Returns (answer_text, usage) — usage is Groq's raw
        {prompt_tokens, completion_tokens, total_tokens} dict, or None if the
        response didn't include one, so callers can record it without this
        client knowing anything about tracing or pricing."""
        payload = {"model": self.model, "temperature": temperature, "max_tokens": max_tokens, "messages": messages}
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post(self.url, headers=self._headers(), json=payload)
        if r.status_code != 200:
            raise GroqError(f"upstream model error: {r.status_code}")
        data = r.json()
        return data["choices"][0]["message"]["content"], data.get("usage")

    async def stream(
        self,
        messages: list[dict],
        temperature: float = 0.2,
        max_tokens: int = 500,
        usage_sink: dict | None = None,
    ) -> AsyncIterator[str]:
        """Yields content pieces exactly as before. If `usage_sink` is given,
        it's mutated in place with the final usage dict once the stream's
        last frame (a usage-only frame with empty `choices`, per
        stream_options.include_usage) arrives — the caller reads it after the
        `async for` loop completes, no return-type change needed here."""
        payload = {
            "model": self.model, "temperature": temperature, "max_tokens": max_tokens,
            "stream": True, "messages": messages, "stream_options": {"include_usage": True},
        }
        async with httpx.AsyncClient(timeout=60) as client:
            async with client.stream("POST", self.url, headers=self._headers(), json=payload) as upstream:
                if upstream.status_code != 200:
                    raise GroqError(f"upstream model error: {upstream.status_code}")
                async for line in upstream.aiter_lines():
                    if not line.startswith("data: "):
                        continue
                    body = line[6:].strip()
                    if body == "[DONE]":
                        break
                    try:
                        parsed = json.loads(body)
                    except json.JSONDecodeError:
                        continue
                    usage = parsed.get("usage")
                    if usage and usage_sink is not None:
                        usage_sink.update(usage)
                    choices = parsed.get("choices") or []
                    if not choices:
                        continue  # the trailing usage-only frame has no choices
                    piece = choices[0].get("delta", {}).get("content")
                    if piece:
                        yield piece

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}


class GroqError(RuntimeError):
    pass
