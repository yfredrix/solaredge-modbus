from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field

from .models import CommonModel, InverterData, MpptModelData, MpptUnitData


class CommonModelSchema(BaseModel):
    """Validated common SunSpec block values."""

    model_config = ConfigDict(extra="forbid")

    manufacturer: str = Field(description="Inverter manufacturer")
    model: str = Field(description="Inverter model")
    version: str = Field(description="Inverter firmware/software version")
    serial_number: str = Field(description="Inverter serial number")
    device_address: int = Field(ge=1, le=247, description="Modbus unit/device address")

    @classmethod
    def from_common_model(cls, value: CommonModel) -> "CommonModelSchema":
        return cls.model_validate(value.to_dict())


class InverterDataSchema(BaseModel):
    """Validated inverter model 101/102/103 data with scale factors applied."""

    model_config = ConfigDict(extra="forbid")

    model_id: int = Field(description="SunSpec model ID: 101, 102, or 103")
    model_length: int = Field(description="Model block length in registers")

    ac_current_a: float | None = Field(description="AC phase A current in A")
    ac_current_b: float | None = Field(description="AC phase B current in A")
    ac_current_c: float | None = Field(description="AC phase C current in A")
    ac_current_total: float | None = Field(description="Total AC current in A")

    ac_voltage_ab: float | None = Field(description="AC voltage AB in V")
    ac_voltage_bc: float | None = Field(description="AC voltage BC in V")
    ac_voltage_ca: float | None = Field(description="AC voltage CA in V")
    ac_voltage_an: float | None = Field(description="AC voltage AN in V")
    ac_voltage_bn: float | None = Field(description="AC voltage BN in V")
    ac_voltage_cn: float | None = Field(description="AC voltage CN in V")

    ac_power_w: float | None = Field(description="AC real power in W")
    ac_frequency_hz: float | None = Field(description="AC frequency in Hz")
    ac_apparent_power_va: float | None = Field(description="AC apparent power in VA")
    ac_reactive_power_var: float | None = Field(description="AC reactive power in VAR")
    ac_power_factor_pct: float | None = Field(description="AC power factor in percent")
    ac_energy_wh: float | None = Field(description="Lifetime AC energy in Wh")

    dc_current_a: float | None = Field(description="DC current in A")
    dc_voltage_v: float | None = Field(description="DC voltage in V")
    dc_power_w: float | None = Field(description="DC power in W")
    temp_sink_c: float | None = Field(description="Heat sink temperature in C")

    status: str | int = Field(description="Inverter operating state name/code")
    status_code: int | None = Field(default=None, description="Status code when status is name")
    status_vendor_16: int = Field(description="Vendor status/error (16-bit)")
    status_vendor_32: int | None = Field(description="Vendor status/error (32-bit)")

    @classmethod
    def from_inverter_data(cls, value: InverterData) -> "InverterDataSchema":
        return cls.model_validate(value.to_dict())


class MpptUnitDataSchema(BaseModel):
    """Validated model 160 unit-level values."""

    model_config = ConfigDict(extra="forbid")

    unit_index: int = Field(ge=0, description="0-based unit index")
    unit_id: int = Field(description="Synergy unit ID")
    unit_id_string: str = Field(description="Synergy unit string ID")
    dc_current_a: float | None = Field(description="Unit DC current in A")
    dc_voltage_v: float | None = Field(description="Unit DC voltage in V")
    dc_power_w: float | None = Field(description="Unit DC power in W")
    temperature_c: float | None = Field(description="Unit temperature in C")

    @classmethod
    def from_mppt_unit(cls, value: MpptUnitData) -> "MpptUnitDataSchema":
        return cls.model_validate(value.to_dict())


class MpptModelDataSchema(BaseModel):
    """Validated model 160 MPPT block values."""

    model_config = ConfigDict(extra="forbid")

    model_id: int = Field(description="SunSpec model ID")
    model_length: int = Field(description="Model block length in registers")
    unit_count: int = Field(ge=0, le=3, description="Number of Synergy units")
    units: list[MpptUnitDataSchema] = Field(default_factory=list)

    @classmethod
    def from_mppt_model(cls, value: MpptModelData) -> "MpptModelDataSchema":
        return cls.model_validate(value.to_dict())
