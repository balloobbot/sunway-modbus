"""Writes: scaling, validators, enum codes, flags and the clock sync."""

from __future__ import annotations

from datetime import datetime

import pytest
from modbus_connection.mock import MockModbusUnit, WriteEvent

from sunway_modbus import PowerOutputPriority, SunwayInverter, WorkingMode


async def test_write_scales_the_value(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    await inverter.battery_protection.write("on_grid_depth_of_discharge", 22.5)
    assert await mock_modbus_unit.read_holding_registers(52503, 1) == [225]


async def test_write_uses_the_hundredths_scale(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    await inverter.settings.write("off_grid_frequency", 49.95)
    assert await mock_modbus_unit.read_holding_registers(50005, 1) == [4995]


async def test_write_an_unscaled_integer(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    await inverter.settings.write("pv_power", 12000)
    assert await mock_modbus_unit.read_holding_registers(50211, 1) == [12000]


async def test_write_an_enum(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    await inverter.settings.write("working_mode", WorkingMode.EMS_BATT_CTRL)
    assert await mock_modbus_unit.read_holding_registers(50000, 1) == [513]

    await inverter.settings.write("power_output_priority", PowerOutputPriority.BATTERY)
    assert await mock_modbus_unit.read_holding_registers(50210, 1) == [1]


async def test_write_a_flag(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """The on/off registers take the whole word as 0 or 1, as the plugin writes them."""
    await inverter.grid_injection_limit.write("enabled", False)
    assert await mock_modbus_unit.read_holding_registers(25100, 1) == [0]

    await inverter.settings.write("peak_load_shifting", True)
    assert await mock_modbus_unit.read_holding_registers(50007, 1) == [1]


async def test_writes_go_out_as_single_register_writes(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    events: list[WriteEvent] = []
    mock_modbus_unit.on_write(events.append)

    await inverter.grid_injection_limit.write("limit", 55.0)

    assert [(e.address, e.values, e.function_code) for e in events] == [
        (25103, [550], 0x06)
    ]


@pytest.mark.parametrize(
    ("component", "field", "value"),
    [
        ("grid_injection_limit", "limit", 100.1),
        ("grid_injection_limit", "limit", -0.1),
        ("settings", "off_grid_voltage", 199.9),
        ("settings", "off_grid_voltage", 250.1),
        ("settings", "off_grid_frequency", 44.9),
        ("settings", "off_grid_frequency", 65.1),
        ("settings", "max_grid_power", 20.1),
        ("settings", "pv_power", 20001),
        ("battery_protection", "on_grid_depth_of_discharge", 100.1),
        ("battery_protection", "off_grid_depth_of_discharge", -1.0),
    ],
)
async def test_out_of_range_write_is_rejected(
    inverter: SunwayInverter,
    mock_modbus_unit: MockModbusUnit,
    component: str,
    field: str,
    value: float,
) -> None:
    """A rejected value never reaches the inverter."""
    events: list[WriteEvent] = []
    mock_modbus_unit.on_write(events.append)

    with pytest.raises(ValueError, match="outside"):
        await getattr(inverter, component).write(field, value)

    assert events == []


@pytest.mark.parametrize(
    ("component", "field", "value"),
    [
        ("grid_injection_limit", "limit", 100.0),
        ("settings", "off_grid_voltage", 200.0),
        ("settings", "off_grid_frequency", 65.0),
        ("settings", "max_grid_power", 0.0),
        ("settings", "pv_power", 20000),
    ],
)
async def test_range_boundaries_are_accepted(
    inverter: SunwayInverter, component: str, field: str, value: float
) -> None:
    await getattr(inverter, component).write(field, value)


async def test_read_only_field_refuses_a_write(inverter: SunwayInverter) -> None:
    with pytest.raises(AttributeError):
        await inverter.grid.write("ac_power", 1)


async def test_sync_time_writes_the_packed_clock(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    events: list[WriteEvent] = []
    mock_modbus_unit.on_write(events.append)

    await inverter.status.async_sync_time(datetime(2025, 8, 12, 14, 30, 45))

    assert len(events) == 1
    event = events[0]
    assert event.address == 20000
    assert event.function_code == 0x10  # one multi-register write, as the plugin does
    assert event.values == [
        (25 << 8) | 8,
        (12 << 8) | 14,
        (30 << 8) | 45,
    ]


async def test_sync_time_round_trips_through_the_read_registers(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """The write layout matches the read layout, one address block apart."""
    moment = datetime(2031, 12, 31, 23, 59, 59)
    await inverter.status.async_sync_time(moment)

    written = await mock_modbus_unit.read_holding_registers(20000, 3)
    mock_modbus_unit.holding.update(
        dict(zip([10100, 10101, 10102], written, strict=True))
    )
    await inverter.status.async_update()
    assert inverter.status.clock == moment
