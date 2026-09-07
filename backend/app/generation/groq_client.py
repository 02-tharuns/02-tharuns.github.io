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


class GroqClient:
    def __init__(self, api_key: str, url: str, model: str):
        self.api_key = api_key
        self.url = url
        self.model = model

    async def complete(self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 500) -> str:
        payload = {"model": self.model, "temperature": temperature, "max_tokens": max_tokens, "messages": messages}
        async with httpx.AsyncClient(timeout=45) as client:
            r = await client.post(self.url, headers=self._headers(), json=payload)
        if r.status_code != 200:
            raise GroqError(f"upstream model error: {r.status_code}")
        return r.json()["choices"][0]["message"]["content"]

    async def stream(self, messages: list[dict], temperature: float = 0.2, max_tokens: int = 500) -> AsyncIterator[str]:
        payload = {
            "model": self.model, "temperature": temperature, "max_tokens": max_tokens,
            "stream": True, "messages": messages,
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
                        delta = json.loads(body)["choices"][0]["delta"]
                    except (json.JSONDecodeError, KeyError, IndexError):
                        continue
                    piece = delta.get("content")
                    if piece:
                        yield piece

    def _headers(self) -> dict:
        return {"Authorization": f"Bearer {self.api_key}"}


class GroqError(RuntimeError):
    pass
