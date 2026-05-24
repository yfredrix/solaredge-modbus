from __future__ import annotations

import pytest

from solaredgemodbus2mqtt.solaredge_modbus.cli import build_parser


def test_mqtt_options_are_accepted_after_subcommand() -> None:
    args = build_parser().parse_args(["mqtt-bridge", "--mqtt-host", "broker", "--mqtt-topic", "solaredge"])
    assert args.command == "mqtt-bridge"
    assert args.mqtt_host == "broker"
    assert args.mqtt_topic == "solaredge"


def test_mqtt_runtime_timeouts_do_not_override_transport_timeout() -> None:
    args = build_parser().parse_args(["mqtt-listen"])
    assert args.timeout == 3.0
    assert args.listen_timeout is None

    bridge_args = build_parser().parse_args(["mqtt-bridge"])
    assert bridge_args.timeout == 3.0
    assert bridge_args.bridge_timeout is None


@pytest.mark.parametrize("command, option", [("mqtt-publish", "--interval"), ("mqtt-bridge", "--publish-interval")])
def test_mqtt_intervals_must_be_positive(command: str, option: str) -> None:
    parser = build_parser()
    with pytest.raises(SystemExit):
        parser.parse_args([command, option, "0"])


def test_mqtt_ssl_options_are_accepted() -> None:
    args = build_parser().parse_args(
        [
            "mqtt-publish",
            "--mqtt-host",
            "mqtt.example.com",
            "--mqtt-port",
            "8883",
            "--mqtt-ca-certs",
            "/path/to/ca.crt",
            "--mqtt-certfile",
            "/path/to/client.crt",
            "--mqtt-keyfile",
            "/path/to/client.key",
        ]
    )
    assert args.mqtt_ca_certs == "/path/to/ca.crt"
    assert args.mqtt_certfile == "/path/to/client.crt"
    assert args.mqtt_keyfile == "/path/to/client.key"
    assert args.mqtt_tls_insecure is False


def test_mqtt_tls_insecure_flag() -> None:
    args = build_parser().parse_args(["mqtt-listen", "--mqtt-tls-insecure"])
    assert args.mqtt_tls_insecure is True


def test_mqtt_ssl_options_default_to_none() -> None:
    args = build_parser().parse_args(["mqtt-publish"])
    assert args.mqtt_ca_certs is None
    assert args.mqtt_certfile is None
    assert args.mqtt_keyfile is None


@pytest.mark.parametrize("command", ["mqtt-publish", "mqtt-listen", "mqtt-bridge"])
def test_mqtt_tls_insecure_without_tls_certs_raises_error(command: str) -> None:
    import sys
    from unittest.mock import patch

    from solaredgemodbus2mqtt.solaredge_modbus.cli import main

    with patch.object(sys, "argv", ["prog", command, "--mqtt-tls-insecure"]):
        with pytest.raises(SystemExit) as exc_info:
            main()
        assert exc_info.value.code == 2
