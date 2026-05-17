from __future__ import annotations

from dataclasses import asdict, dataclass
from enum import IntEnum
from typing import Any


class InverterStatus(IntEnum):
    OFF = 1
    SLEEPING = 2
    STARTING = 3
    MPPT = 4
    THROTTLED = 5
    SHUTTING_DOWN = 6
    FAULT = 7
    STANDBY = 8


@dataclass(slots=True)
class CommonModel:
    manufacturer: str
    model: str
    version: str
    serial_number: str
    device_address: int

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class InverterData:
    model_id: int
    model_length: int
    ac_current_a: float | None
    ac_current_b: float | None
    ac_current_c: float | None
    ac_current_total: float | None
    ac_voltage_ab: float | None
    ac_voltage_bc: float | None
    ac_voltage_ca: float | None
    ac_voltage_an: float | None
    ac_voltage_bn: float | None
    ac_voltage_cn: float | None
    ac_power_w: float | None
    ac_frequency_hz: float | None
    ac_apparent_power_va: float | None
    ac_reactive_power_var: float | None
    ac_power_factor_pct: float | None
    ac_energy_wh: float | None
    dc_current_a: float | None
    dc_voltage_v: float | None
    dc_power_w: float | None
    temp_sink_c: float | None
    status: InverterStatus | int
    status_vendor_16: int
    status_vendor_32: int | None

    def to_dict(self) -> dict[str, Any]:
        data = asdict(self)
        if isinstance(self.status, InverterStatus):
            data["status"] = self.status.name
            data["status_code"] = int(self.status)
        return data


@dataclass(slots=True)
class MpptUnitData:
    unit_index: int
    unit_id: int
    unit_id_string: str
    dc_current_a: float | None
    dc_voltage_v: float | None
    dc_power_w: float | None
    temperature_c: float | None

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)


@dataclass(slots=True)
class MpptModelData:
    model_id: int
    model_length: int
    unit_count: int
    units: list[MpptUnitData]

    def to_dict(self) -> dict[str, Any]:
        return {
            "model_id": self.model_id,
            "model_length": self.model_length,
            "unit_count": self.unit_count,
            "units": [unit.to_dict() for unit in self.units],
        }
