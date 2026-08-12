"""The inverter's own grid-side measurements."""

from __future__ import annotations

from modbus_connection.model import gauge, int32

from .model import SunwayComponent


class Grid(SunwayComponent):
    """Voltage, current, frequency and AC power at the inverter's grid port."""

    phase_a_voltage = gauge(11009, 0.1, signed=False, unit="V")
    phase_a_current = gauge(11010, 0.1, signed=False, unit="A")
    phase_b_voltage = gauge(11011, 0.1, signed=False, unit="V")
    phase_b_current = gauge(11012, 0.1, signed=False, unit="A")
    phase_c_voltage = gauge(11013, 0.1, signed=False, unit="V")
    phase_c_current = gauge(11014, 0.1, signed=False, unit="A")

    frequency = gauge(11015, 0.01, signed=False, unit="Hz")
    """Grid frequency."""

    ac_power = int32(11016, unit="W")
    """AC power the inverter is delivering to the grid port."""
