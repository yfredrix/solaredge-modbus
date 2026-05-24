from __future__ import annotations

import ssl
from types import SimpleNamespace
from unittest.mock import MagicMock, patch

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


def test_mqtt_config_ssl_defaults() -> None:
    config = MQTTConfig("localhost")
    assert config.ssl_ca_certs is None
    assert config.ssl_certfile is None
    assert config.ssl_keyfile is None
    assert config.ssl_tls_version == ssl.PROTOCOL_TLS_CLIENT
    assert config.ssl_insecure is False


def test_mqtt_config_ssl_fields_stored() -> None:
    config = MQTTConfig(
        broker_host="mqtt.example.com",
        broker_port=8883,
        ssl_ca_certs="/path/to/ca.crt",
        ssl_certfile="/path/to/client.crt",
        ssl_keyfile="/path/to/client.key",
        ssl_insecure=False,
    )
    assert config.ssl_ca_certs == "/path/to/ca.crt"
    assert config.ssl_certfile == "/path/to/client.crt"
    assert config.ssl_keyfile == "/path/to/client.key"
    assert config.ssl_insecure is False


def test_bridge_role_config_propagates_ssl_fields() -> None:
    config = MQTTConfig(
        broker_host="mqtt.example.com",
        broker_port=8883,
        client_id="bridge",
        ssl_ca_certs="/path/to/ca.crt",
        ssl_certfile="/path/to/client.crt",
        ssl_keyfile="/path/to/client.key",
        ssl_insecure=True,
    )
    bridge = MQTTBridge(modbus_client=object(), mqtt_config=config)
    writer_cfg = bridge._role_config("writer")

    assert writer_cfg.ssl_ca_certs == "/path/to/ca.crt"
    assert writer_cfg.ssl_certfile == "/path/to/client.crt"
    assert writer_cfg.ssl_keyfile == "/path/to/client.key"
    assert writer_cfg.ssl_insecure is True
    assert writer_cfg.client_id == "bridge-writer"


def test_connect_calls_tls_set_when_ca_certs_provided() -> None:
    config = MQTTConfig(
        broker_host="mqtt.example.com",
        broker_port=8883,
        ssl_ca_certs="/path/to/ca.crt",
    )
    reader = MQTTReader(config, lambda addr, val: None)

    mock_client = MagicMock()
    mock_client.on_connect = None
    mock_client.on_disconnect = None
    mock_client.on_message = None
    connected_event = MagicMock()
    connected_event.wait.return_value = True

    with patch("paho.mqtt.client.Client", return_value=mock_client):
        reader._connected = connected_event  # type: ignore[assignment]
        try:
            reader.connect()
        except Exception:
            pass

    mock_client.tls_set.assert_called_once_with(
        ca_certs="/path/to/ca.crt",
        certfile=None,
        keyfile=None,
        tls_version=ssl.PROTOCOL_TLS_CLIENT,
    )
    mock_client.tls_insecure_set.assert_not_called()


def test_connect_calls_tls_insecure_set_when_ssl_insecure_true() -> None:
    config = MQTTConfig(
        broker_host="mqtt.example.com",
        broker_port=8883,
        ssl_ca_certs="/path/to/ca.crt",
        ssl_insecure=True,
    )
    reader = MQTTReader(config, lambda addr, val: None)

    mock_client = MagicMock()
    connected_event = MagicMock()
    connected_event.wait.return_value = True

    with patch("paho.mqtt.client.Client", return_value=mock_client):
        reader._connected = connected_event  # type: ignore[assignment]
        try:
            reader.connect()
        except Exception:
            pass

    mock_client.tls_insecure_set.assert_called_once_with(True)


def test_connect_skips_tls_when_no_ssl_config() -> None:
    config = MQTTConfig(broker_host="localhost", broker_port=1883)
    reader = MQTTReader(config, lambda addr, val: None)

    mock_client = MagicMock()
    connected_event = MagicMock()
    connected_event.wait.return_value = True

    with patch("paho.mqtt.client.Client", return_value=mock_client):
        reader._connected = connected_event  # type: ignore[assignment]
        try:
            reader.connect()
        except Exception:
            pass

    mock_client.tls_set.assert_not_called()
    mock_client.tls_insecure_set.assert_not_called()
