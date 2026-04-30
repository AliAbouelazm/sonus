from abc import ABC, abstractmethod
from typing import Any


class Device(ABC):
    """Abstract base class for all smart home devices."""

    def __init__(self, device_id: str, device_type: str) -> None:
        self.device_id = device_id
        self.device_type = device_type

    @abstractmethod
    def get_state(self) -> dict[str, Any]:
        ...

    @abstractmethod
    def load_state(self, state: dict[str, Any]) -> None:
        ...

    @abstractmethod
    async def execute_action(self, action: str, value: Any = None) -> dict[str, Any]:
        ...

    def to_dict(self) -> dict[str, Any]:
        return {
            "device_id": self.device_id,
            "device_type": self.device_type,
            "state": self.get_state(),
        }
