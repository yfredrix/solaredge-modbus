from __future__ import annotations

from dataclasses import dataclass
from typing import Any

from pymodbus.client import ModbusSerialClient, ModbusTcpClient
from pymodbus.exceptions import ModbusException
from pymodbus.pdu import ExceptionResponse

from .models import (
    CommonModel,
    InverterData,
    InverterStatus,
    MpptModelData,
    MpptUnitData,
)
from . import registers as reg


class SolarEdgeModbusError(RuntimeError):
    """Raised for transport and protocol level failures."""


@dataclass(slots=True)
class TransportConfig:
    transport: str
    kwargs: dict[str, Any]


class SolarEdgeModbusClient:
    """Read/write helper for SolarEdge SunSpec mappings over Modbus TCP or RTU."""

    def __init__(self, config: TransportConfig):
        self._config = config
        self._client: ModbusTcpClient | ModbusSerialClient | None = None

    @classmethod
    def tcp(
        cls, host: str, port: int = 1502, timeout: float = 3.0
    ) -> "SolarEdgeModbusClient":
        return cls(
            TransportConfig("tcp", {"host": host, "port": port, "timeout": timeout})
        )

    @classmethod
    def rtu(
        cls,
        port: str,
        baudrate: int = 115200,
        bytesize: int = 8,
        parity: str = "N",
        stopbits: int = 1,
        timeout: float = 1.0,
    ) -> "SolarEdgeModbusClient":
        return cls(
            TransportConfig(
                "rtu",
                {
                    "port": port,
                    "baudrate": baudrate,
                    "bytesize": bytesize,
                    "parity": parity,
                    "stopbits": stopbits,
                    "timeout": timeout,
                },
            )
        )

    def connect(self) -> None:
        if self._client is not None:
            return

        if self._config.transport == "tcp":
            self._client = ModbusTcpClient(**self._config.kwargs)
        elif self._config.transport == "rtu":
            self._client = ModbusSerialClient(**self._config.kwargs)
        else:
            raise SolarEdgeModbusError(
                f"Unsupported transport: {self._config.transport}"
            )

        if not self._client.connect():
            raise SolarEdgeModbusError("Could not connect to Modbus device")

    def close(self) -> None:
        if self._client is not None:
            self._client.close()
            self._client = None

    def __enter__(self) -> "SolarEdgeModbusClient":
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.close()

    def read_holding(self, address: int, count: int, unit: int = 1) -> list[int]:
        self._ensure_connected()
        try:
            response = self._client.read_holding_registers(
                address, count=count, device_id=unit
            )
        except ModbusException as exc:
            raise SolarEdgeModbusError(str(exc)) from exc

        if isinstance(response, ExceptionResponse) or response.isError():
            raise SolarEdgeModbusError(f"Read failed at address {address}: {response}")

        return list(response.registers)

    def write_register(self, address: int, value: int, unit: int = 1) -> None:
        self._ensure_connected()
        try:
            response = self._client.write_register(address, value, device_id=unit)
        except ModbusException as exc:
            raise SolarEdgeModbusError(str(exc)) from exc

        if isinstance(response, ExceptionResponse) or response.isError():
            raise SolarEdgeModbusError(f"Write failed at address {address}: {response}")

    def write_registers(self, address: int, values: list[int], unit: int = 1) -> None:
        self._ensure_connected()
        try:
            response = self._client.write_registers(address, values, device_id=unit)
        except ModbusException as exc:
            raise SolarEdgeModbusError(str(exc)) from exc

        if isinstance(response, ExceptionResponse) or response.isError():
            raise SolarEdgeModbusError(f"Write failed at address {address}: {response}")

    def set_device_address(self, new_unit_id: int, unit: int = 1) -> None:
        if not 1 <= new_unit_id <= 247:
            raise ValueError("new_unit_id must be in range 1..247")
        self.write_register(reg.COMMON_DEVICE_ADDRESS, new_unit_id, unit=unit)

    def read_common_model(self, unit: int = 1) -> CommonModel:
        registers = self.read_holding(reg.COMMON_BASE, 69, unit=unit)
        return CommonModel(
            manufacturer=_decode_string(
                registers, reg.COMMON_MANUFACTURER - reg.COMMON_BASE, 16
            ),
            model=_decode_string(registers, reg.COMMON_MODEL - reg.COMMON_BASE, 16),
            version=_decode_string(registers, reg.COMMON_VERSION - reg.COMMON_BASE, 8),
            serial_number=_decode_string(
                registers, reg.COMMON_SERIAL - reg.COMMON_BASE, 16
            ),
            device_address=_u16(registers[reg.COMMON_DEVICE_ADDRESS - reg.COMMON_BASE]),
        )

    def read_inverter_data(self, unit: int = 1) -> InverterData:
        registers = self.read_holding(reg.INVERTER_BASE, 52, unit=unit)

        current_sf = _s16(registers[reg.INVERTER_AC_CURRENT_SF - reg.INVERTER_BASE])
        voltage_sf = _s16(registers[reg.INVERTER_AC_VOLTAGE_SF - reg.INVERTER_BASE])
        ac_power_sf = _s16(registers[reg.INVERTER_AC_POWER_SF - reg.INVERTER_BASE])
        freq_sf = _s16(registers[reg.INVERTER_AC_FREQUENCY_SF - reg.INVERTER_BASE])
        va_sf = _s16(registers[reg.INVERTER_AC_VA_SF - reg.INVERTER_BASE])
        var_sf = _s16(registers[reg.INVERTER_AC_VAR_SF - reg.INVERTER_BASE])
        pf_sf = _s16(registers[reg.INVERTER_AC_PF_SF - reg.INVERTER_BASE])
        energy_sf = _s16(registers[reg.INVERTER_AC_ENERGY_WH_SF - reg.INVERTER_BASE])
        dc_current_sf = _s16(registers[reg.INVERTER_DC_CURRENT_SF - reg.INVERTER_BASE])
        dc_voltage_sf = _s16(registers[reg.INVERTER_DC_VOLTAGE_SF - reg.INVERTER_BASE])
        dc_power_sf = _s16(registers[reg.INVERTER_DC_POWER_SF - reg.INVERTER_BASE])
        temp_sf = _s16(registers[reg.INVERTER_TEMP_SF - reg.INVERTER_BASE])

        status_raw = _u16(registers[reg.INVERTER_STATUS - reg.INVERTER_BASE])
        try:
            status: InverterStatus | int = InverterStatus(status_raw)
        except ValueError:
            status = status_raw

        vendor32 = _u32(
            registers[reg.INVERTER_STATUS_VENDOR_32 - reg.INVERTER_BASE],
            registers[reg.INVERTER_STATUS_VENDOR_32 - reg.INVERTER_BASE + 1],
        )
        if vendor32 == reg.SUNSPEC_NOT_IMPL_U32:
            vendor32 = None

        return InverterData(
            model_id=_u16(registers[reg.INVERTER_DID - reg.INVERTER_BASE]),
            model_length=_u16(registers[reg.INVERTER_LENGTH - reg.INVERTER_BASE]),
            ac_current_total=_scaled_u16(
                registers, reg.INVERTER_AC_CURRENT, reg.INVERTER_BASE, current_sf
            ),
            ac_current_a=_scaled_u16(
                registers, reg.INVERTER_AC_CURRENT_A, reg.INVERTER_BASE, current_sf
            ),
            ac_current_b=_scaled_u16(
                registers, reg.INVERTER_AC_CURRENT_B, reg.INVERTER_BASE, current_sf
            ),
            ac_current_c=_scaled_u16(
                registers, reg.INVERTER_AC_CURRENT_C, reg.INVERTER_BASE, current_sf
            ),
            ac_voltage_ab=_scaled_u16(
                registers, reg.INVERTER_AC_VOLTAGE_AB, reg.INVERTER_BASE, voltage_sf
            ),
            ac_voltage_bc=_scaled_u16(
                registers, reg.INVERTER_AC_VOLTAGE_BC, reg.INVERTER_BASE, voltage_sf
            ),
            ac_voltage_ca=_scaled_u16(
                registers, reg.INVERTER_AC_VOLTAGE_CA, reg.INVERTER_BASE, voltage_sf
            ),
            ac_voltage_an=_scaled_u16(
                registers, reg.INVERTER_AC_VOLTAGE_AN, reg.INVERTER_BASE, voltage_sf
            ),
            ac_voltage_bn=_scaled_u16(
                registers, reg.INVERTER_AC_VOLTAGE_BN, reg.INVERTER_BASE, voltage_sf
            ),
            ac_voltage_cn=_scaled_u16(
                registers, reg.INVERTER_AC_VOLTAGE_CN, reg.INVERTER_BASE, voltage_sf
            ),
            ac_power_w=_scaled_s16(
                registers, reg.INVERTER_AC_POWER, reg.INVERTER_BASE, ac_power_sf
            ),
            ac_frequency_hz=_scaled_u16(
                registers, reg.INVERTER_AC_FREQUENCY, reg.INVERTER_BASE, freq_sf
            ),
            ac_apparent_power_va=_scaled_s16(
                registers, reg.INVERTER_AC_VA, reg.INVERTER_BASE, va_sf
            ),
            ac_reactive_power_var=_scaled_s16(
                registers, reg.INVERTER_AC_VAR, reg.INVERTER_BASE, var_sf
            ),
            ac_power_factor_pct=_scaled_s16(
                registers, reg.INVERTER_AC_PF, reg.INVERTER_BASE, pf_sf
            ),
            ac_energy_wh=_scaled_u32(
                registers,
                reg.INVERTER_AC_ENERGY_WH,
                reg.INVERTER_BASE,
                energy_sf,
            ),
            dc_current_a=_scaled_u16(
                registers, reg.INVERTER_DC_CURRENT, reg.INVERTER_BASE, dc_current_sf
            ),
            dc_voltage_v=_scaled_u16(
                registers, reg.INVERTER_DC_VOLTAGE, reg.INVERTER_BASE, dc_voltage_sf
            ),
            dc_power_w=_scaled_s16(
                registers, reg.INVERTER_DC_POWER, reg.INVERTER_BASE, dc_power_sf
            ),
            temp_sink_c=_scaled_s16(
                registers, reg.INVERTER_TEMP_SINK, reg.INVERTER_BASE, temp_sf
            ),
            status=status,
            status_vendor_16=_u16(
                registers[reg.INVERTER_STATUS_VENDOR_16 - reg.INVERTER_BASE]
            ),
            status_vendor_32=vendor32,
        )

    def read_mppt_model(self, unit: int = 1) -> MpptModelData:
        header = self.read_holding(reg.MPPT_BASE, 2, unit=unit)
        model_id = _u16(header[0])
        model_length = _u16(header[1])

        if model_id != 160:
            raise SolarEdgeModbusError(
                f"Model at {reg.MPPT_BASE} is {model_id}, expected 160"
            )

        payload = self.read_holding(reg.MPPT_BASE + 2, model_length, unit=unit)
        full_block = header + payload

        dca_sf = _s16(full_block[reg.MPPT_DCA_SF - reg.MPPT_BASE])
        dcv_sf = _s16(full_block[reg.MPPT_DCV_SF - reg.MPPT_BASE])
        dcw_sf = _s16(full_block[reg.MPPT_DCW_SF - reg.MPPT_BASE])
        unit_count = _u16(full_block[reg.MPPT_UNIT_COUNT - reg.MPPT_BASE])

        units: list[MpptUnitData] = []
        for idx in range(unit_count):
            unit_base = reg.MPPT_FIRST_UNIT_BASE + (idx * reg.MPPT_UNIT_BLOCK_SIZE)
            offset = unit_base - reg.MPPT_BASE

            if offset + reg.MPPT_UNIT_BLOCK_SIZE > len(full_block):
                break

            unit_id = _u16(full_block[offset])
            unit_id_str = _decode_string(full_block, offset + 1, 8)
            dca = _scaled_u16_addr(full_block, offset + 9, dca_sf)
            dcv = _scaled_u16_addr(full_block, offset + 10, dcv_sf)
            dcw = _scaled_u16_addr(full_block, offset + 11, dcw_sf)
            tmp = _scaled_s16_addr(full_block, offset + 16, 0)

            units.append(
                MpptUnitData(
                    unit_index=idx,
                    unit_id=unit_id,
                    unit_id_string=unit_id_str,
                    dc_current_a=dca,
                    dc_voltage_v=dcv,
                    dc_power_w=dcw,
                    temperature_c=tmp,
                )
            )

        return MpptModelData(
            model_id=model_id,
            model_length=model_length,
            unit_count=unit_count,
            units=units,
        )

    def _ensure_connected(self) -> None:
        if self._client is None:
            self.connect()


def _u16(value: int) -> int:
    return value & 0xFFFF


def _s16(value: int) -> int:
    value &= 0xFFFF
    if value & 0x8000:
        return value - 0x10000
    return value


def _u32(msw: int, lsw: int) -> int:
    return ((msw & 0xFFFF) << 16) | (lsw & 0xFFFF)


def _decode_string(registers: list[int], start: int, words: int) -> str:
    values = registers[start : start + words]
    raw = bytearray()
    for word in values:
        raw.append((word >> 8) & 0xFF)
        raw.append(word & 0xFF)
    return raw.decode("ascii", errors="ignore").rstrip("\x00 ")


def _apply_sf(raw_value: int, sf: int) -> float:
    return float(raw_value * (10**sf))


def _scaled_u16(registers: list[int], addr: int, base: int, sf: int) -> float | None:
    value = _u16(registers[addr - base])
    if value == reg.SUNSPEC_NOT_IMPL_U16:
        return None
    return _apply_sf(value, sf)


def _scaled_s16(registers: list[int], addr: int, base: int, sf: int) -> float | None:
    raw = _u16(registers[addr - base])
    if raw == reg.SUNSPEC_NOT_IMPL_S16:
        return None
    return _apply_sf(_s16(raw), sf)


def _scaled_u32(registers: list[int], addr: int, base: int, sf: int) -> float | None:
    value = _u32(registers[addr - base], registers[addr - base + 1])
    if value == reg.SUNSPEC_NOT_IMPL_U32:
        return None
    return _apply_sf(value, sf)


def _scaled_u16_addr(block: list[int], offset: int, sf: int) -> float | None:
    value = _u16(block[offset])
    if value == reg.SUNSPEC_NOT_IMPL_U16:
        return None
    return _apply_sf(value, sf)


def _scaled_s16_addr(block: list[int], offset: int, sf: int) -> float | None:
    raw = _u16(block[offset])
    if raw == reg.SUNSPEC_NOT_IMPL_S16:
        return None
    return _apply_sf(_s16(raw), sf)
