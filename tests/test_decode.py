"""Decode tests: synthetic register words in, typed Python values out."""

from __future__ import annotations

from datetime import datetime

import pytest
from modbus_connection.mock import MockModbusUnit

from sunway_modbus import (
    AcPowerSettingMode,
    BatteryMode,
    PowerOutputPriority,
    RunningStatus,
    Status,
    SunwayInverter,
    WorkingMode,
)


async def test_device_info(inverter: SunwayInverter) -> None:
    await inverter.async_update()
    info = inverter.info
    assert info.manufacturer == "SunWay"
    assert info.serial_number == "SW24000A"
    assert info.model == "WTS-10KW-3P"  # register 10008 = 0x3004
    assert info.firmware_version == 105


@pytest.mark.parametrize(
    ("code", "model"),
    [
        (0x3000, "WTS-4KW-3P"),
        (0x3105, "WTS-6KW-1P"),
        (0x3006, "N/A"),  # a slot the source integration leaves unnamed
        (0x3209, "Unknown"),  # no such hardware code
    ],
)
async def test_equipment_info_decodes_the_model(
    mock_modbus_unit: MockModbusUnit, code: int, model: str
) -> None:
    mock_modbus_unit.holding[10008] = code
    inverter = SunwayInverter(mock_modbus_unit)
    await inverter.info.async_update()
    assert inverter.info.model == model


async def test_status(inverter: SunwayInverter) -> None:
    await inverter.async_update()
    status = inverter.status
    assert status.running_status is RunningStatus.ON_GRID
    assert status.awake is True
    assert status.clock == datetime(2025, 8, 12, 14, 30, 45)
    assert status.fault_flag_1 == 0x00010002
    assert inverter.arm_status.arm_fault_flag_1 == 5


async def test_clock_rejects_an_impossible_date(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    """Month 0 is what a cold-booted inverter reports; it must not raise."""
    mock_modbus_unit.holding.update({10100: 0, 10101: 0, 10102: 0})
    status = Status(mock_modbus_unit)
    await status.async_update()
    assert status.clock is None


async def test_clock_is_none_before_the_first_read(
    mock_modbus_unit: MockModbusUnit,
) -> None:
    assert Status(mock_modbus_unit).clock is None


async def test_meter(inverter: SunwayInverter) -> None:
    await inverter.async_update()
    meter = inverter.meter
    assert meter.phase_a_power == -1000  # signed 32-bit
    assert meter.phase_b_power == 500
    assert meter.phase_c_power == 250
    assert meter.total_power == -250
    assert meter.total_grid_injection_energy == pytest.approx(12345.67)  # 0.01 scale
    assert meter.total_purchasing_energy == pytest.approx(50.0)


async def test_grid(inverter: SunwayInverter) -> None:
    await inverter.async_update()
    grid = inverter.grid
    assert grid.phase_a_voltage == pytest.approx(230.1)
    assert grid.phase_a_current == pytest.approx(5.5)
    assert grid.phase_b_voltage == pytest.approx(230.2)
    assert grid.phase_b_current == pytest.approx(6.0)
    assert grid.phase_c_voltage == pytest.approx(230.3)
    assert grid.phase_c_current == pytest.approx(6.5)
    assert grid.frequency == pytest.approx(50.01)  # 0.01 scale
    assert grid.ac_power == 4200


async def test_solar(inverter: SunwayInverter) -> None:
    await inverter.async_update()
    solar = inverter.solar
    assert solar.generation_today == pytest.approx(15.2)
    assert solar.generation_total == pytest.approx(9876.5)
    assert solar.input_total_power == 4500
    assert solar.pv1_voltage == pytest.approx(380.1)
    assert solar.pv1_current == pytest.approx(6.2)
    assert solar.pv1_input_power == 2350
    assert solar.pv2_voltage == pytest.approx(375.2)
    assert solar.pv2_current == pytest.approx(5.8)
    assert solar.pv2_input_power == 2150


async def test_backup(inverter: SunwayInverter) -> None:
    await inverter.async_update()
    backup = inverter.backup
    assert backup.phase_a_voltage == pytest.approx(229.5)
    assert backup.phase_a_current == pytest.approx(4.3)
    assert backup.phase_a_power == 980
    assert backup.total_power == 980


async def test_battery(inverter: SunwayInverter) -> None:
    await inverter.async_update()
    battery = inverter.battery
    assert battery.voltage == pytest.approx(402.1)
    assert battery.current == pytest.approx(-1.0)  # signed 16-bit
    assert battery.mode is BatteryMode.DISCHARGE
    assert battery.power == -400
    assert inverter.battery_energy.total_charged == pytest.approx(1234.5)
    assert inverter.battery_energy.total_discharged == pytest.approx(1111.1)


async def test_battery_current_is_signed(mock_modbus_unit: MockModbusUnit) -> None:
    """Battery current is the one 16-bit signed register on the device."""
    mock_modbus_unit.holding[40255] = 0x0032
    inverter = SunwayInverter(mock_modbus_unit)
    await inverter.battery.async_update()
    assert inverter.battery.current == pytest.approx(5.0)


async def test_battery_voltage_is_unsigned(mock_modbus_unit: MockModbusUnit) -> None:
    """A high-voltage pack must not fold negative."""
    mock_modbus_unit.holding[40254] = 0x8000
    inverter = SunwayInverter(mock_modbus_unit)
    await inverter.battery.async_update()
    assert inverter.battery.voltage == pytest.approx(3276.8)


async def test_bms(inverter: SunwayInverter) -> None:
    await inverter.async_update()
    info, bms = inverter.bms_info, inverter.bms
    assert info.battery_type == 1
    assert info.battery_strings == 4
    assert info.protocol == 2
    assert info.software_version == 110
    assert info.hardware_version == 101
    assert info.max_charge_current == pytest.approx(50.0)
    assert info.max_discharge_current == pytest.approx(60.0)

    assert bms.state_of_charge == pytest.approx(87.5)  # 0.01 scale
    assert bms.state_of_health == pytest.approx(99.0)
    assert bms.status == 3
    assert bms.pack_temperature == pytest.approx(23.5)
    assert bms.max_cell_temperature == pytest.approx(24.6)
    assert bms.min_cell_temperature == pytest.approx(22.8)
    assert bms.max_cell_voltage == pytest.approx(3.345)  # 0.001 scale
    assert bms.min_cell_voltage == pytest.approx(3.312)
    assert bms.error_code == 0
    assert bms.warning_code == 2


async def test_settings(inverter: SunwayInverter) -> None:
    await inverter.async_update()
    limit = inverter.grid_injection_limit
    assert limit.enabled is True
    assert limit.limit == pytest.approx(80.0)

    settings = inverter.settings
    assert settings.working_mode is WorkingMode.ECONOMIC
    assert settings.eps_ups_function is True
    assert settings.off_grid_voltage == pytest.approx(230.0)
    assert settings.off_grid_frequency == pytest.approx(50.0)
    assert settings.off_grid_asymmetric_output is False
    assert settings.peak_load_shifting is False
    assert settings.max_grid_power == pytest.approx(10.0)
    assert settings.ac_power_setting_mode is AcPowerSettingMode.TOTAL_POWER
    assert settings.power_output_priority is PowerOutputPriority.PV
    assert settings.pv_power == 10000

    protection = inverter.battery_protection
    assert protection.on_grid_soc_protection is True
    assert protection.on_grid_depth_of_discharge == pytest.approx(20.0)
    assert protection.off_grid_soc_protection is False
    assert protection.off_grid_depth_of_discharge == pytest.approx(15.0)


async def test_ems_working_modes_decode(mock_modbus_unit: MockModbusUnit) -> None:
    """The EMS modes use codes well above the plain 1-3 ones."""
    mock_modbus_unit.holding[50000] = 772
    inverter = SunwayInverter(mock_modbus_unit)
    await inverter.settings.async_update()
    assert inverter.settings.working_mode is WorkingMode.EMS_OFF_GRID


async def test_unknown_code_decodes_to_none(mock_modbus_unit: MockModbusUnit) -> None:
    mock_modbus_unit.holding[10105] = 99
    status = Status(mock_modbus_unit)
    await status.async_update()
    assert status.running_status is None
    assert status.awake is False
