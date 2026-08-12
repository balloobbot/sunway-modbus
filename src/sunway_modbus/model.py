"""SunWay-specific pieces layered on the ``modbus_connection.model`` framework.

The generic ``Component`` base and the field helpers come straight from
``modbus_connection.model``; sub-systems import those directly. This module adds
only what is specific to the SunWay STT control:

- :class:`SunwayComponent`, a ``Component`` preset with the inverter's read cap;
- :func:`in_range`, the write validator used for the settings registers.

No readable address ranges are declared: the source integration has no map of
which registers the inverter serves, only a 100-register cap on how wide a single
read may be, so reads are planned from the fields themselves.

Everything on this device is a holding register (FC03); there are no coils and no
input registers.
"""

from __future__ import annotations

from collections.abc import Callable

from modbus_connection.model import Component

# The source integration reads this device in blocks of at most 100 registers.
MAX_READ_SPAN = 100


class SunwayComponent(Component):
    """A SunWay sub-system: holding registers, capped at the inverter's read width."""

    max_span = MAX_READ_SPAN


def in_range(low: float, high: float) -> Callable[[float], float]:
    """Reject a write outside the register's documented range."""

    def validate(value: float) -> float:
        if not low <= value <= high:
            raise ValueError(f"{value} is outside {low}..{high}")
        return value

    return validate
