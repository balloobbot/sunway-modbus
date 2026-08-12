# sunway-modbus

Read and control a **SunWay STT hybrid solar inverter** over Modbus, as typed
Python objects. Built on [modbus-connection](https://github.com/home-assistant-libs/modbus-connection):
the library models the register map, the caller owns the connection.

## Install

```bash
pip install sunway-modbus
```

## Usage

```python
import asyncio

from modbus_connection import ModbusTcpParams
from modbus_connection.tmodbus import ModbusConnection
from sunway_modbus import SunwayInverter, WorkingMode


async def main() -> None:
    connection = ModbusConnection(ModbusTcpParams(host="192.168.1.50", port=502))
    try:
        inverter = SunwayInverter(connection.for_unit(1))
        await inverter.async_update()

        print("Model:", inverter.info.model, inverter.info.serial_number)
        print("Status:", inverter.status.running_status)
        print("PV today:", inverter.solar.generation_today, "kWh")
        print("AC power:", inverter.grid.ac_power, "W")
        print("Battery SOC:", inverter.bms.state_of_charge, "%")

        await inverter.settings.write("working_mode", WorkingMode.ECONOMIC)
    finally:
        await connection.close()


asyncio.run(main())
```

`SunwayInverter` takes a `ModbusUnit`, never a connection or a host — the caller
opens, owns and closes the link with whichever backend it prefers.

## Supported devices

The register map covers the SunWay STT-10KTL hybrid inverter family. Register
10008 identifies the specific product, exposed as `inverter.info.model`:
`WTS-4KW-3P`, `WTS-5KW-3P`, `WTS-6KW-3P`, `WTS-8KW-3P`, `WTS-10KW-3P`,
`WTS-12KW-3P`, and the single-phase `WTS-3KW-1P` … `WTS-8KW-1P`.

**There is only one variant of the register map.** The source integration
declares a single inverter type and applies every entity to it, so this library
does the same: it does not gate fields on model, generation or firmware. On a
single-phase unit the phase B/C registers exist but read as zero, exactly as they
do in the source integration.

Which register blocks are actually polled is settled on the first
`async_update()`: each sub-system is read once, and one the inverter refuses with
an *illegal data address* is dropped from the poll. Its fields keep reading
`None` rather than failing the whole update — the behaviour the source
integration gets from its per-block `ignore_readerror`.

## Sub-systems

| Attribute | Registers | What it holds |
| --- | --- | --- |
| `info` | 10000-10011 | Serial number, model, firmware (read once at setup) |
| `status` | 10100-10113 | Clock, running status, fault flags |
| `arm_status` | 18000-18001 | ARM controller fault flags |
| `meter` | 10994-11005 | External grid meter power and energy |
| `grid` | 11009-11017 | Grid voltage, current, frequency, AC power |
| `solar` | 11018-11065 | PV yield and the two MPPT strings |
| `backup` | 40200-40231 | Backup (EPS/UPS) output |
| `battery` | 40254-40259 | Battery voltage, current, mode, power |
| `battery_energy` | 41108-41111 | Lifetime charge/discharge counters |
| `bms_info` | 42000-42006 | BMS identity and current limits |
| `bms` | 43000-43019 | SOC, SOH, temperatures, cell extremes, codes |
| `grid_injection_limit` | 25100-25103 | Export limitation (writable) |
| `settings` | 50000-50211 | Working mode, off-grid, AC/PV power (writable) |
| `battery_protection` | 52502-52505 | On/off-grid DOD protection (writable) |

Writable fields are written by name, and the ones with a documented range reject
an out-of-range value before it reaches the inverter:

```python
await inverter.battery_protection.write("on_grid_depth_of_discharge", 20.0)
await inverter.grid_injection_limit.write("enabled", True)
await inverter.status.async_sync_time()  # set the inverter's real-time clock
```

## ASCII framing is not supported

This library speaks binary Modbus only — RTU or TCP framing. **ASCII over TCP is
not supported under any circumstance.** The library never constructs a
connection, so there is nothing here that accepts a framer; if you build a
`ModbusConnection` yourself, do not configure it with `framer="ascii"` for TCP.

## Attribution

The register maps are based on
[homeassistant-solax-modbus](https://github.com/wills106/homeassistant-solax-modbus)
(Apache-2.0), specifically its SunWay plugin. This is a derived work and keeps
that licence — see [LICENSE](LICENSE).
