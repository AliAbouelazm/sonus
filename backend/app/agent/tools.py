import json
import logging
from typing import Any

logger = logging.getLogger(__name__)

TOOL_DEFINITIONS: list[dict[str, Any]] = [
    {
        "type": "function",
        "function": {
            "name": "get_calendar_events",
            "description": "Fetch upcoming events from Google Calendar.",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "Number of days ahead to look. Default 1.",
                        "default": 1,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_calendar_event",
            "description": (
                "Create a new event on Google Calendar. Requires OAuth (user must connect via /api/gcal/login). "
                "Use ISO 8601 format for date/times (e.g. '2026-03-10T14:00:00' for a timed event, '2026-03-10' for all-day)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Event title/summary.",
                    },
                    "start": {
                        "type": "string",
                        "description": "Start date/time in ISO 8601 (e.g. '2026-03-10T14:00:00' or '2026-03-10' for all-day).",
                    },
                    "end": {
                        "type": "string",
                        "description": "End date/time in ISO 8601. For all-day events, use the day after (exclusive end).",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional event description/notes.",
                    },
                    "location": {
                        "type": "string",
                        "description": "Optional event location.",
                    },
                },
                "required": ["title", "start", "end"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "update_calendar_event",
            "description": (
                "Update an existing Google Calendar event. Use search_calendar_events first to find the event_id. "
                "Only the fields you provide will be changed."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The Google Calendar event ID (get from search_calendar_events).",
                    },
                    "title": {
                        "type": "string",
                        "description": "New event title. Leave out to keep unchanged.",
                    },
                    "start": {
                        "type": "string",
                        "description": "New start date/time in ISO 8601. Leave out to keep unchanged.",
                    },
                    "end": {
                        "type": "string",
                        "description": "New end date/time in ISO 8601. Leave out to keep unchanged.",
                    },
                    "description": {
                        "type": "string",
                        "description": "New description. Leave out to keep unchanged.",
                    },
                    "location": {
                        "type": "string",
                        "description": "New location. Leave out to keep unchanged.",
                    },
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_calendar_event",
            "description": (
                "Delete an event from Google Calendar by its event_id. "
                "Use search_calendar_events first to find the event_id."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "event_id": {
                        "type": "string",
                        "description": "The Google Calendar event ID to delete.",
                    },
                },
                "required": ["event_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_calendar_events",
            "description": (
                "Search Google Calendar events by keyword. Returns events with their event_id, "
                "which you need for update_calendar_event and delete_calendar_event. "
                "Requires OAuth."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search term to find matching events.",
                    },
                    "days_ahead": {
                        "type": "integer",
                        "description": "How many days ahead to search. Default 30.",
                        "default": 30,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_canvas_assignments",
            "description": "Fetch upcoming assignments and exams from the Canvas LMS calendar (ICS feed).",
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ahead": {
                        "type": "integer",
                        "description": "Number of days ahead to look. Default 7.",
                        "default": 7,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_weather",
            "description": "Get current weather conditions and forecast for the configured city.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "control_device",
            "description": (
                "Control a smart home device. "
                "Device IDs come from the device_states in your context — always use the exact IDs listed there. "
                "Lock actions: lock, unlock. "
                "Bulb actions: turn_on, turn_off, set_brightness (value: 0-100), "
                "set_color_temp (value: warm/neutral/cool), "
                "set_color (value: color name like 'red', 'blue', 'purple', 'mint' or hex like '#ff5500'). "
                "Fan actions: turn_on, turn_off, set_speed (value: low/medium/high). "
                "AC actions: turn_on, turn_off, set_temp (value: 60-85°F), "
                "set_mode (value: cool/heat/fan/auto/dry), set_fan_speed (value: low/medium/high/auto)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "The exact device_id from device_states in your context (e.g. 'bulb.smart_bulb', 'bulb.smart_bulb_1234567890', 'lock.smart_lock').",
                    },
                    "action": {
                        "type": "string",
                        "description": "The action to perform on the device.",
                    },
                    "value": {
                        "description": "Optional value for the action (brightness level, color temp, color name/hex, speed, temperature, AC mode).",
                    },
                },
                "required": ["device_id", "action"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_device_states",
            "description": "Get the current state of all smart home devices.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "store_memory",
            "description": (
                "Store a user preference, fact, or note in long-term memory. "
                "Use this whenever the user expresses a preference, corrects you, or shares personal info."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "memory_type": {
                        "type": "string",
                        "description": "Type of memory: preference, fact, or note.",
                        "enum": ["preference", "fact", "note"],
                    },
                    "content": {
                        "type": "string",
                        "description": "The content to remember, e.g. 'User prefers fan on when studying'.",
                    },
                    "importance": {
                        "type": "number",
                        "description": "Importance from 0 to 1. Preferences that override defaults should be 0.8+.",
                        "default": 0.5,
                    },
                },
                "required": ["memory_type", "content"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "recall_memories",
            "description": "Search stored memories for relevant preferences, facts, or notes.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query to match against stored memories.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max number of results to return. Default 5.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_reminder",
            "description": "Create a timed reminder. Use natural language for the time.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Short title for the reminder.",
                    },
                    "when": {
                        "type": "string",
                        "description": "When to remind, e.g. 'in 30 minutes', 'tomorrow at 9am', 'next monday 2pm'.",
                    },
                    "description": {
                        "type": "string",
                        "description": "Optional longer description.",
                        "default": "",
                    },
                },
                "required": ["title", "when"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_reminders",
            "description": "List all reminders.",
            "parameters": {
                "type": "object",
                "properties": {
                    "include_completed": {
                        "type": "boolean",
                        "description": "Whether to include completed/past reminders. Default false.",
                        "default": False,
                    }
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_food",
            "description": (
                "Search for a food item to get nutrition info (calories, protein, carbs, fat) using FatSecret. "
                "Use when the user asks about calories, macros, nutrition, or what to eat."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Food name to search for, e.g. 'chicken breast', 'banana', 'Big Mac'.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max number of results. Default 5.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_food_nutrition",
            "description": (
                "Get detailed nutrition breakdown for a specific food item by its FatSecret food_id. "
                "Use after search_food to get full details on a specific result."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "food_id": {
                        "type": "string",
                        "description": "The food_id from a search_food result.",
                    },
                },
                "required": ["food_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "log_food_entry",
            "description": (
                "Log a food item to the user's FatSecret food diary to track calories. "
                "First call search_food to find the food, then get_food_nutrition to get the serving_id (search_food alone does not return serving_id). "
                "Use when the user says 'I ate X', 'log X calories', 'add X to my food diary'."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "food_id": {
                        "type": "string",
                        "description": "The food_id from a search_food result.",
                    },
                    "serving_id": {
                        "type": "string",
                        "description": "The serving_id from a search_food result.",
                    },
                    "food_entry_name": {
                        "type": "string",
                        "description": "The food name as it should appear in the diary (e.g. 'Banana, 1 medium').",
                    },
                    "number_of_units": {
                        "type": "number",
                        "description": "How many servings to log. Default 1.0.",
                        "default": 1.0,
                    },
                    "meal": {
                        "type": "string",
                        "description": "Meal type: 'breakfast', 'lunch', 'dinner', or 'other'. Default 'other'.",
                        "enum": ["breakfast", "lunch", "dinner", "other"],
                        "default": "other",
                    },
                },
                "required": ["food_id", "serving_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_food_log",
            "description": (
                "Get the user's food diary for today (or a specific day). "
                "Returns all logged food entries with calories and macros. "
                "Use when the user asks 'what have I eaten today', 'how many calories today', etc."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "days_ago": {
                        "type": "integer",
                        "description": "How many days ago to look up. 0 = today, 1 = yesterday. Default 0.",
                        "default": 0,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_tasks",
            "description": "Get tasks from Google Tasks (your to-do list). Returns pending tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "show_completed": {
                        "type": "boolean",
                        "description": "Whether to include completed tasks. Default false.",
                        "default": False,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "create_task",
            "description": "Create a new task in Google Tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "title": {
                        "type": "string",
                        "description": "Task title.",
                    },
                    "notes": {
                        "type": "string",
                        "description": "Optional notes/details for the task.",
                    },
                    "due": {
                        "type": "string",
                        "description": "Optional due date in ISO 8601 (e.g. '2026-03-10').",
                    },
                },
                "required": ["title"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "complete_task",
            "description": "Mark a Google Tasks task as completed. Use get_tasks first to find the task ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID from get_tasks.",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "delete_task",
            "description": "Delete a task from Google Tasks.",
            "parameters": {
                "type": "object",
                "properties": {
                    "task_id": {
                        "type": "string",
                        "description": "The task ID to delete.",
                    },
                },
                "required": ["task_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_unread_emails",
            "description": "Get the count of unread emails in the Gmail inbox.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "get_recent_emails",
            "description": "Get recent emails from Gmail inbox with sender, subject, and snippet.",
            "parameters": {
                "type": "object",
                "properties": {
                    "max_results": {
                        "type": "integer",
                        "description": "Number of emails to return. Default 5.",
                        "default": 5,
                    },
                    "unread_only": {
                        "type": "boolean",
                        "description": "Only show unread emails. Default false.",
                        "default": False,
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "read_email",
            "description": "Read the full body of a specific email by ID. Use get_recent_emails first to find the ID.",
            "parameters": {
                "type": "object",
                "properties": {
                    "message_id": {
                        "type": "string",
                        "description": "The email message ID.",
                    },
                },
                "required": ["message_id"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "search_emails",
            "description": "Search Gmail for emails matching a query (uses Gmail search syntax).",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query, e.g. 'from:professor subject:exam', 'homework', 'is:unread'.",
                    },
                    "max_results": {
                        "type": "integer",
                        "description": "Max results. Default 5.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_notification",
            "description": (
                "Send a push notification to the user's phone via ntfy. "
                "Use for reminders, alerts, or any info the user should see on their phone."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The notification message body.",
                    },
                    "title": {
                        "type": "string",
                        "description": "Notification title. Default 'Sonus'.",
                        "default": "Sonus",
                    },
                    "priority": {
                        "type": "string",
                        "enum": ["min", "low", "default", "high", "urgent"],
                        "description": "Notification priority. Default 'default'.",
                    },
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_sms",
            "description": (
                "Send a real SMS text message to the user's phone via Twilio. "
                "Use when the user asks to send a text message or SMS."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The SMS text to send.",
                    },
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_telegram_message",
            "description": (
                "Send a message to the user's Telegram chat via the Sonus bot. "
                "Use when the user asks to send something to Telegram."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message text to send.",
                    },
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "send_discord_message",
            "description": (
                "Send a message to the user's Discord channel via webhook. "
                "Use when the user asks to send something to Discord, or to push an alert/summary there."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "message": {
                        "type": "string",
                        "description": "The message text to send.",
                    },
                },
                "required": ["message"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spotify_play",
            "description": (
                "Play music on Spotify. Can play a specific song by name, resume playback, "
                "or play by Spotify URI. Requires an active Spotify device (phone, laptop, speaker)."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Song/artist to search and play, e.g. 'Blinding Lights by The Weeknd'. Leave empty to resume.",
                    },
                    "uri": {
                        "type": "string",
                        "description": "Spotify URI to play directly (e.g. spotify:track:xxx). Optional.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spotify_pause",
            "description": "Pause Spotify playback.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spotify_skip",
            "description": "Skip to next or previous track on Spotify.",
            "parameters": {
                "type": "object",
                "properties": {
                    "direction": {
                        "type": "string",
                        "enum": ["next", "previous"],
                        "description": "Skip direction. Default 'next'.",
                    },
                },
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spotify_volume",
            "description": "Set Spotify playback volume (0-100).",
            "parameters": {
                "type": "object",
                "properties": {
                    "volume": {
                        "type": "integer",
                        "description": "Volume level 0-100.",
                    },
                },
                "required": ["volume"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spotify_now_playing",
            "description": "Get info about what's currently playing on Spotify.",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spotify_search",
            "description": (
                "Search Spotify for tracks, albums, artists, or playlists. "
                "Returns a list of results with names and URIs."
            ),
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Search query.",
                    },
                    "type": {
                        "type": "string",
                        "enum": ["track", "album", "artist", "playlist"],
                        "description": "Type of result to search for. Default 'track'.",
                    },
                    "limit": {
                        "type": "integer",
                        "description": "Max results. Default 5.",
                        "default": 5,
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spotify_play_playlist",
            "description": "Search for and play a playlist on Spotify by name.",
            "parameters": {
                "type": "object",
                "properties": {
                    "query": {
                        "type": "string",
                        "description": "Playlist name to search for, e.g. 'lo-fi beats', 'workout mix'.",
                    },
                },
                "required": ["query"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spotify_shuffle",
            "description": "Turn shuffle on or off for Spotify playback.",
            "parameters": {
                "type": "object",
                "properties": {
                    "state": {
                        "type": "boolean",
                        "description": "true to enable shuffle, false to disable.",
                    },
                },
                "required": ["state"],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spotify_devices",
            "description": "List available Spotify playback devices (speakers, phones, laptops).",
            "parameters": {
                "type": "object",
                "properties": {},
                "required": [],
            },
        },
    },
    {
        "type": "function",
        "function": {
            "name": "spotify_transfer",
            "description": "Transfer Spotify playback to a different device by its device ID (get IDs from spotify_devices).",
            "parameters": {
                "type": "object",
                "properties": {
                    "device_id": {
                        "type": "string",
                        "description": "The Spotify device ID to transfer playback to.",
                    },
                },
                "required": ["device_id"],
            },
        },
    },
]


class ToolExecutor:
    """Routes tool calls to their implementations."""

    def __init__(
        self,
        device_manager: Any,
        memory_store: Any,
        weather_integration: Any,
        calendar_integration: Any,
        canvas_integration: Any,
        fatsecret_integration: Any = None,
        spotify_integration: Any = None,
        tasks_integration: Any = None,
        gmail_integration: Any = None,
        ntfy_integration: Any = None,
        discord_integration: Any = None,
        twilio_integration: Any = None,
        telegram_integration: Any = None,
    ) -> None:
        self.device_manager = device_manager
        self.memory_store = memory_store
        self.weather = weather_integration
        self.calendar = calendar_integration
        self.canvas = canvas_integration
        self.fatsecret = fatsecret_integration
        self.spotify = spotify_integration
        self.tasks = tasks_integration
        self.gmail = gmail_integration
        self.ntfy = ntfy_integration
        self.discord = discord_integration
        self.twilio = twilio_integration
        self.telegram = telegram_integration

    async def execute(self, tool_name: str, arguments: dict[str, Any]) -> str:
        try:
            handler = getattr(self, f"_exec_{tool_name}", None)
            if handler is None:
                return json.dumps({"error": f"Unknown tool: {tool_name}"})
            result = await handler(arguments)
            return json.dumps(result, default=str)
        except Exception as e:
            logger.exception("Tool execution error for %s", tool_name)
            return json.dumps({"error": str(e)})

    async def _exec_get_calendar_events(self, args: dict) -> Any:
        days = args.get("days_ahead", 1)
        return await self.calendar.get_events(days_ahead=days)

    async def _exec_create_calendar_event(self, args: dict) -> Any:
        return await self.calendar.create_event(
            title=args["title"],
            start=args["start"],
            end=args["end"],
            description=args.get("description", ""),
            location=args.get("location", ""),
        )

    async def _exec_update_calendar_event(self, args: dict) -> Any:
        return await self.calendar.update_event(
            event_id=args["event_id"],
            title=args.get("title"),
            start=args.get("start"),
            end=args.get("end"),
            description=args.get("description"),
            location=args.get("location"),
        )

    async def _exec_delete_calendar_event(self, args: dict) -> Any:
        return await self.calendar.delete_event(event_id=args["event_id"])

    async def _exec_search_calendar_events(self, args: dict) -> Any:
        return await self.calendar.search_events(
            query=args["query"],
            days_ahead=args.get("days_ahead", 30),
        )

    async def _exec_get_canvas_assignments(self, args: dict) -> Any:
        days = args.get("days_ahead", 7)
        return await self.canvas.get_assignments(days_ahead=days)

    async def _exec_get_weather(self, args: dict) -> Any:
        return await self.weather.get_current()

    async def _exec_control_device(self, args: dict) -> Any:
        device_id = args["device_id"]
        action = args["action"]
        value = args.get("value")
        return await self.device_manager.execute_action(device_id, action, value)

    async def _exec_get_device_states(self, args: dict) -> Any:
        return self.device_manager.get_all_states()

    async def _exec_store_memory(self, args: dict) -> Any:
        memory_type = args["memory_type"]
        content = args["content"]
        importance = args.get("importance", 0.5)
        await self.memory_store.store_memory(memory_type, content, importance=importance)
        return {"status": "stored", "content": content}

    async def _exec_recall_memories(self, args: dict) -> Any:
        query = args["query"]
        limit = args.get("limit", 5)
        memories = await self.memory_store.recall_memories(query, limit=limit)
        return memories

    async def _exec_create_reminder(self, args: dict) -> Any:
        title = args["title"]
        when = args["when"]
        description = args.get("description", "")
        result = await self.memory_store.create_reminder(title, when, description)
        return result

    async def _exec_get_reminders(self, args: dict) -> Any:
        include_completed = args.get("include_completed", False)
        return await self.memory_store.get_reminders(include_completed=include_completed)

    async def _exec_search_food(self, args: dict) -> Any:
        if self.fatsecret is None:
            return {"error": "FatSecret integration not available."}
        query = args["query"]
        max_results = args.get("max_results", 5)
        return await self.fatsecret.search_foods(query, max_results=max_results)

    async def _exec_get_food_nutrition(self, args: dict) -> Any:
        if self.fatsecret is None:
            return {"error": "FatSecret integration not available."}
        food_id = args["food_id"]
        return await self.fatsecret.get_food_details(food_id)

    async def _exec_log_food_entry(self, args: dict) -> Any:
        if self.fatsecret is None:
            return {"error": "FatSecret integration not available."}
        return await self.fatsecret.log_food_entry(
            food_id=args["food_id"],
            serving_id=args["serving_id"],
            food_entry_name=args.get("food_entry_name", ""),
            number_of_units=args.get("number_of_units", 1.0),
            meal=args.get("meal", "other"),
        )

    async def _exec_get_food_log(self, args: dict) -> Any:
        if self.fatsecret is None:
            return {"error": "FatSecret integration not available."}
        import time as _time
        days_ago = args.get("days_ago", 0)
        date_int = int(_time.time() // 86400) - days_ago
        return await self.fatsecret.get_food_entries(date_int=date_int)

    # ── Google Tasks ──

    async def _exec_get_tasks(self, args: dict) -> Any:
        if self.tasks is None:
            return {"error": "Google Tasks not available."}
        return await self.tasks.get_tasks(show_completed=args.get("show_completed", False))

    async def _exec_create_task(self, args: dict) -> Any:
        if self.tasks is None:
            return {"error": "Google Tasks not available."}
        return await self.tasks.create_task(
            title=args["title"],
            notes=args.get("notes", ""),
            due=args.get("due", ""),
        )

    async def _exec_complete_task(self, args: dict) -> Any:
        if self.tasks is None:
            return {"error": "Google Tasks not available."}
        return await self.tasks.complete_task(task_id=args["task_id"])

    async def _exec_delete_task(self, args: dict) -> Any:
        if self.tasks is None:
            return {"error": "Google Tasks not available."}
        return await self.tasks.delete_task(task_id=args["task_id"])

    # ── Gmail ──

    async def _exec_get_unread_emails(self, args: dict) -> Any:
        if self.gmail is None:
            return {"error": "Gmail not available."}
        return await self.gmail.get_unread_count()

    async def _exec_get_recent_emails(self, args: dict) -> Any:
        if self.gmail is None:
            return {"error": "Gmail not available."}
        return await self.gmail.get_recent_emails(
            max_results=args.get("max_results", 5),
            unread_only=args.get("unread_only", False),
        )

    async def _exec_read_email(self, args: dict) -> Any:
        if self.gmail is None:
            return {"error": "Gmail not available."}
        return await self.gmail.read_email(message_id=args["message_id"])

    async def _exec_search_emails(self, args: dict) -> Any:
        if self.gmail is None:
            return {"error": "Gmail not available."}
        return await self.gmail.search_emails(
            query=args["query"],
            max_results=args.get("max_results", 5),
        )

    # ── Ntfy ──

    async def _exec_send_notification(self, args: dict) -> Any:
        if self.ntfy is None:
            return {"error": "Ntfy not available."}
        return await self.ntfy.send(
            message=args["message"],
            title=args.get("title", "Sonus"),
            priority=args.get("priority", "default"),
        )

    # ── Spotify ──

    def _spotify_guard(self) -> dict[str, str] | None:
        if self.spotify is None:
            return {"error": "Spotify integration not available."}
        return None

    async def _exec_spotify_play(self, args: dict) -> Any:
        if (err := self._spotify_guard()):
            return err
        return await self.spotify.play(query=args.get("query"), uri=args.get("uri"))

    async def _exec_spotify_pause(self, args: dict) -> Any:
        if (err := self._spotify_guard()):
            return err
        return await self.spotify.pause()

    async def _exec_spotify_skip(self, args: dict) -> Any:
        if (err := self._spotify_guard()):
            return err
        return await self.spotify.skip(direction=args.get("direction", "next"))

    async def _exec_spotify_volume(self, args: dict) -> Any:
        if (err := self._spotify_guard()):
            return err
        return await self.spotify.set_volume(args["volume"])

    async def _exec_spotify_now_playing(self, args: dict) -> Any:
        if (err := self._spotify_guard()):
            return err
        return await self.spotify.get_current_playback()

    async def _exec_spotify_search(self, args: dict) -> Any:
        if (err := self._spotify_guard()):
            return err
        return await self.spotify.search(
            query=args["query"],
            search_type=args.get("type", "track"),
            limit=args.get("limit", 5),
        )

    async def _exec_spotify_play_playlist(self, args: dict) -> Any:
        if (err := self._spotify_guard()):
            return err
        return await self.spotify.play_playlist(args["query"])

    async def _exec_spotify_shuffle(self, args: dict) -> Any:
        if (err := self._spotify_guard()):
            return err
        return await self.spotify.shuffle(args["state"])

    async def _exec_spotify_devices(self, args: dict) -> Any:
        if (err := self._spotify_guard()):
            return err
        return await self.spotify.get_devices()

    async def _exec_spotify_transfer(self, args: dict) -> Any:
        if (err := self._spotify_guard()):
            return err
        return await self.spotify.transfer_playback(args["device_id"])

    # ── Discord ──

    async def _exec_send_discord_message(self, args: dict) -> Any:
        if self.discord is None:
            return {"error": "Discord not connected. Add it on the Integrations page."}
        return await self.discord.send_message(args["message"])

    # ── Twilio ──

    async def _exec_send_sms(self, args: dict) -> Any:
        if self.twilio is None:
            return {"error": "Twilio SMS not connected. Add it on the Integrations page."}
        return await self.twilio.send_sms(args["message"])

    # ── Telegram ──

    async def _exec_send_telegram_message(self, args: dict) -> Any:
        if self.telegram is None:
            return {"error": "Telegram not connected. Add it on the Integrations page."}
        return await self.telegram.send_message(args["message"])
