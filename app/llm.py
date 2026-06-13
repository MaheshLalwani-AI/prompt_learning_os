from __future__ import annotations

import json
import os
from dataclasses import dataclass
from typing import AsyncIterator

import httpx
from dotenv import load_dotenv

load_dotenv()


@dataclass
class LLMConfig:
    provider_name: str
    base_url: str
    api_key: str
    model: str
    temperature: float = 0.2
    input_cost_per_1m_tokens: float = 0.0
    output_cost_per_1m_tokens: float = 0.0
    routing_reason: str = "Configured default model"

    @property
    def enabled(self) -> bool:
        return bool(self.base_url and self.api_key and self.model)


def get_llm_config() -> LLMConfig:
    return LLMConfig(
        provider_name=os.getenv("LLM_PROVIDER_NAME", "OpenAI-compatible"),
        base_url=os.getenv("LLM_BASE_URL", "").rstrip("/"),
        api_key=os.getenv("LLM_API_KEY", ""),
        model=os.getenv("LLM_MODEL", ""),
        temperature=float(os.getenv("LLM_TEMPERATURE", "0.2")),
        input_cost_per_1m_tokens=float(os.getenv("LLM_INPUT_COST_PER_1M_TOKENS", "0")),
        output_cost_per_1m_tokens=float(os.getenv("LLM_OUTPUT_COST_PER_1M_TOKENS", "0")),
        routing_reason=os.getenv("LLM_ROUTING_REASON", "Configured default model"),
    )


def estimate_tokens(text: str) -> int:
    if not text:
        return 0
    return max(1, round(len(text) / 4))


def estimate_cost_usd(
    input_tokens: int,
    output_tokens: int,
    config: LLMConfig,
) -> float:
    input_cost = (input_tokens / 1_000_000) * config.input_cost_per_1m_tokens
    output_cost = (output_tokens / 1_000_000) * config.output_cost_per_1m_tokens
    return round(input_cost + output_cost, 8)


async def stream_chat_completion(
    prompt: str,
    system_prompt: str,
    config: LLMConfig,
) -> AsyncIterator[str]:
    if not config.enabled:
        yield "API is not configured. Copy the optimized prompt into ChatGPT, Claude, or DeepSeek manually."
        return

    url = f"{config.base_url}/chat/completions"
    headers = {
        "Authorization": f"Bearer {config.api_key}",
        "Content-Type": "application/json",
    }

    payload = {
        "model": config.model,
        "temperature": config.temperature,
        "stream": True,
        "messages": [
            {"role": "system", "content": system_prompt},
            {"role": "user", "content": prompt},
        ],
    }

    async with httpx.AsyncClient(timeout=None) as client:
        async with client.stream("POST", url, headers=headers, json=payload) as response:
            response.raise_for_status()

            async for line in response.aiter_lines():
                if not line or not line.startswith("data: "):
                    continue

                data = line.removeprefix("data: ").strip()
                if data == "[DONE]":
                    break

                try:
                    chunk = json.loads(data)
                except json.JSONDecodeError:
                    continue

                choices = chunk.get("choices") or []
                if not choices:
                    continue

                delta = choices[0].get("delta") or {}
                text = delta.get("content")
                if text:
                    yield text
