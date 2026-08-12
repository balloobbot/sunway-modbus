"""The top-level SunWay inverter object."""

from __future__ import annotations

from typing import TYPE_CHECKING

from modbus_connection import IllegalDataAddressError
from modbus_connection.model import Component, ComponentGroup

from .backup import Backup
from .battery import Battery, BatteryEnergy
from .bms import Bms, BmsInfo
from .device_info import DeviceInformation
from .grid import Grid
from .meter import Meter
from .settings import BatteryProtection, GridInjectionLimit, InverterSettings
from .solar import Solar
from .status import ArmStatus, Status

if TYPE_CHECKING:
    from modbus_connection import ModbusUnit


class SunwayInverter:
    """A SunWay STT hybrid solar inverter.

    Construct it from a ``ModbusUnit`` — the caller owns the connection — and
    call :meth:`async_update` to refresh every sub-system in one pooled set of
    block reads. The first update reads the identity registers and probes which
    blocks this inverter serves.
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

        # Filled in by the first update: the sub-systems this inverter answered.
        self.polled_components: tuple[Component, ...] = ()
        self._group: ComponentGroup | None = None

    @property
    def _candidates(self) -> tuple[Component, ...]:
        """Every sub-system that is polled, identity aside."""
        return (
            self.status,
            self.arm_status,
            self.meter,
            self.grid,
            self.solar,
            self.backup,
            self.battery,
            self.battery_energy,
            self.bms_info,
            self.bms,
            self.grid_injection_limit,
            self.settings,
            self.battery_protection,
        )

    async def _async_setup(self) -> None:
        """Read the identity and settle which sub-systems this inverter serves.

        A sub-system whose registers the inverter refuses outright is dropped
        from the poll; its fields keep reading ``None``. Anything else — a
        timeout, a closed connection — propagates, and setup runs again on the
        next update.
        """
        await self.info.async_update()

        served: list[Component] = []
        for component in self._candidates:
            try:
                await component.async_update()
            except IllegalDataAddressError:
                continue
            served.append(component)

        self.polled_components = tuple(served)
        self._group = ComponentGroup(self._unit, served)

    async def async_update(self) -> None:
        """Refresh every served sub-system; the first call sets the inverter up."""
        if self._group is None:
            await self._async_setup()
            return  # setup already read everything once
        await self._group.async_update()
