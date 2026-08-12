"""Coded register values on the SunWay STT inverter."""

from __future__ import annotations

from enum import IntEnum


class RunningStatus(IntEnum):
    """Inverter running status (register 10105)."""

    WAIT = 0
    CHECK = 1
    ON_GRID = 2
    FAULT = 3
    FLASH = 4  # firmware update in progress
    OFF_GRID = 5


class BatteryMode(IntEnum):
    """Battery charge direction (register 40256)."""

    DISCHARGE = 0
    CHARGE = 1


class WorkingMode(IntEnum):
    """Hybrid inverter working mode (register 50000)."""

    GENERAL = 1
    ECONOMIC = 2
    UPS = 3
    EMS_GENERAL = 258
    EMS_AC_CTRL = 259
    EMS_BATT_CTRL = 513
    EMS_OFF_GRID = 772


class AcPowerSettingMode(IntEnum):
    """Inverter AC power setting mode (register 50202)."""

    OFF = 0
    TOTAL_POWER = 1
    PER_PHASE_POWER = 2


class PowerOutputPriority(IntEnum):
    """Priority power output setting (register 50210)."""

    PV = 0
    BATTERY = 1


# Register 10008 packs a hardware code in the high byte and a power-rating index
# in the low byte. Entries the inverter reports but that name no product are
# "N/A" in the source integration and are kept as such.
EQUIPMENT_MODELS: dict[tuple[int, int], str] = {
    (0x30, 0): "WTS-4KW-3P",
    (0x31, 0): "N/A",
    (0x30, 1): "WTS-5KW-3P",
    (0x31, 1): "N/A",
    (0x30, 2): "WTS-6KW-3P",
    (0x31, 2): "WTS-4.2KW-1P",
    (0x30, 3): "WTS-8KW-3P",
    (0x31, 3): "WTS-4.6KW-1P",
    (0x30, 4): "WTS-10KW-3P",
    (0x31, 4): "WTS-5KW-1P",
    (0x30, 5): "WTS-12KW-3P",
    (0x31, 5): "WTS-6KW-1P",
    (0x30, 6): "N/A",
    (0x31, 6): "WTS-7KW-1P",
    (0x30, 7): "N/A",
    (0x31, 7): "WTS-8KW-1P",
    (0x30, 8): "N/A",
    (0x31, 8): "WTS-3KW-1P",
    (0x30, 9): "N/A",
    (0x31, 9): "WTS-3.6KW-1P",
}
