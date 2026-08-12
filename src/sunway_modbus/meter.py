"""The external grid meter."""

from __future__ import annotations

from modbus_connection.model import int32, uint32

from .model import SunwayComponent


class Meter(SunwayComponent):
    """Power and energy as measured by the meter at the grid connection."""

    phase_a_power = int32(10994, unit="W")
    """Phase A power on the meter; positive is export."""

    phase_b_power = int32(10996, unit="W")
    """Phase B power on the meter; positive is export."""

    phase_c_power = int32(10998, unit="W")
    """Phase C power on the meter; positive is export."""

    total_power = int32(11000, unit="W")
    """Total power on the meter; positive is export."""

    total_grid_injection_energy = uint32(11002, scale=0.01, unit="kWh")
    """Lifetime energy exported to the grid."""

    total_purchasing_energy = uint32(11004, scale=0.01, unit="kWh")
    """Lifetime energy imported from the grid."""
