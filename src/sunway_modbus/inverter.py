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

# What the inverter measures, in read order. info is absent: the identity
# registers are read once, at setup.
_MEASURED = (
    "status",
    "meter",
    "grid",
    "solar",
    "arm_status",
    "backup",
    "battery",
    "battery_energy",
    "bms_info",
    "bms",
)

# What the inverter has been configured to do: every writable block, none of
# which changes unless something writes it. bms_info stays measured — the BMS
# reports its own current limits there, they are not set from outside.
_CONFIGURED = (
    "grid_injection_limit",
    "settings",
    "battery_protection",
)

# Every component attribute a poll may refresh, in read order.
_POLLED = (*_MEASURED, *_CONFIGURED)

# The refusals that mean "this inverter does not serve those registers". Any
# other failure says nothing about the register map.
_ABSENT = (IllegalDataAddressError, IllegalFunctionError)


class SunwayInverter:
    """A SunWay STT hybrid solar inverter.

    Construct it from a ``ModbusUnit`` — the caller owns the connection — and
    call :meth:`async_update` to refresh every sub-system. The first update
    reads the identity registers and probes which blocks this inverter serves.

    Each sub-system is read on its own, so one slow or refused block cannot
    blank the rest: every update method returns an :class:`UpdateReport` naming
    what refreshed and what failed with which error.

    What the inverter measures and what it has been configured to do refresh
    separately — :meth:`async_update_measurements` and
    :meth:`async_update_settings` — so a caller can poll the settings rarely, or
    on demand after writing one. :meth:`async_update` does both.
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
        report = await self._async_read(_POLLED, UpdateReport(set(), {}))
        absent = {
            name for name, err in report.failed.items() if isinstance(err, _ABSENT)
        }
        self._polled = [name for name in _POLLED if name not in absent]
        return UpdateReport(
            report.updated,
            {name: err for name, err in report.failed.items() if name not in absent},
        )

    async def async_update_measurements(self) -> UpdateReport:
        """Refresh what the inverter measures: power, energy, battery, status.

        The first call sets the inverter up, which probes every sub-system, so
        that one report covers the settings too.
        """
        if self._polled is None:
            return await self.async_setup()
        return await self._async_read(
            self._served(_MEASURED), UpdateReport(set(), {}), fatal_timeout=True
        )

    async def async_update_settings(self) -> UpdateReport:
        """Refresh what is configured: working mode, export limit, DOD protection.

        These change when something writes them, not on their own, so a caller
        that polls them at all polls them rarely — and reads them straight after
        writing one. The first call sets the inverter up.
        """
        if self._polled is None:
            return await self.async_setup()
        return await self._async_read(
            self._served(_CONFIGURED), UpdateReport(set(), {}), fatal_timeout=True
        )

    async def async_update(self) -> UpdateReport:
        """Refresh measurements and settings together, in one report.

        For a caller that does not want to schedule the two apart. A timeout
        with nothing read yet raises: the inverter is not answering, and the
        rest would only wait for their own timeouts.
        """
        if self._polled is None:
            return await self.async_setup()  # the probe reads everything already
        report = await self._async_read(
            self._served(_MEASURED), UpdateReport(set(), {}), fatal_timeout=True
        )
        return await self._async_read(
            self._served(_CONFIGURED), report, fatal_timeout=True
        )

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

    def _served(self, names: Sequence[str]) -> list[str]:
        """The named sub-systems this inverter answered for at setup."""
        assert self._polled is not None  # async_setup() builds it
        return [name for name in names if name in self._polled]

    async def _async_read(
        self,
        names: Sequence[str],
        report: UpdateReport,
        *,
        fatal_timeout: bool = False,
    ) -> UpdateReport:
        """Read the named sub-systems one at a time, adding to ``report``.

        Listeners fire only once every sub-system in this read has been tried,
        and only for the ones that refreshed — a failed component's store is
        untouched, so its fields keep their previous values.

        ``fatal_timeout`` raises a timeout that nothing in ``report`` has
        answered before. The setup probe leaves it off: there a timeout must
        keep its sub-system.
        """
        for name in names:
            component: SunwayComponent = getattr(self, name)
            try:
                await component.async_update(notify=False)
            except ModbusConnectionError:
                raise
            except ModbusTimeoutError as err:
                if fatal_timeout and not report.updated and not report.failed:
                    raise  # nothing answered at all; assume the rest time out too
                report.failed[name] = err
            except ModbusError as err:
                report.failed[name] = err
            else:
                report.updated.add(name)
        for name in names:
            if name in report.updated:
                fresh: SunwayComponent = getattr(self, name)
                fresh.notify()
        return report
