"""The battery management system, as the inverter relays it."""

from __future__ import annotations

from modbus_connection.model import gauge, integer, uint32

from .model import SunwayComponent


class BmsInfo(SunwayComponent):
    """What the BMS reports about itself."""

    battery_type = integer(42000, signed=False)
    battery_strings = integer(42001, signed=False)
    protocol = integer(42002, signed=False)
    software_version = integer(42003, signed=False)
    hardware_version = integer(42004, signed=False)
    max_charge_current = gauge(42005, 0.1, signed=False, unit="A")
    max_discharge_current = gauge(42006, 0.1, signed=False, unit="A")


class Bms(SunwayComponent):
    """Live BMS state of charge, temperatures, cell extremes and codes."""

    state_of_charge = gauge(43000, 0.01, signed=False, unit="%")
    state_of_health = gauge(43001, 0.01, signed=False, unit="%")
    status = integer(43002, signed=False)
    """BMS status word; the source integration does not decode it."""

    pack_temperature = gauge(43003, 0.1, signed=False, unit="°C")
    max_cell_temperature = gauge(43009, 0.1, signed=False, unit="°C")
    min_cell_temperature = gauge(43011, 0.1, signed=False, unit="°C")
    max_cell_voltage = gauge(43013, 0.001, signed=False, unit="V")
    min_cell_voltage = gauge(43015, 0.001, signed=False, unit="V")

    error_code = uint32(43016)
    warning_code = uint32(43018)
