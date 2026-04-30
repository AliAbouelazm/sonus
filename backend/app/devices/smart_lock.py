from typing import Any

from backend.app.devices.base import Device


class SmartLock(Device):
    def __init__(self, device_id: str = "lock.bedroom") -> None:
        super().__init__(device_id, "lock")
        self._locked: bool = True

    def get_state(self) -> dict[str, Any]:
        return {"locked": self._locked}

    def load_state(self, state: dict[str, Any]) -> None:
        self._locked = state.get("locked", True)

    async def execute_action(self, action: str, value: Any = None) -> dict[str, Any]:
        if action == "lock":
            self._locked = True
        elif action == "unlock":
            self._locked = False
        else:
            return {"error": f"Unknown lock action: {action}. Use 'lock' or 'unlock'."}
        return self.get_state()
