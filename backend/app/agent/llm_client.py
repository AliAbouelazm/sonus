import json
import logging
from typing import Any, Optional

import httpx

from backend.app.config import settings

logger = logging.getLogger(__name__)


INPUT_COST_PER_TOKEN = 2.50 / 1_000_000
OUTPUT_COST_PER_TOKEN = 10.00 / 1_000_000


class TokenTracker:
    """Tracks daily token usage and estimated cost from LLM API responses."""

    def __init__(self) -> None:
        self.prompt_tokens: int = 0
        self.completion_tokens: int = 0
        self.total_tokens: int = 0
        self.request_count: int = 0
        self._reset_date: str = ""
        self._check_reset()

    def _check_reset(self) -> None:
        from datetime import date
        today = date.today().isoformat()
        if today != self._reset_date:
            self.prompt_tokens = 0
            self.completion_tokens = 0
            self.total_tokens = 0
            self.request_count = 0
            self._reset_date = today

    def record(self, usage: dict[str, Any]) -> None:
        self._check_reset()
        self.prompt_tokens += usage.get("prompt_tokens", 0)
        self.completion_tokens += usage.get("completion_tokens", 0)
        self.total_tokens += usage.get("total_tokens", 0)
        self.request_count += 1

    @property
    def estimated_cost(self) -> float:
        return (self.prompt_tokens * INPUT_COST_PER_TOKEN
                + self.completion_tokens * OUTPUT_COST_PER_TOKEN)

    def get_stats(self) -> dict[str, Any]:
        self._check_reset()
        budget = settings.daily_token_budget
        return {
            "date": self._reset_date,
            "prompt_tokens": self.prompt_tokens,
            "completion_tokens": self.completion_tokens,
            "total_tokens": self.total_tokens,
            "budget": budget if budget > 0 else None,
            "cost": round(self.estimated_cost, 4),
            "requests": self.request_count,
        }


class LLMClient:
    """OpenAI-compatible API client with tool-calling support."""

    def __init__(self) -> None:
        self.api_key = settings.ai_api_key
        self.base_url = settings.ai_base_url.rstrip("/")
        self.model = settings.ai_model
        self._client: Optional[httpx.AsyncClient] = None
        self.token_tracker = TokenTracker()

        self._completions_url = f"{self.base_url}/chat/completions"

    async def _get_client(self) -> httpx.AsyncClient:
        if self._client is None or self._client.is_closed:
            self._client = httpx.AsyncClient(
                headers={
                    "Authorization": f"Bearer {self.api_key}",
                    "Content-Type": "application/json",
                },
                timeout=httpx.Timeout(60.0, connect=10.0),
            )
        return self._client

    async def chat_completion(
        self,
        messages: list[dict[str, Any]],
        tools: Optional[list[dict[str, Any]]] = None,
        temperature: float = 0.7,
    ) -> dict[str, Any]:
        client = await self._get_client()

        payload: dict[str, Any] = {
            "model": self.model,
            "messages": messages,
            "temperature": temperature,
            "stream": False,
        }

        if tools:
            payload["tools"] = tools
            payload["tool_choice"] = "auto"

        try:
            response = await client.post(self._completions_url, json=payload)
            response.raise_for_status()
            data = response.json()
            if "usage" in data:
                self.token_tracker.record(data["usage"])
            return data["choices"][0]["message"]
        except httpx.HTTPStatusError as e:
            logger.error("LLM API HTTP error %s: %s", e.response.status_code, e.response.text)
            if tools and e.response.status_code in (400, 405, 422):
                logger.info("Retrying without native tool calling – using JSON prompt fallback")
                return await self._fallback_completion(messages, tools, temperature)
            raise
        except Exception:
            logger.exception("LLM API request failed")
            raise

    async def _fallback_completion(
        self,
        messages: list[dict[str, Any]],
        tools: list[dict[str, Any]],
        temperature: float,
    ) -> dict[str, Any]:
        """When the model doesn't support native tool calling, inject tool
        schemas into the system prompt and parse structured JSON from the
        response."""
        tool_descriptions = self._build_tool_description_text(tools)

        fallback_instruction = (
            "\n\n--- TOOL CALLING INSTRUCTIONS ---\n"
            "You have access to tools. To call one or more tools, respond with a JSON block:\n"
            '```json\n{"tool_calls": [{"name": "<tool_name>", "arguments": {<args>}}]}\n```\n'
            "If you don't need any tool, just respond normally.\n\n"
            f"Available tools:\n{tool_descriptions}\n"
            "--- END TOOL CALLING INSTRUCTIONS ---"
        )

        augmented_messages = []
        for msg in messages:
            if msg["role"] == "system":
                augmented_messages.append(
                    {"role": "system", "content": msg["content"] + fallback_instruction}
                )
            else:
                augmented_messages.append(msg)

        client = await self._get_client()
        payload = {
            "model": self.model,
            "messages": augmented_messages,
            "temperature": temperature,
            "stream": False,
        }

        response = await client.post(self._completions_url, json=payload)
        response.raise_for_status()
        data = response.json()
        if "usage" in data:
            self.token_tracker.record(data["usage"])
        raw_message = data["choices"][0]["message"]

        return self._parse_fallback_tool_calls(raw_message)

    def _parse_fallback_tool_calls(self, message: dict[str, Any]) -> dict[str, Any]:
        content = message.get("content", "")
        if not content:
            return message

        json_block = self._extract_json_block(content)
        if json_block and "tool_calls" in json_block:
            tool_calls = []
            for i, tc in enumerate(json_block["tool_calls"]):
                tool_calls.append({
                    "id": f"fallback_{i}",
                    "type": "function",
                    "function": {
                        "name": tc["name"],
                        "arguments": json.dumps(tc.get("arguments", {})),
                    },
                })
            preamble = content.split("```json")[0].strip()
            return {
                "role": "assistant",
                "content": preamble if preamble else None,
                "tool_calls": tool_calls,
            }

        return message

    @staticmethod
    def _extract_json_block(text: str) -> Optional[dict]:
        try:
            start = text.index("```json")
            end = text.index("```", start + 7)
            raw = text[start + 7 : end].strip()
            return json.loads(raw)
        except (ValueError, json.JSONDecodeError):
            pass
        try:
            start = text.index("{")
            end = text.rindex("}") + 1
            return json.loads(text[start:end])
        except (ValueError, json.JSONDecodeError):
            return None

    @staticmethod
    def _build_tool_description_text(tools: list[dict[str, Any]]) -> str:
        lines = []
        for tool in tools:
            fn = tool["function"]
            lines.append(f"- {fn['name']}: {fn['description']}")
            params = fn.get("parameters", {}).get("properties", {})
            if params:
                for pname, pinfo in params.items():
                    lines.append(f"    {pname} ({pinfo.get('type', 'any')}): {pinfo.get('description', '')}")
        return "\n".join(lines)

    async def close(self) -> None:
        if self._client and not self._client.is_closed:
            await self._client.aclose()
