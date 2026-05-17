from __future__ import annotations

from solaredgemodbus2mqtt.solaredge_modbus.models import (
    CommonModel,
    InverterData,
    InverterStatus,
    MpptModelData,
    MpptUnitData,
)
from solaredgemodbus2mqtt.solaredge_modbus.schemas import (
    CommonModelSchema,
    InverterDataSchema,
    MpptModelDataSchema,
)


def test_common_model_schema_from_dataclass() -> None:
    common = CommonModel(
        manufacturer="SolarEdge",
        model="SE5000",
        version="0002.0611",
        serial_number="ABC123",
        device_address=1,
    )

    schema = CommonModelSchema.from_common_model(common)
    assert schema.manufacturer == "SolarEdge"
    assert schema.device_address == 1


def test_inverter_schema_from_dataclass() -> None:
    inverter = InverterData(
        model_id=103,
        model_length=50,
        ac_current_a=10.0,
        ac_current_b=10.1,
        ac_current_c=None,
        ac_current_total=20.1,
        ac_voltage_ab=230.0,
        ac_voltage_bc=None,
        ac_voltage_ca=None,
        ac_voltage_an=230.0,
        ac_voltage_bn=None,
        ac_voltage_cn=None,
        ac_power_w=4500.0,
        ac_frequency_hz=50.0,
        ac_apparent_power_va=4550.0,
        ac_reactive_power_var=120.0,
        ac_power_factor_pct=98.0,
        ac_energy_wh=12345.0,
        dc_current_a=11.0,
        dc_voltage_v=410.0,
        dc_power_w=4510.0,
        temp_sink_c=42.0,
        status=InverterStatus.MPPT,
        status_vendor_16=0,
        status_vendor_32=0,
    )

    schema = InverterDataSchema.from_inverter_data(inverter)
    assert schema.status == "MPPT"
    assert schema.status_code == 4


def test_mppt_schema_from_dataclass() -> None:
    mppt = MpptModelData(
        model_id=160,
        model_length=48,
        unit_count=2,
        units=[
            MpptUnitData(
                unit_index=0,
                unit_id=0,
                unit_id_string="UNIT0",
                dc_current_a=12.3,
                dc_voltage_v=400.0,
                dc_power_w=500.0,
                temperature_c=41.0,
            )
        ],
    )

    schema = MpptModelDataSchema.from_mppt_model(mppt)
    assert schema.unit_count == 2
    assert schema.units[0].unit_id_string == "UNIT0"
