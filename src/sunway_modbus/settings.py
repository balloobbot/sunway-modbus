"""Writable settings blocks.

These are holding registers the source integration writes but — apart from the
six on/off flags, which it mirrors into internal sensors — never reads back. They
are modelled as ordinary readable/writable fields, but kept in components of
their own so an inverter that refuses a settings block does not take the
measurement poll down with it.

The on/off flags are ``boolean`` registers: the integration reads bit 0 and
writes the whole register as 0 or 1, which agrees for every in-spec value.
"""

from __future__ import annotations

from modbus_connection.model import boolean, enum, gauge, integer

from .enums import AcPowerSettingMode, PowerOutputPriority, WorkingMode
from .model import SunwayComponent, in_range


class GridInjectionLimit(SunwayComponent):
    """Export limitation."""

    enabled = boolean(25100, writable=True)
    """Whether the grid injection power limit is applied."""

    limit = gauge(25103, 0.1, signed=False, writable=in_range(0.0, 100.0), unit="%")
    """Export limit, as a percentage of rated power."""


class InverterSettings(SunwayComponent):
    """Working mode, off-grid behaviour and AC/PV power settings."""

    working_mode = enum(50000, WorkingMode, writable=True)
    eps_ups_function = boolean(50001, writable=True)
    """Whether the backup (EPS/UPS) output is enabled."""

    off_grid_voltage = gauge(
        50004, 0.1, signed=False, writable=in_range(200.0, 250.0), unit="V"
    )
    off_grid_frequency = gauge(
        50005, 0.01, signed=False, writable=in_range(45.0, 65.0), unit="Hz"
    )
    off_grid_asymmetric_output = boolean(50006, writable=True)
    peak_load_shifting = boolean(50007, writable=True)
    max_grid_power = gauge(
        50009, 0.1, signed=False, writable=in_range(0.0, 20.0), unit="kVA"
    )

    # A second block, ~190 registers above the first.
    ac_power_setting_mode = enum(50202, AcPowerSettingMode, writable=True)
    power_output_priority = enum(50210, PowerOutputPriority, writable=True)
    pv_power = integer(50211, signed=False, writable=in_range(0, 20000), unit="W")
    """Installed PV power, in steps of 100 W."""


class BatteryProtection(SunwayComponent):
    """On- and off-grid battery depth-of-discharge protection."""

    on_grid_soc_protection = boolean(52502, writable=True)
    on_grid_depth_of_discharge = gauge(
        52503, 0.1, signed=False, writable=in_range(0.0, 100.0), unit="%"
    )
    off_grid_soc_protection = boolean(52504, writable=True)
    off_grid_depth_of_discharge = gauge(
        52505, 0.1, signed=False, writable=in_range(0.0, 100.0), unit="%"
    )
