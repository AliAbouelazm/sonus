"""
Fake smart home devices for train-mode tests.

Each FakeDevice records all execute_action calls so tests can assert
what interventions and patterns actually triggered.
"""
from typing import Any


class FakeDevice:
    """
    Generic mock device. Records every execute_action call.
    The BiometricLoop checks type(device).__name__ for "Bulb", "AC", "Fan"
    so we create typed subclasses below.
    """
    def __init__(self, device_id: str, device_type: str = "FakeDevice"):
        self.device_id = device_id
        self.device_type = device_type  # "SmartBulb", "ACSplit", "Fan", "Thermostat"
        self.actions_log: list[dict] = []
        self.state: dict = {}

    async def execute_action(self, action: str, params: dict = None) -> dict:
        entry = {"action": action, "params": params or {}}
        self.actions_log.append(entry)

        # Update internal state for assertions
        if action == "set_brightness":
            self.state["brightness"] = (params or {}).get("brightness")
        elif action == "set_color_temp":
            self.state["color_temp"] = (params or {}).get("temp")
        elif action == "turn_on":
            self.state["on"] = True
        elif action == "turn_off":
            self.state["on"] = False
        elif action == "set_temperature":
            self.state["temperature"] = (params or {}).get("temperature")

        return {"ok": True}

    def received_action(self, action: str) -> bool:
        return any(a["action"] == action for a in self.actions_log)

    def last_action(self) -> dict | None:
        return self.actions_log[-1] if self.actions_log else None

    def clear_log(self):
        self.actions_log.clear()


# Named subclasses so BiometricLoop's `type(device).__name__` checks work:
#   "Bulb" in "SmartBulb" → True   "AC" in "ACSplit" → True   "Fan" in "Fan" → True
class SmartBulb(FakeDevice):
    def __init__(self, device_id: str):
        super().__init__(device_id, "SmartBulb")

class ACSplit(FakeDevice):
    def __init__(self, device_id: str):
        super().__init__(device_id, "ACSplit")

class Fan(FakeDevice):
    def __init__(self, device_id: str):
        super().__init__(device_id, "Fan")

class Thermostat(FakeDevice):
    def __init__(self, device_id: str):
        super().__init__(device_id, "Thermostat")


class FakeDeviceManager:
    """
    Wraps a dict of FakeDevice instances.
    Mirrors the interface used by BiometricLoop and ThinkingLoop.
    """
    def __init__(self, devices: dict[str, FakeDevice]):
        self.devices = devices

    def all_actions(self) -> list[dict]:
        """Flatten all actions from all devices."""
        result = []
        for dev_id, dev in self.devices.items():
            for action in dev.actions_log:
                result.append({"device_id": dev_id, **action})
        return result

    def clear_all_logs(self):
        for dev in self.devices.values():
            dev.clear_log()


# ---------------------------------------------------------------------------
# Preset device sets
# ---------------------------------------------------------------------------

def few_devices() -> FakeDeviceManager:
    """
    Minimal setup: 1 smart bulb + 1 AC unit.
    Matches 'few integrations' scenario.
    """
    return FakeDeviceManager({
        "living_room_bulb": SmartBulb("living_room_bulb"),
        "bedroom_ac":       ACSplit("bedroom_ac"),
    })


def many_devices() -> FakeDeviceManager:
    """
    Full setup: multiple lights, AC, fans, thermostat.
    Matches 'many integrations' scenario.
    """
    return FakeDeviceManager({
        "living_room_bulb":  SmartBulb("living_room_bulb"),
        "bedroom_bulb":      SmartBulb("bedroom_bulb"),
        "office_bulb":       SmartBulb("office_bulb"),
        "bedroom_ac":        ACSplit("bedroom_ac"),
        "living_room_fan":   Fan("living_room_fan"),
        "office_fan":        Fan("office_fan"),
        "thermostat":        Thermostat("thermostat"),
    })
