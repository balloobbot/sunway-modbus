"""The top-level SunWay inverter object."""

from __future__ import annotations

from typing import TYPE_CHECKING

from modbus_connection import (
    IllegalDataAddressError,
    IllegalFunctionError,
    ModbusConnectionError,
    ModbusError,
    ModbusTimeoutError,
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
        """Refresh every served sub-system; the first call sets the inverter up.

        A timeout with nothing read yet raises: the inverter is not answering,
        and the rest would only wait for their own timeouts.
        """
        if self._polled is None:
            return await self.async_setup()
        updated, failed = await self._async_read(self._polled, fatal_timeout=True)
        return UpdateReport(updated, failed)

    async def async_read_raw(self) -> dict[str, dict[int, int | bool]]:
        """Every register this inverter reads, undecoded — for diagnostics.

        The identity block comes along: a poll never reads it again, and it is
        the first thing an issue report is read for. Left out are the
        sub-systems setup found this inverter does not serve, so a dump is not
        half refusals; one that refuses anyway raises, since there the error is
        the point. The first call sets the inverter up. Nothing notifies: a
        download is not a poll.
        """
        if self._polled is None:
            await self.async_setup()
        assert self._polled is not None  # async_setup() builds it
        raw: dict[str, dict[int, int | bool]] = {}
        for name in ("info", *self._polled):
            component: SunwayComponent = getattr(self, name)
            for space, values in (await component.async_read_raw(notify=False)).items():
                raw.setdefault(space, {}).update(values)
        return {space: dict(sorted(values.items())) for space, values in raw.items()}

    async def _async_read(
        self, names: Sequence[str], *, fatal_timeout: bool = False
    ) -> tuple[set[str], dict[str, ModbusError]]:
        """Read the named sub-systems one at a time, containing failures.

        Listeners fire only once every sub-system has been tried, and only for
        the ones that refreshed — a failed component's store is untouched, so
        its fields keep their previous values.

        ``fatal_timeout`` raises a timeout that nothing has answered before.
        The setup probe leaves it off: there a timeout must keep its sub-system.
        """
        updated: set[str] = set()
        failed: dict[str, ModbusError] = {}
        for name in names:
            component: SunwayComponent = getattr(self, name)
            try:
                await component.async_update(notify=False)
            except ModbusConnectionError:
                raise
            except ModbusTimeoutError as err:
                if fatal_timeout and not updated and not failed:
                    raise  # nothing answered at all; assume the rest time out too
                failed[name] = err
            except ModbusError as err:
                failed[name] = err
            else:
                updated.add(name)
        for name in updated:
            fresh: SunwayComponent = getattr(self, name)
            fresh.notify()
        return updated, failed
