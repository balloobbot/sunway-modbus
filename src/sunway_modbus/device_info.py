"""Inverter identity — read once at setup, never polled."""

from __future__ import annotations

from modbus_connection.model import integer, raw_register, string

from .enums import EQUIPMENT_MODELS
from .model import SunwayComponent


class DeviceInformation(SunwayComponent):
    """Serial number, model and firmware of the inverter."""

    serial_number = string(10000, 4)
    """Inverter serial number (8 ASCII characters)."""

    _equipment_info = raw_register(10008)

    firmware_version = integer(10011, signed=False)
    """Firmware version as the inverter reports it."""

    manufacturer = "SunWay"

    @property
    def model(self) -> str | None:
        """Product name decoded from the equipment info register."""
        code = self._equipment_info
        if code is None:
            return None
        return EQUIPMENT_MODELS.get((code >> 8, code & 0xFF), "Unknown")
