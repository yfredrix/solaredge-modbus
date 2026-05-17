from __future__ import annotations

import pytest

from solaredgemodbus2mqtt.solaredge_modbus import registers as reg
from solaredgemodbus2mqtt.solaredge_modbus.client import (
    SolarEdgeModbusError,
    SolarEdgeModbusClient,
    TransportConfig,
    _decode_string,
    _s16,
    _scaled_s16,
    _scaled_u16,
    _scaled_u32,
    _u16,
)


def _encode_ascii_words(text: str, words: int) -> list[int]:
    b = text.encode("ascii")
    b = b[: words * 2].ljust(words * 2, b"\x00")
    out: list[int] = []
    for i in range(0, len(b), 2):
        out.append((b[i] << 8) | b[i + 1])
    return out


def test_u16_wraps_values() -> None:
    assert _u16(0x12345) == 0x2345


def test_s16_decodes_negative() -> None:
    assert _s16(0xFFFE) == -2


def test_decode_string_strips_padding() -> None:
    regs = _encode_ascii_words("SolarEdge", 8)
    assert _decode_string(regs, 0, 8) == "SolarEdge"


def test_scaled_u16_applies_scale_factor() -> None:
    regs = [123]
    assert _scaled_u16(regs, addr=100, base=100, sf=-1) == 12.3


def test_scaled_s16_handles_not_implemented() -> None:
    regs = [reg.SUNSPEC_NOT_IMPL_S16]
    assert _scaled_s16(regs, addr=200, base=200, sf=0) is None


def test_scaled_u32_handles_values() -> None:
    # 0x0001_0000 = 65536
    regs = [0x0001, 0x0000]
    assert _scaled_u32(regs, addr=300, base=300, sf=0) == 65536.0


def test_scaled_u16_returns_none_when_sf_not_implemented() -> None:
    regs = [123]
    assert _scaled_u16(regs, addr=100, base=100, sf=_s16(reg.SUNSPEC_NOT_IMPL_S16)) is None


def test_connect_does_not_cache_failed_client(monkeypatch: pytest.MonkeyPatch) -> None:
    created: list[object] = []

    class FakeTcpClient:
        def __init__(self, **kwargs: object) -> None:
            created.append(self)

        def connect(self) -> bool:
            return False

        def close(self) -> None:
            return None

    monkeypatch.setattr("solaredgemodbus2mqtt.solaredge_modbus.client.ModbusTcpClient", FakeTcpClient)
    client = SolarEdgeModbusClient(TransportConfig("tcp", {"host": "127.0.0.1"}))

    with pytest.raises(SolarEdgeModbusError):
        client.connect()
    assert client._client is None
    assert len(created) == 1
