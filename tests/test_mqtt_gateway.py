from __future__ import annotations

from types import SimpleNamespace

from solaredgemodbus2mqtt.mqtt.gateway import MQTTBridge, MQTTConfig, MQTTReader


def _message(topic: str, payload: str) -> SimpleNamespace:
    return SimpleNamespace(topic=topic, payload=payload.encode("utf-8"))


def test_mqtt_reader_dispatches_single_and_bulk_writes() -> None:
    writes: list[tuple[int, int | list[int]]] = []
    reader = MQTTReader(
        MQTTConfig("localhost"), lambda address, value: writes.append((address, value)), base_topic="solaredge/modbus/set"
    )

    reader._on_message(None, None, _message("solaredge/modbus/set/register/40245", '{"value": 50}'))  # type: ignore[arg-type]
    reader._on_message(None, None, _message("solaredge/modbus/set/registers/40100", '{"values": [10, 20]}'))  # type: ignore[arg-type]

    assert writes == [(40245, 50), (40100, [10, 20])]


def test_mqtt_reader_rejects_malformed_write_payloads() -> None:
    writes: list[tuple[int, int | list[int]]] = []
    reader = MQTTReader(
        MQTTConfig("localhost"), lambda address, value: writes.append((address, value)), base_topic="solaredge/modbus/set"
    )

    reader._on_message(None, None, _message("solaredge/modbus/set/register/40245", "{}"))  # type: ignore[arg-type]
    reader._on_message(None, None, _message("solaredge/modbus/set/registers/40100", '{"values": []}'))  # type: ignore[arg-type]
    reader._on_message(None, None, _message("solaredge/modbus/set/registers/40100", '{"values": "x"}'))  # type: ignore[arg-type]

    assert writes == []


def test_bridge_publishes_selected_modbus_unit() -> None:
    published: list[tuple[str, dict[str, int], dict[str, int]]] = []
    bridge = MQTTBridge(modbus_client=object(), mqtt_config=MQTTConfig("localhost"), modbus_unit=7)
    bridge._writer = SimpleNamespace(
        publish_model=lambda model_name, data, **kwargs: published.append((model_name, data, kwargs))
    )  # type: ignore[assignment]

    bridge.publish_common_model({"x": 1})

    assert published == [("common", {"x": 1}, {"unit": 7})]


def test_bridge_uses_distinct_client_ids_for_reader_and_writer() -> None:
    bridge = MQTTBridge(modbus_client=object(), mqtt_config=MQTTConfig("localhost", client_id="client"))
    assert bridge._role_config("writer").client_id == "client-writer"
    assert bridge._role_config("reader").client_id == "client-reader"
