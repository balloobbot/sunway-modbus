"""Pin the Modbus reads a poll issues, and check each one is justified.

The source integration reads this inverter in blocks of at most 100 registers and
declares no map of which addresses the device serves, so the plan here comes from
the fields themselves: neighbouring addresses merge up to the default 16-register
gap, and nothing is ever read wider than the inverter's 100-register cap.
"""

from __future__ import annotations

from modbus_connection import IllegalDataAddressError
from modbus_connection.mock import MockModbusUnit

from sunway_modbus import Solar, Status, SunwayInverter
from sunway_modbus.model import MAX_READ_SPAN

# (address, count) of every block a full poll issues, in order.
POLL_BLOCKS = [
    (10100, 14),  # status: clock 10100-10102, running status 10105, fault 10112-10113
    (10994, 12),  # meter: four int32 powers + two uint32 energies
    # Grid and solar are adjacent (11017 meets 11018) but are read apart: each
    # component is polled on its own so a failure cannot take the other with it.
    (11009, 9),  # grid: three phase voltage/current pairs, frequency, int32 power
    (11018, 24),  # solar: energy counters, PV total power, the two string pairs
    (11062, 4),  # solar per-string power sits 21 registers above the pair block
    (18000, 2),  # ARM fault flag, alone in its own address region
    (25100, 4),  # grid injection limit: enable flag + limit setting
    (40200, 6),  # backup voltage/current + int32 power
    (40230, 2),  # total backup power, 25 registers above the block before it
    (40254, 6),  # battery voltage/current/mode + int32 power
    (41108, 4),  # battery lifetime energy counters
    (42000, 7),  # BMS identity block, fully contiguous
    (43000, 20),  # BMS live block; 43004-43008 are unclaimed but inside the block
    (50000, 10),  # inverter settings, first block
    (50202, 10),  # AC/PV power settings, 193 registers above the first block
    (52502, 4),  # battery DOD protection
]


async def test_poll_blocks(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    await inverter.async_update()  # first update also sets the device up
    mock_modbus_unit.read_events.clear()

    await inverter.async_update()

    blocks = [(event.address, event.count) for event in mock_modbus_unit.read_events]
    assert blocks == POLL_BLOCKS
    assert all(e.register_type == "holding" for e in mock_modbus_unit.read_events)


async def test_every_field_is_covered_by_a_block(inverter: SunwayInverter) -> None:
    """Every polled field's registers fall inside a block the poll reads."""
    report = await inverter.async_update()
    covered = {
        address
        for start, count in POLL_BLOCKS
        for address in range(start, start + count)
    }
    for polled in report.updated:
        component = getattr(inverter, polled)
        for name, field in component.declared_fields.items():
            span = range(field.address, field.address + field.count)
            missing = [address for address in span if address not in covered]
            assert not missing, f"{type(component).__name__}.{name} misses {missing}"


async def test_no_block_exceeds_the_read_cap(inverter: SunwayInverter) -> None:
    assert all(count <= MAX_READ_SPAN for _, count in POLL_BLOCKS)


async def test_identity_is_read_once(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """The identity block is setup-only; the polling path never reads it again."""
    await inverter.async_update()
    setup_reads = [e.address for e in mock_modbus_unit.read_events]
    assert 10000 in setup_reads

    mock_modbus_unit.read_events.clear()
    await inverter.async_update()
    assert 10000 not in [e.address for e in mock_modbus_unit.read_events]


async def test_solar_splits_at_the_gap(mock_modbus_unit: MockModbusUnit) -> None:
    """The 21-register hole below 11062 is wider than the merge gap, so it splits."""
    await Solar(mock_modbus_unit).async_update()
    assert [(e.address, e.count) for e in mock_modbus_unit.read_events] == [
        (11018, 24),
        (11062, 4),
    ]


async def test_status_block_covers_the_packed_clock(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """The six packed clock fields cost three registers, not six reads."""
    await Status(mock_modbus_unit).async_update()
    assert len(mock_modbus_unit.read_events) == 1


async def test_a_refused_block_drops_only_its_component(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """An inverter without a battery refuses that block; the rest still polls."""
    mock_modbus_unit.fail_read(43000, IllegalDataAddressError())

    report = await inverter.async_update()

    assert "bms" not in report.updated
    assert "bms" not in report.failed  # dropped, not failing: it is simply absent
    assert "grid" in report.updated
    assert inverter.bms.state_of_charge is None
    assert inverter.grid.ac_power == 4200

    mock_modbus_unit.read_events.clear()
    await inverter.async_update()  # the dropped block is never read again
    assert 43000 not in [e.address for e in mock_modbus_unit.read_events]


async def test_raw_dump_covers_the_identity_block_and_every_polled_block(
    inverter: SunwayInverter,
) -> None:
    """A dump carries the setup-only identity block, which a poll never reads."""
    holding = (await inverter.async_read_raw())["holding"]

    assert holding[10008] == 0x3004  # equipment info, read at setup only
    assert {address for address, _ in POLL_BLOCKS} <= set(holding)


async def test_raw_dump_skips_a_sub_system_the_inverter_does_not_serve(
    inverter: SunwayInverter, mock_modbus_unit: MockModbusUnit
) -> None:
    """A dump of an inverter without a BMS is not padded out with refusals."""
    mock_modbus_unit.fail_read(43000, IllegalDataAddressError())

    holding = (await inverter.async_read_raw())["holding"]

    assert 43000 not in holding
    assert 10008 in holding  # identity is still in there
    assert 11009 in holding
