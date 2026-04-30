from typing import Any

from backend.app.devices.base import Device

VALID_SPEEDS = ("low", "medium", "high")


class SmartFan(Device):
    def __init__(self, device_id: str = "fan.bedroom") -> None:
        super().__init__(device_id, "fan")
        self._on: bool = False
        self._speed: str = "medium"

    def get_state(self) -> dict[str, Any]:
        return {"on": self._on, "speed": self._speed}

    def load_state(self, state: dict[str, Any]) -> None:
        self._on = state.get("on", False)
        spd = state.get("speed", "medium")
        self._speed = spd if spd in VALID_SPEEDS else "medium"

    async def execute_action(self, action: str, value: Any = None) -> dict[str, Any]:
        if action == "turn_on":
            self._on = True
        elif action == "turn_off":
            self._on = False
        elif action == "set_speed":
            speed = str(value).lower().strip()
            if speed not in VALID_SPEEDS:
                return {"error": f"Invalid fan speed: {value}. Use 'low', 'medium', or 'high'."}
            self._speed = speed
            self._on = True
        else:
            return {"error": f"Unknown fan action: {action}. Use turn_on, turn_off, or set_speed."}
        return self.get_state()
