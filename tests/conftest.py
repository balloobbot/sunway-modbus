"""Fixtures: a SunwayInverter over modbus-connection's in-memory mock backend.

The mock backend (and its ``mock_modbus_unit`` fixture) ship with
``modbus-connection`` as an auto-registered pytest plugin, so there is no real
server, socket, or backend here — just an address-keyed store loaded with
SunWay-shaped register values. Everything on this device is a holding register.
"""

from __future__ import annotations

import pytest
from modbus_connection.mock import MockModbusUnit

from sunway_modbus import SunwayInverter


def _ascii(text: str) -> list[int]:
    """Pack ASCII into 16-bit registers, two chars per register (hi, lo)."""
    if len(text) % 2:
        text += "\0"
    return [(ord(text[i]) << 8) | ord(text[i + 1]) for i in range(0, len(text), 2)]


def _u32(value: int) -> list[int]:
    """Split an unsigned 32-bit value into two big-endian registers."""
    return [(value >> 16) & 0xFFFF, value & 0xFFFF]


def _s32(value: int) -> list[int]:
    """Split a signed 32-bit value into two big-endian registers."""
    return _u32(value & 0xFFFFFFFF)


# Raw holding-register words keyed by their address; decoded view inline.
HOLDING: dict[int, int | list[int]] = {
    # -- identity --
    10000: _ascii("SW24000A"),  # serial number
    10008: 0x3004,  # equipment info -> WTS-10KW-3P
    10011: 105,  # firmware version
    # -- status --
    10100: (25 << 8) | 8,  # clock: 2025-08
    10101: (12 << 8) | 14,  # clock: day 12, hour 14
    10102: (30 << 8) | 45,  # clock: minute 30, second 45
    10105: 2,  # running status -> ON_GRID
    10112: _u32(0x00010002),  # fault flag 1
    18000: _u32(5),  # ARM fault flag 1
    # -- grid meter --
    10994: _s32(-1000),  # phase A power -> -1000 W (importing)
    10996: _s32(500),  # phase B power
    10998: _s32(250),  # phase C power
    11000: _s32(-250),  # total power
    11002: _u32(1234567),  # grid injection energy -> 12345.67 kWh
    11004: _u32(5000),  # purchasing energy -> 50.0 kWh
    # -- grid port --
    11009: 2301,  # phase A voltage -> 230.1 V
    11010: 55,  # phase A current -> 5.5 A
    11011: 2302,  # phase B voltage -> 230.2 V
    11012: 60,  # phase B current -> 6.0 A
    11013: 2303,  # phase C voltage -> 230.3 V
    11014: 65,  # phase C current -> 6.5 A
    11015: 5001,  # frequency -> 50.01 Hz
    11016: _s32(4200),  # AC power -> 4200 W
    # -- solar --
    11018: _u32(152),  # generation today -> 15.2 kWh
    11020: _u32(98765),  # generation total -> 9876.5 kWh
    11028: _u32(4500),  # PV input total power -> 4500 W
    11038: 3801,  # PV1 voltage -> 380.1 V
    11039: 62,  # PV1 current -> 6.2 A
    11040: 3752,  # PV2 voltage -> 375.2 V
    11041: 58,  # PV2 current -> 5.8 A
    11062: _u32(2350),  # PV1 input power -> 2350 W
    11064: _u32(2150),  # PV2 input power -> 2150 W
    # -- backup / EPS --
    40200: 2295,  # backup A voltage -> 229.5 V
    40201: 43,  # backup A current -> 4.3 A
    40204: _s32(980),  # backup A power -> 980 W
    40230: _s32(980),  # total backup power -> 980 W
    # -- battery --
    40254: 4021,  # voltage -> 402.1 V
    40255: 0xFFF6,  # current -> -1.0 A (signed)
    40256: 0,  # mode -> DISCHARGE
    40258: _s32(-400),  # power -> -400 W
    41108: _u32(12345),  # total charged -> 1234.5 kWh
    41110: _u32(11111),  # total discharged -> 1111.1 kWh
    # -- BMS --
    42000: 1,  # battery type
    42001: 4,  # battery strings
    42002: 2,  # protocol
    42003: 110,  # software version
    42004: 101,  # hardware version
    42005: 500,  # max charge current -> 50.0 A
    42006: 600,  # max discharge current -> 60.0 A
    43000: 8750,  # state of charge -> 87.5 %
    43001: 9900,  # state of health -> 99.0 %
    43002: 3,  # BMS status word
    43003: 235,  # pack temperature -> 23.5 °C
    43009: 246,  # max cell temperature -> 24.6 °C
    43011: 228,  # min cell temperature -> 22.8 °C
    43013: 3345,  # max cell voltage -> 3.345 V
    43015: 3312,  # min cell voltage -> 3.312 V
    43016: _u32(0),  # error code
    43018: _u32(2),  # warning code
    # -- settings --
    25100: 1,  # grid injection limit enabled
    25103: 800,  # grid injection limit -> 80.0 %
    50000: 2,  # working mode -> ECONOMIC
    50001: 1,  # EPS/UPS function on
    50004: 2300,  # off-grid voltage -> 230.0 V
    50005: 5000,  # off-grid frequency -> 50.00 Hz
    50006: 0,  # asymmetric output off
    50007: 0,  # peak load shifting off
    50009: 100,  # max grid power -> 10.0 kVA
    50202: 1,  # AC power setting mode -> TOTAL_POWER
    50210: 0,  # power output priority -> PV
    50211: 10000,  # PV power -> 10000 W
    52502: 1,  # on-grid SOC protection on
    52503: 200,  # on-grid DOD -> 20.0 %
    52504: 0,  # off-grid SOC protection off
    52505: 150,  # off-grid DOD -> 15.0 %
}


@pytest.fixture
def inverter(mock_modbus_unit: MockModbusUnit) -> SunwayInverter:
    """A SunwayInverter over the mock unit, preloaded with device values."""
    mock_modbus_unit.holding.update(HOLDING)
    return SunwayInverter(mock_modbus_unit)
