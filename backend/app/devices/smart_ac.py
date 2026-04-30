from typing import Any

from backend.app.devices.base import Device

VALID_MODES = ("cool", "heat", "fan", "auto", "dry")
VALID_FAN_SPEEDS = ("low", "medium", "high", "auto")
MIN_TEMP = 60
MAX_TEMP = 85


class SmartAC(Device):
    def __init__(self, device_id: str = "ac.bedroom") -> None:
        super().__init__(device_id, "ac")
        self._on: bool = False
        self._target_temp: int = 72
        self._mode: str = "cool"
        self._fan_speed: str = "auto"

    def get_state(self) -> dict[str, Any]:
        return {
            "on": self._on,
            "target_temp": self._target_temp,
            "mode": self._mode,
            "fan_speed": self._fan_speed,
        }

    def load_state(self, state: dict[str, Any]) -> None:
        self._on = state.get("on", False)
        temp = state.get("target_temp", 72)
        self._target_temp = max(MIN_TEMP, min(MAX_TEMP, int(temp)))
        mode = state.get("mode", "cool")
        self._mode = mode if mode in VALID_MODES else "cool"
        fan = state.get("fan_speed", "auto")
        self._fan_speed = fan if fan in VALID_FAN_SPEEDS else "auto"

    async def execute_action(self, action: str, value: Any = None) -> dict[str, Any]:
        if action == "turn_on":
            self._on = True
        elif action == "turn_off":
            self._on = False
        elif action == "set_temp":
            try:
                temp = int(value)
            except (TypeError, ValueError):
                return {"error": f"Invalid temperature: {value}. Use a number between {MIN_TEMP}-{MAX_TEMP}."}
            if temp < MIN_TEMP or temp > MAX_TEMP:
                return {"error": f"Temperature must be between {MIN_TEMP}°F and {MAX_TEMP}°F."}
            self._target_temp = temp
            self._on = True
        elif action == "set_mode":
            mode = str(value).lower().strip()
            if mode not in VALID_MODES:
                return {"error": f"Invalid AC mode: {value}. Use {', '.join(VALID_MODES)}."}
            self._mode = mode
            self._on = True
        elif action == "set_fan_speed":
            speed = str(value).lower().strip()
            if speed not in VALID_FAN_SPEEDS:
                return {"error": f"Invalid fan speed: {value}. Use {', '.join(VALID_FAN_SPEEDS)}."}
            self._fan_speed = speed
        else:
            return {"error": f"Unknown AC action: {action}. Use turn_on, turn_off, set_temp, set_mode, or set_fan_speed."}
        return self.get_state()
