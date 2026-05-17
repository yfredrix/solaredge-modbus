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
