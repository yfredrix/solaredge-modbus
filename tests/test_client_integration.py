from __future__ import annotations

from types import MethodType

import pytest

from solaredge_modbus.client import SolarEdgeModbusClient, TransportConfig
from solaredge_modbus.models import InverterStatus
from solaredge_modbus import registers as reg


def _encode_ascii_words(text: str, words: int) -> list[int]:
    b = text.encode("ascii")
    b = b[: words * 2].ljust(words * 2, b"\x00")
    out: list[int] = []
    for i in range(0, len(b), 2):
        out.append((b[i] << 8) | b[i + 1])
    return out


def _new_client() -> SolarEdgeModbusClient:
    return SolarEdgeModbusClient(TransportConfig("tcp", {"host": "127.0.0.1"}))


def test_read_common_model_parsing() -> None:
    registers = [0] * 69
    registers[
        reg.COMMON_MANUFACTURER
        - reg.COMMON_BASE : reg.COMMON_MANUFACTURER
        - reg.COMMON_BASE
        + 16
    ] = _encode_ascii_words("SolarEdge", 16)
    registers[
        reg.COMMON_MODEL - reg.COMMON_BASE : reg.COMMON_MODEL - reg.COMMON_BASE + 16
    ] = _encode_ascii_words("SE5000", 16)
    registers[
        reg.COMMON_VERSION - reg.COMMON_BASE : reg.COMMON_VERSION - reg.COMMON_BASE + 8
    ] = _encode_ascii_words("0002.0611", 8)
    registers[
        reg.COMMON_SERIAL - reg.COMMON_BASE : reg.COMMON_SERIAL - reg.COMMON_BASE + 16
    ] = _encode_ascii_words("ABC1234567", 16)
    registers[reg.COMMON_DEVICE_ADDRESS - reg.COMMON_BASE] = 1

    client = _new_client()

    def fake_read_holding(self, address: int, count: int, unit: int = 1) -> list[int]:
        assert address == reg.COMMON_BASE
        assert count == 69
        assert unit == 1
        return registers

    client.read_holding = MethodType(fake_read_holding, client)

    common = client.read_common_model()
    assert common.manufacturer == "SolarEdge"
    assert common.model == "SE5000"
    assert common.version == "0002.0611"
    assert common.serial_number == "ABC1234567"
    assert common.device_address == 1


def test_read_inverter_data_parsing() -> None:
    block = [0] * 52

    block[reg.INVERTER_DID - reg.INVERTER_BASE] = 103
    block[reg.INVERTER_LENGTH - reg.INVERTER_BASE] = 50

    block[reg.INVERTER_AC_CURRENT - reg.INVERTER_BASE] = 321
    block[reg.INVERTER_AC_CURRENT_A - reg.INVERTER_BASE] = 111
    block[reg.INVERTER_AC_CURRENT_B - reg.INVERTER_BASE] = 112
    block[reg.INVERTER_AC_CURRENT_C - reg.INVERTER_BASE] = reg.SUNSPEC_NOT_IMPL_U16
    block[reg.INVERTER_AC_CURRENT_SF - reg.INVERTER_BASE] = 0xFFFF  # -1

    block[reg.INVERTER_AC_VOLTAGE_AB - reg.INVERTER_BASE] = 2301
    block[reg.INVERTER_AC_VOLTAGE_SF - reg.INVERTER_BASE] = 0xFFFF  # -1

    block[reg.INVERTER_AC_POWER - reg.INVERTER_BASE] = 5000
    block[reg.INVERTER_AC_POWER_SF - reg.INVERTER_BASE] = 0

    block[reg.INVERTER_AC_FREQUENCY - reg.INVERTER_BASE] = 5000
    block[reg.INVERTER_AC_FREQUENCY_SF - reg.INVERTER_BASE] = 0xFFFE  # -2

    block[reg.INVERTER_AC_ENERGY_WH - reg.INVERTER_BASE] = 0x0000
    block[reg.INVERTER_AC_ENERGY_WH - reg.INVERTER_BASE + 1] = 0x0064
    block[reg.INVERTER_AC_ENERGY_WH_SF - reg.INVERTER_BASE] = 0

    block[reg.INVERTER_DC_CURRENT - reg.INVERTER_BASE] = 120
    block[reg.INVERTER_DC_CURRENT_SF - reg.INVERTER_BASE] = 0xFFFF  # -1
    block[reg.INVERTER_DC_VOLTAGE - reg.INVERTER_BASE] = 398
    block[reg.INVERTER_DC_VOLTAGE_SF - reg.INVERTER_BASE] = 0
    block[reg.INVERTER_DC_POWER - reg.INVERTER_BASE] = 4700
    block[reg.INVERTER_DC_POWER_SF - reg.INVERTER_BASE] = 0

    block[reg.INVERTER_TEMP_SINK - reg.INVERTER_BASE] = 450
    block[reg.INVERTER_TEMP_SF - reg.INVERTER_BASE] = 0xFFFF  # -1

    block[reg.INVERTER_STATUS - reg.INVERTER_BASE] = 4
    block[reg.INVERTER_STATUS_VENDOR_16 - reg.INVERTER_BASE] = 22
    block[reg.INVERTER_STATUS_VENDOR_32 - reg.INVERTER_BASE] = 0x0003
    block[reg.INVERTER_STATUS_VENDOR_32 - reg.INVERTER_BASE + 1] = 0x0123

    client = _new_client()

    def fake_read_holding(self, address: int, count: int, unit: int = 1) -> list[int]:
        assert address == reg.INVERTER_BASE
        assert count == 52
        return block

    client.read_holding = MethodType(fake_read_holding, client)

    inverter = client.read_inverter_data()
    assert inverter.model_id == 103
    assert inverter.model_length == 50
    assert inverter.ac_current_total == pytest.approx(32.1)
    assert inverter.ac_current_a == pytest.approx(11.1)
    assert inverter.ac_current_b == pytest.approx(11.2)
    assert inverter.ac_current_c is None
    assert inverter.ac_voltage_ab == pytest.approx(230.1)
    assert inverter.ac_power_w == pytest.approx(5000.0)
    assert inverter.ac_frequency_hz == pytest.approx(50.0)
    assert inverter.ac_energy_wh == pytest.approx(100.0)
    assert inverter.dc_current_a == pytest.approx(12.0)
    assert inverter.dc_voltage_v == pytest.approx(398.0)
    assert inverter.dc_power_w == pytest.approx(4700.0)
    assert inverter.temp_sink_c == pytest.approx(45.0)
    assert inverter.status == InverterStatus.MPPT
    assert inverter.status_vendor_16 == 22
    assert inverter.status_vendor_32 == 196899


def test_read_mppt_model_parsing() -> None:
    header = [160, 48]
    payload = [0] * 48

    # Fixed block scale factors.
    payload[0] = 0xFFFF  # DCA_SF -1
    payload[1] = 0  # DCV_SF
    payload[2] = 0  # DCW_SF
    payload[6] = 2  # N (unit count)

    # Unit 0 starts at full-block offset 10 -> payload offset 8.
    u0 = 8
    payload[u0] = 0
    payload[u0 + 1 : u0 + 9] = _encode_ascii_words("UNIT0", 8)
    payload[u0 + 9] = 123
    payload[u0 + 10] = 400
    payload[u0 + 11] = 500
    payload[u0 + 16] = 42

    # Unit 1 starts at full-block offset 30 -> payload offset 28.
    u1 = 28
    payload[u1] = 1
    payload[u1 + 1 : u1 + 9] = _encode_ascii_words("UNIT1", 8)
    payload[u1 + 9] = 200
    payload[u1 + 10] = 410
    payload[u1 + 11] = 520
    payload[u1 + 16] = 43

    client = _new_client()

    def fake_read_holding(self, address: int, count: int, unit: int = 1) -> list[int]:
        if address == reg.MPPT_BASE and count == 2:
            return header
        if address == reg.MPPT_BASE + 2 and count == 48:
            return payload
        raise AssertionError(f"Unexpected read {address=} {count=}")

    client.read_holding = MethodType(fake_read_holding, client)

    mppt = client.read_mppt_model()
    assert mppt.model_id == 160
    assert mppt.model_length == 48
    assert mppt.unit_count == 2
    assert len(mppt.units) == 2
    assert mppt.units[0].unit_id_string == "UNIT0"
    assert mppt.units[0].dc_current_a == pytest.approx(12.3)
    assert mppt.units[1].unit_id_string == "UNIT1"
    assert mppt.units[1].dc_power_w == pytest.approx(520.0)
