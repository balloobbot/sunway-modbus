"""Running status, real-time clock and fault flags."""

from __future__ import annotations

from datetime import datetime

from modbus_connection.model import bits, enum, uint32

from .enums import RunningStatus
from .model import SunwayComponent

# The clock is written as three packed registers, in the same layout as the
# read-back at 10100. It is never read back from here.
CLOCK_WRITE_REGISTER = 20000


class Status(SunwayComponent):
    """Inverter running status, clock and fault flags."""

    # Registers 10100-10102 pack the clock two fields per register.
    _rtc_year = bits(10100, 8, 8)
    _rtc_month = bits(10100, 0, 8)
    _rtc_day = bits(10101, 8, 8)
    _rtc_hour = bits(10101, 0, 8)
    _rtc_minute = bits(10102, 8, 8)
    _rtc_second = bits(10102, 0, 8)

    running_status = enum(10105, RunningStatus)
    """What the inverter is currently doing."""

    fault_flag_1 = uint32(10112)
    """Inverter fault bitmask 1, as a raw 32-bit value."""

    @property
    def clock(self) -> datetime | None:
        """The inverter's real-time clock, or None if it reads back nonsense."""
        parts = (
            self._rtc_year,
            self._rtc_month,
            self._rtc_day,
            self._rtc_hour,
            self._rtc_minute,
            self._rtc_second,
        )
        if any(part is None for part in parts):
            return None
        year, month, day, hour, minute, second = (int(part) for part in parts)  # type: ignore[arg-type]
        try:
            return datetime(2000 + year, month, day, hour, minute, second)
        except ValueError:
            return None

    @property
    def awake(self) -> bool:
        """Whether the inverter is communicating live measurements."""
        return self.running_status in (RunningStatus.ON_GRID, RunningStatus.OFF_GRID)

    async def async_sync_time(self, when: datetime | None = None) -> None:
        """Set the inverter's real-time clock (defaults to now)."""
        moment = when if when is not None else datetime.now()
        await self.modbus_unit.write_registers(
            CLOCK_WRITE_REGISTER,
            [
                ((moment.year % 100) << 8) | moment.month,
                (moment.day << 8) | moment.hour,
                (moment.minute << 8) | moment.second,
            ],
        )


class ArmStatus(SunwayComponent):
    """The ARM controller's fault flags, far from every other block."""

    arm_fault_flag_1 = uint32(18000)
    """ARM fault bitmask 1, as a raw 32-bit value."""
