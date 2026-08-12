"""The backup (EPS / UPS) output port."""

from __future__ import annotations

from modbus_connection.model import gauge, int32

from .model import SunwayComponent


class Backup(SunwayComponent):
    """Measurements on the off-grid backup output."""

    phase_a_voltage = gauge(40200, 0.1, signed=False, unit="V")
    phase_a_current = gauge(40201, 0.1, signed=False, unit="A")
    phase_a_power = int32(40204, unit="W")

    total_power = int32(40230, unit="W")
    """Total power delivered on the backup output."""
