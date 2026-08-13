"""The top-level SunWay inverter object."""

from __future__ import annotations

from typing import TYPE_CHECKING

from modbus_connection import (
    IllegalDataAddressError,
    IllegalFunctionError,
    ModbusConnectionError,
    ModbusError,
)

from .backup import Backup
from .battery import Battery, BatteryEnergy
from .bms import Bms, BmsInfo
from .device_info import DeviceInformation
from .grid import Grid
from .meter import Meter
from .model import SunwayComponent, UpdateReport
from .settings import BatteryProtection, GridInjectionLimit, InverterSettings
from .solar import Solar
from .status import ArmStatus, Status

if TYPE_CHECKING:
    from collections.abc import Sequence

    from modbus_connection import ModbusUnit

# Every component attribute a poll may refresh, in read order. info is absent:
# the identity registers are read once, at setup.
_POLLED = (
    "status",
    "meter",
    "grid",
    "solar",
    "arm_status",
    "grid_injection_limit",
    "backup",
    "battery",
    "battery_energy",
    "bms_info",
    "bms",
    "settings",
    "battery_protection",
)

# The refusals that mean "this inverter does not serve those registers". Any
# other failure says nothing about the register map.
_ABSENT = (IllegalDataAddressError, IllegalFunctionError)


class SunwayInverter:
    """A SunWay STT hybrid solar inverter.

    Construct it from a ``ModbusUnit`` — the caller owns the connection — and
    call :meth:`async_update` to refresh every sub-system. The first update
    reads the identity registers and probes which blocks this inverter serves.

    Each sub-system is read on its own, so one slow or refused block cannot
    blank the rest: :meth:`async_update` returns an :class:`UpdateReport` naming
    what refreshed and what failed with which error.
    """

    def __init__(self, unit: ModbusUnit) -> None:
        self._unit = unit

        self.info = DeviceInformation(unit)
        self.status = Status(unit)
        self.arm_status = ArmStatus(unit)
        self.meter = Meter(unit)
        self.grid = Grid(unit)
        self.solar = Solar(unit)
        self.backup = Backup(unit)
        self.battery = Battery(unit)
        self.battery_energy = BatteryEnergy(unit)
        self.bms_info = BmsInfo(unit)
        self.bms = Bms(unit)
        self.grid_injection_limit = GridInjectionLimit(unit)
        self.settings = InverterSettings(unit)
        self.battery_protection = BatteryProtection(unit)

        # The sub-systems this inverter answered for, settled by async_setup();
        # None until then, so a failed setup retries on the next update.
        self._polled: list[str] | None = None

    async def async_setup(self) -> UpdateReport:
        """Read the identity and settle which sub-systems this inverter serves.

        A sub-system whose registers the inverter refuses outright is dropped
        from the poll; its fields keep reading ``None``. A probe that fails any
        other way — a timeout, a busy device — proves nothing about the register
        map, so that sub-system stays polled and is reported as failed. If the
        identity read itself fails the device is left unset up, and the next
        update runs setup again.

        Call it again to re-probe a device that has since gained a sub-system.
        """
        await self.info.async_update()
        updated, failed = await self._async_read(_POLLED)
        absent = {name for name, err in failed.items() if isinstance(err, _ABSENT)}
        self._polled = [name for name in _POLLED if name not in absent]
        return UpdateReport(
            updated, {name: err for name, err in failed.items() if name not in absent}
        )

    async def async_update(self) -> UpdateReport:
        """Refresh every served sub-system; the first call sets the inverter up."""
        if self._polled is None:
            return await self.async_setup()
        updated, failed = await self._async_read(self._polled)
        return UpdateReport(updated, failed)

    async def _async_read(
        self, names: Sequence[str]
    ) -> tuple[set[str], dict[str, ModbusError]]:
        """Read the named sub-systems one at a time, containing failures.

        Listeners fire only once every sub-system has been tried, and only for
        the ones that refreshed — a failed component's store is untouched, so
        its fields keep their previous values.
        """
        updated: set[str] = set()
        failed: dict[str, ModbusError] = {}
        for name in names:
            component: SunwayComponent = getattr(self, name)
            try:
                await component.async_update(notify=False)
            except ModbusConnectionError:
                raise
            except ModbusError as err:
                failed[name] = err
            else:
                updated.add(name)
        for name in updated:
            fresh: SunwayComponent = getattr(self, name)
            fresh.notify()
        return updated, failed
