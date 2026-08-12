"""PV generation and the two MPPT strings."""

from __future__ import annotations

from modbus_connection.model import gauge, uint32

from .model import SunwayComponent


class Solar(SunwayComponent):
    """PV yield and the per-string input measurements."""

    generation_today = uint32(11018, scale=0.1, unit="kWh")
    """PV energy generated since midnight."""

    generation_total = uint32(11020, scale=0.1, unit="kWh")
    """PV energy generated since installation."""

    input_total_power = uint32(11028, unit="W")
    """Total DC power over all PV inputs."""

    pv1_voltage = gauge(11038, 0.1, signed=False, unit="V")
    pv1_current = gauge(11039, 0.1, signed=False, unit="A")
    pv2_voltage = gauge(11040, 0.1, signed=False, unit="V")
    pv2_current = gauge(11041, 0.1, signed=False, unit="A")

    # The per-string power registers sit far above the voltage/current pairs.
    pv1_input_power = uint32(11062, unit="W")
    pv2_input_power = uint32(11064, unit="W")
