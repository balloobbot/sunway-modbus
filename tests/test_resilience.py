"""One failing block must not take the rest of the poll with it.

The source integration reads its blocks independently and tolerates a failure:
the failing block's sensors keep their last values while everything else
refreshes. The library mirrors that at component granularity, both in the poll
and in the setup probe that settles which sub-systems the inverter serves.
"""

from __future__ import annotations

import pytest
from modbus_connection import (
    IllegalDataAddressError,
    IllegalFunctionError,
    ModbusConnectionError,
    ModbusTimeoutError,
)
from modbus_connection.mock import MockModbusUnit

from sunway_modbus import SunwayInverter


async def test_a_failed_component_leaves_the_rest_fresh(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    await inverter.async_update()
    before = inverter.grid.ac_power

    mock_modbus_unit.holding[11016] = [0, 5000]  # AC power changes on the device
    mock_modbus_unit.holding[11018] = [0, 200]  # so does today's solar generation
    mock_modbus_unit.fail_read(11009, ModbusTimeoutError("slow grid block"))
    report = await inverter.async_update()

    assert not report.complete
    assert set(report.failed) == {"grid"}
    assert isinstance(report.failed["grid"], ModbusTimeoutError)
    assert "solar" in report.updated
    assert inverter.grid.ac_power == before
    assert inverter.solar.generation_today == 20.0


async def test_listeners_fire_at_the_end_and_only_for_fresh_components(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    await inverter.async_update()
    seen: list[int] = []
    inverter.solar.add_update_listener(
        lambda: seen.append(len(mock_modbus_unit.read_events))
    )
    inverter.grid.add_update_listener(lambda: seen.append(-1))

    mock_modbus_unit.fail_read(11009, ModbusTimeoutError("slow grid block"))
    mock_modbus_unit.read_events.clear()
    await inverter.async_update()

    # One notification, after every measurement was tried; none for the failure.
    # The settings poll that follows is its own, and does not hold it up.
    settings_start = next(
        i
        for i, event in enumerate(mock_modbus_unit.read_events)
        if event.address == 25100
    )
    assert seen == [settings_start]


async def test_a_dead_link_raises_instead_of_reporting(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    await inverter.async_update()
    mock_modbus_unit.fail_requests(ModbusConnectionError("link down"))
    with pytest.raises(ModbusConnectionError):
        await inverter.async_update()


async def test_every_component_refreshes_on_a_healthy_device(
    inverter: SunwayInverter,
) -> None:
    await inverter.async_update()
    report = await inverter.async_update()
    assert report.complete
    assert report.failed == {}
    assert {"status", "grid", "solar", "bms", "settings"} <= report.updated
    assert "info" not in report.updated  # identity is read at setup, not polled


async def test_a_sleeping_device_raises_on_the_first_timeout(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """A device that answers nothing is not walked sub-system by sub-system.

    Nothing refreshed and nothing refused either, so the first timeout ends the
    poll instead of paying one timeout per block on an inverter that is asleep.
    """
    await inverter.async_update()

    mock_modbus_unit.fail_requests(ModbusTimeoutError("no answer"))
    mock_modbus_unit.read_events.clear()

    with pytest.raises(ModbusTimeoutError):
        await inverter.async_update()

    assert len(mock_modbus_unit.read_events) == 1


async def test_a_settings_poll_of_a_sleeping_device_raises_at_once(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """A standalone settings poll is its own "nothing answered" run."""
    await inverter.async_update()

    mock_modbus_unit.fail_requests(ModbusTimeoutError("no answer"))
    mock_modbus_unit.read_events.clear()

    with pytest.raises(ModbusTimeoutError):
        await inverter.async_update_settings()

    assert len(mock_modbus_unit.read_events) == 1


async def test_a_slow_block_during_setup_keeps_its_component_polled(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """A timeout says nothing about the register map, so nothing is dropped."""
    mock_modbus_unit.fail_read(43000, ModbusTimeoutError("slow BMS block"))
    setup = await inverter.async_update()

    assert set(setup.failed) == {"bms"}
    assert inverter.bms.state_of_charge is None

    mock_modbus_unit.fail_read(43000, None)
    report = await inverter.async_update()

    assert report.complete
    assert "bms" in report.updated
    assert inverter.bms.state_of_charge == 87.5


async def test_the_first_block_timing_out_during_setup_is_not_fatal(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """The probe must still try every sub-system, even if the first is silent.

    The poll stops on a timeout nothing answered before; setup may not, or a
    slow first block would leave the inverter unset up.
    """
    mock_modbus_unit.fail_read(10100, ModbusTimeoutError("slow status block"))
    setup = await inverter.async_update()

    assert set(setup.failed) == {"status"}
    assert "grid" in setup.updated  # the probe carried on past the silent block

    mock_modbus_unit.fail_read(10100, None)
    assert (await inverter.async_update()).complete


async def test_a_refused_function_during_setup_drops_only_its_component(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """An illegal function is a refusal like an illegal address, not an abort."""
    mock_modbus_unit.fail_read(43000, IllegalFunctionError())
    report = await inverter.async_update()

    assert report.complete  # a dropped sub-system is absent, not failing
    assert "bms" not in report.updated
    assert inverter.bms.state_of_charge is None
    assert inverter.grid.ac_power == 4200

    mock_modbus_unit.read_events.clear()
    await inverter.async_update()
    assert 43000 not in [event.address for event in mock_modbus_unit.read_events]


async def test_a_refusal_after_setup_does_not_poison_later_polls(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """A block that starts refusing is contained, and recovers when it stops."""
    await inverter.async_update()

    mock_modbus_unit.fail_read(11009, IllegalDataAddressError())
    report = await inverter.async_update()
    assert set(report.failed) == {"grid"}
    assert "solar" in report.updated

    mock_modbus_unit.fail_read(11009, None)
    mock_modbus_unit.holding[11016] = [0, 5000]
    assert (await inverter.async_update()).complete
    assert inverter.grid.ac_power == 5000


async def test_a_failed_setup_raises_and_retries(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """Identity is the poll's foundation; without it there is nothing partial."""
    mock_modbus_unit.fail_read(10000, ModbusTimeoutError("no identity"))
    with pytest.raises(ModbusTimeoutError):
        await inverter.async_update()

    mock_modbus_unit.fail_read(10000, None)
    report = await inverter.async_update()

    assert report.complete
    assert inverter.info.serial_number == "SW24000A"
