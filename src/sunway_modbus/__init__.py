"""sunway-modbus — read and control a SunWay STT hybrid inverter over Modbus.

Construct ``SunwayInverter(unit)`` with a ``modbus_connection.ModbusUnit``, call
``await inverter.async_update()``, then read its sub-systems as normal Python
objects::

    inverter.grid.ac_power
    inverter.solar.generation_today
    inverter.battery.power
    inverter.bms.state_of_charge
    await inverter.settings.write("working_mode", WorkingMode.ECONOMIC)

Every register on this device is a holding register (FC03); there are no coils
and no input registers. ASCII framing over TCP is not supported.

The register map is derived from the SunWay plugin of
`homeassistant-solax-modbus <https://github.com/wills106/homeassistant-solax-modbus>`_
(Apache-2.0).
"""

from .backup import Backup
from .battery import Battery, BatteryEnergy
from .bms import Bms, BmsInfo
from .device_info import DeviceInformation
from .enums import (
    EQUIPMENT_MODELS,
    AcPowerSettingMode,
    BatteryMode,
    PowerOutputPriority,
    RunningStatus,
    WorkingMode,
)
from .grid import Grid
from .inverter import SunwayInverter
from .meter import Meter
from .settings import BatteryProtection, GridInjectionLimit, InverterSettings
from .solar import Solar
from .status import ArmStatus, Status

__all__ = [
    "EQUIPMENT_MODELS",
    "AcPowerSettingMode",
    "ArmStatus",
    "Backup",
    "Battery",
    "BatteryEnergy",
    "BatteryMode",
    "BatteryProtection",
    "Bms",
    "BmsInfo",
    "DeviceInformation",
    "Grid",
    "GridInjectionLimit",
    "InverterSettings",
    "Meter",
    "PowerOutputPriority",
    "RunningStatus",
    "Solar",
    "Status",
    "SunwayInverter",
    "WorkingMode",
]
