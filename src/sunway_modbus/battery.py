"""The battery port and its lifetime energy counters."""

from __future__ import annotations

from modbus_connection.model import enum, gauge, int32, uint32

from .enums import BatteryMode
from .model import SunwayComponent


class Battery(SunwayComponent):
    """Live battery measurements at the inverter's DC port."""

    voltage = gauge(40254, 0.1, signed=False, unit="V")
    current = gauge(40255, 0.1, unit="A")
    mode = enum(40256, BatteryMode)
    """Whether the battery is charging or discharging."""

    power = int32(40258, unit="W")
    """Battery power; sign follows the inverter's own convention."""


class BatteryEnergy(SunwayComponent):
    """Lifetime battery energy counters, in their own register block."""

    total_charged = uint32(41108, scale=0.1, unit="kWh")
    total_discharged = uint32(41110, scale=0.1, unit="kWh")
