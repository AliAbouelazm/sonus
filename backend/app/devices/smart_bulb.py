from typing import Any

from backend.app.devices.base import Device

VALID_COLOR_TEMPS = ("warm", "neutral", "cool")

NAMED_COLORS: dict[str, str] = {
    "red": "#ff0000",
    "green": "#00ff00",
    "blue": "#0000ff",
    "purple": "#8b00ff",
    "violet": "#8b00ff",
    "pink": "#ff69b4",
    "orange": "#ff8c00",
    "yellow": "#ffd700",
    "cyan": "#00ffff",
    "teal": "#008080",
    "magenta": "#ff00ff",
    "white": "#ffffff",
    "lavender": "#b57edc",
    "lime": "#32cd32",
    "coral": "#ff7f50",
    "salmon": "#fa8072",
    "gold": "#ffd700",
    "indigo": "#4b0082",
    "turquoise": "#40e0d0",
    "mint": "#98ff98",
    "peach": "#ffcba4",
    "maroon": "#800000",
    "navy": "#000080",
    "sky blue": "#87ceeb",
    "forest green": "#228b22",
    "crimson": "#dc143c",
    "amber": "#ffbf00",
    "rose": "#ff007f",
}

COLOR_TEMP_HEX: dict[str, str] = {
    "warm": "#ffb347",
    "neutral": "#fff4e0",
    "cool": "#87ceeb",
}


def _parse_color(value: Any) -> str | None:
    """Try to resolve a user value to a hex color string."""
    if value is None:
        return None
    raw = str(value).strip().lower()
    if raw in NAMED_COLORS:
        return NAMED_COLORS[raw]
    clean = raw.lstrip("#")
    if len(clean) == 6:
        try:
            int(clean, 16)
            return f"#{clean}"
        except ValueError:
            pass
    if len(clean) == 3:
        try:
            int(clean, 16)
            expanded = "".join(c * 2 for c in clean)
            return f"#{expanded}"
        except ValueError:
            pass
    return None


class SmartBulb(Device):
    def __init__(self, device_id: str) -> None:
        super().__init__(device_id, "bulb")
        self._on: bool = False
        self._brightness: int = 80
        self._color_temp: str = "warm"
        self._color: str = ""

    def get_state(self) -> dict[str, Any]:
        return {
            "on": self._on,
            "brightness": self._brightness,
            "color_temp": self._color_temp,
            "color": self._color,
        }

    def load_state(self, state: dict[str, Any]) -> None:
        self._on = state.get("on", False)
        self._brightness = state.get("brightness", 80)
        ct = state.get("color_temp", "warm")
        self._color_temp = ct if ct in VALID_COLOR_TEMPS else "warm"
        self._color = state.get("color", "")

    async def execute_action(self, action: str, value: Any = None) -> dict[str, Any]:
        if action == "turn_on":
            self._on = True
        elif action == "turn_off":
            self._on = False
        elif action == "set_brightness":
            try:
                level = int(value)
                self._brightness = max(0, min(100, level))
                if self._brightness > 0:
                    self._on = True
            except (TypeError, ValueError):
                return {"error": f"Invalid brightness value: {value}. Provide a number 0-100."}
        elif action == "set_color_temp":
            temp = str(value).lower().strip()
            if temp not in VALID_COLOR_TEMPS:
                return {"error": f"Invalid color_temp: {value}. Use 'warm', 'neutral', or 'cool'."}
            self._color_temp = temp
            self._color = ""
        elif action == "set_color":
            parsed = _parse_color(value)
            if parsed is None:
                names = ", ".join(sorted(NAMED_COLORS.keys()))
                return {
                    "error": f"Invalid color: {value}. Use a color name ({names}) or hex code (#ff0000)."
                }
            self._color = parsed
            self._on = True
        else:
            return {
                "error": (
                    f"Unknown bulb action: {action}. "
                    "Use turn_on, turn_off, set_brightness, set_color_temp, or set_color."
                )
            }
        return self.get_state()
