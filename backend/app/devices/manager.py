import logging
from typing import Any, Callable, Coroutine, Optional

from backend.app.devices.base import Device
from backend.app.devices.smart_bulb import SmartBulb
from backend.app.devices.smart_ac import SmartAC
from backend.app.devices.smart_fan import SmartFan
from backend.app.devices.smart_lock import SmartLock

logger = logging.getLogger(__name__)

OnStateChange = Callable[[str, dict[str, Any]], Coroutine[Any, Any, None]]

# Maps integration_id → (device_type_prefix, Device class)
INTEGRATION_DEVICE_MAP: dict[str, tuple[str, type]] = {
    "smart_lock": ("lock", SmartLock),
    "smart_bulb": ("bulb", SmartBulb),
    "smart_fan": ("fan", SmartFan),
    "smart_ac": ("ac", SmartAC),
}


def device_id_for(integration_id: str, instance_id: str) -> Optional[str]:
    """Return the device_id for a given integration instance, or None if not hardware."""
    entry = INTEGRATION_DEVICE_MAP.get(integration_id)
    if not entry:
        return None
    prefix, _ = entry
    return f"{prefix}.{instance_id}"


class DeviceManager:
    """Central manager for all smart home devices. Devices are created dynamically
    when hardware integrations are connected and removed when they are disconnected."""

    def __init__(self) -> None:
        self._devices: dict[str, Device] = {}
        self._on_state_change: Optional[OnStateChange] = None
        self._disabled: set[str] = set()

    def add_device(self, device_id: str, device: Device) -> None:
        if device_id not in self._devices:
            self._devices[device_id] = device
            logger.info("Added device: %s", device_id)

    def remove_device(self, device_id: str) -> None:
        if device_id in self._devices:
            del self._devices[device_id]
            self._disabled.discard(device_id)
            logger.info("Removed device: %s", device_id)

    def sync_from_integrations(self, configs: list[dict[str, Any]]) -> None:
        """Add/remove devices to match the list of connected hardware integrations."""
        expected: dict[str, type] = {}
        for cfg in configs:
            int_id = cfg.get("integration_id", "")
            inst_id = cfg.get("instance_id", "")
            entry = INTEGRATION_DEVICE_MAP.get(int_id)
            if entry:
                prefix, cls = entry
                did = f"{prefix}.{inst_id}"
                expected[did] = cls

        # Add missing
        for did, cls in expected.items():
            if did not in self._devices:
                self._devices[did] = cls(did)
                logger.info("Synced — added device: %s", did)

        # Remove stale
        stale = [did for did in list(self._devices) if did not in expected]
        for did in stale:
            self.remove_device(did)

    def set_on_state_change(self, callback: OnStateChange) -> None:
        self._on_state_change = callback

    def get_device(self, device_id: str) -> Optional[Device]:
        return self._devices.get(device_id)

    def set_disabled(self, device_ids: list[str]) -> None:
        self._disabled = set(device_ids)
        logger.info("Disabled devices: %s", self._disabled or "none")

    def is_disabled(self, device_id: str) -> bool:
        return device_id in self._disabled

    def get_all_states(self) -> dict[str, Any]:
        return {
            did: {**dev.to_dict(), "disabled": did in self._disabled}
            for did, dev in self._devices.items()
        }

    async def execute_action(self, device_id: str, action: str, value: Any = None) -> dict[str, Any]:
        device = self._devices.get(device_id)
        if device is None:
            return {"error": f"Unknown device: {device_id}"}
        if device_id in self._disabled:
            return {"error": f"Device {device_id} is currently disabled."}

        result = await device.execute_action(action, value)

        if "error" not in result and self._on_state_change:
            try:
                await self._on_state_change(device_id, device.to_dict())
            except Exception:
                logger.exception("Error in state change callback")

        return {"device_id": device_id, "action": action, "new_state": result}

    def load_states(self, states: dict[str, dict[str, Any]]) -> None:
        for device_id, state_data in states.items():
            device = self._devices.get(device_id)
            if device:
                device.load_state(state_data)
                logger.info("Loaded persisted state for %s", device_id)

    def export_states(self) -> dict[str, dict[str, Any]]:
        return {did: dev.get_state() for did, dev in self._devices.items()}
