#!/usr/bin/env python3

"""Query a SunWay inverter and print every value.

Reads one inverter once and dumps it to the terminal — the quickest way to check
real hardware with no application around it.

::

    uv run script/query.py /dev/ttyUSB0 --transport serial --unit 1
    uv run script/query.py 192.168.1.50 --transport tcp --unit 1 --framer rtu
"""

from __future__ import annotations

import argparse
import asyncio

from modbus_connection import ModbusError
from modbus_connection.cli_helper import (
    CountingUnit,
    add_connection_args,
    connect_from_args,
    print_component,
)
from modbus_connection.model import Component

from sunway_modbus import SunwayInverter

# The inverter is RS-485 RTU; over TCP it is reached through a gateway, which
# presents it either transparently (rtu) or as native Modbus TCP (socket).
CONNECTIONS = (("serial", "rtu"), ("tcp", "rtu"), ("tcp", "socket"))


def sub_systems(inverter: SunwayInverter) -> list[tuple[str, Component]]:
    """The polled components, in declaration order.

    All of them are built whether or not this inverter serves them, so the set
    is fixed and the update report is what says which ones answered.
    """
    return [
        (name, value)
        for name, value in vars(inverter).items()
        if isinstance(value, Component) and name != "info"
    ]


async def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    add_connection_args(parser, connections=CONNECTIONS)
    parser.add_argument("--unit", type=int, default=1, help="Modbus unit id")
    args = parser.parse_args()

    try:
        connection = await connect_from_args(args)
    except ModbusError as err:
        print(f"Could not connect: {err}")
        return 1

    counting = CountingUnit(connection.for_unit(args.unit))
    inverter = SunwayInverter(counting)
    try:
        report = await inverter.async_update()  # the first call is the setup probe
    except ModbusError as err:
        print(f"Could not read the inverter: {err}")
        return 1
    finally:
        await connection.close()

    print_component(inverter.info, title="Device information")

    refused = []
    for name, component in sub_systems(inverter):
        if name in report.updated:
            print()
            print_component(component, title=name)
        elif name not in report.failed:
            refused.append(name)

    # Naming a refused sub-system is how you tell a model this inverter lacks
    # from one that is merely mis-addressed. Its fields are all None, so they
    # stay out: printed, they would read as measurements that came back empty.
    if refused:
        print(f"\nNot served by this inverter: {', '.join(refused)}")

    if report.failed:
        print("\nFailed to read")
        print("--------------")
        for name, error in sorted(report.failed.items()):
            print(f"  {name}: {error}")

    print(f"\n{counting.reads} Modbus reads")
    return 0


raise SystemExit(asyncio.run(main()))
