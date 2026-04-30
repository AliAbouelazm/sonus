import json
import logging
from typing import Any, Optional

from backend.app.agent.llm_client import LLMClient
from backend.app.agent.prompts import build_system_prompt
from backend.app.agent.tools import TOOL_DEFINITIONS, ToolExecutor

logger = logging.getLogger(__name__)

MAX_TOOL_ROUNDS = 10


class Agent:
    """Agentic smart home assistant with tool-calling loop."""

    def __init__(self, tool_executor: ToolExecutor) -> None:
        self.llm = LLMClient()
        self.tool_executor = tool_executor
        self.conversation_history: list[dict[str, Any]] = []
        self.mode: str = "demo"

    async def process_message(
        self,
        user_message: str,
        on_tool_call: Optional[Any] = None,
    ) -> str:
        self.conversation_history.append({"role": "user", "content": user_message})

        system_prompt = await self._build_context_prompt(user_message)
        messages = [{"role": "system", "content": system_prompt}] + self._trimmed_history()

        for _round in range(MAX_TOOL_ROUNDS):
            response = await self.llm.chat_completion(messages, tools=TOOL_DEFINITIONS)

            tool_calls = response.get("tool_calls")
            if not tool_calls:
                content = response.get("content", "")
                self.conversation_history.append({"role": "assistant", "content": content})
                return content

            assistant_msg: dict[str, Any] = {
                "role": "assistant",
                "content": response.get("content") or "",
                "tool_calls": tool_calls,
            }
            messages.append(assistant_msg)

            for tc in tool_calls:
                fn = tc["function"]
                tool_name = fn["name"]
                try:
                    arguments = json.loads(fn["arguments"]) if isinstance(fn["arguments"], str) else fn["arguments"]
                except json.JSONDecodeError:
                    arguments = {}

                if on_tool_call:
                    await on_tool_call(tool_name, arguments)

                result = await self.tool_executor.execute(tool_name, arguments)
                messages.append({
                    "role": "tool",
                    "tool_call_id": tc["id"],
                    "content": result,
                })

        final = await self.llm.chat_completion(messages)
        content = final.get("content", "I completed the actions.")
        self.conversation_history.append({"role": "assistant", "content": content})
        return content

    async def _build_context_prompt(self, user_message: str) -> str:
        weather_summary = "Not available"
        events_summary = "No upcoming events"
        memories_text = "No stored preferences yet"

        try:
            weather_data = await self.tool_executor.weather.get_current()
            if isinstance(weather_data, dict) and "error" not in weather_data:
                weather_summary = (
                    f"{weather_data.get('description', 'N/A')}, "
                    f"{weather_data.get('temp', 'N/A')}°F, "
                    f"feels like {weather_data.get('feels_like', 'N/A')}°F"
                )
        except Exception:
            logger.debug("Could not fetch weather for context")

        try:
            events = await self.tool_executor.calendar.get_events(days_ahead=1)
            if isinstance(events, list) and events:
                event_strs = [f"- {e.get('title', 'Event')} at {e.get('start', '?')}" for e in events]
                events_summary = "\n".join(event_strs)
            elif isinstance(events, dict) and "error" in events:
                events_summary = "Calendar not configured"
        except Exception:
            logger.debug("Could not fetch calendar for context")

        try:
            keywords = user_message.lower().split()
            relevant_words = [w for w in keywords if len(w) > 3]
            query = " ".join(relevant_words[:5]) if relevant_words else user_message
            memories = await self.tool_executor.memory_store.recall_memories(query, limit=5)
            if memories:
                memories_text = "\n".join(f"- {m['content']}" for m in memories)
        except Exception:
            logger.debug("Could not fetch memories for context")

        device_states = self.tool_executor.device_manager.get_all_states()
        device_str = json.dumps(device_states, indent=2)

        gcal_write = "Not configured"
        try:
            cal = self.tool_executor.calendar
            if cal._oauth_configured():
                gcal_write = "Connected" if cal.is_authenticated() else "Not connected — user should visit /api/gcal/login"
        except Exception:
            pass

        integrations_text = "None"
        try:
            configs = await self.tool_executor.memory_store.get_integration_configs()
            if configs:
                lines = [f"- {c.get('display_name') or c['integration_id']} ({c['integration_id']})" for c in configs]
                integrations_text = "\n".join(lines)
        except Exception:
            pass

        return build_system_prompt(
            weather_summary=weather_summary,
            events_summary=events_summary,
            device_states=device_str,
            relevant_memories=memories_text,
            gcal_write_status=gcal_write,
            connected_integrations=integrations_text,
            mode=self.mode,
        )

    def _trimmed_history(self, max_messages: int = 30) -> list[dict[str, Any]]:
        """Keep conversation history manageable by trimming old messages."""
        history = self.conversation_history[-max_messages:]
        return [{"role": m["role"], "content": m["content"]} for m in history]

    def clear_history(self) -> None:
        self.conversation_history.clear()
