from __future__ import annotations

import argparse
import json
import logging
import time
from typing import Any

from .client import SolarEdgeModbusClient
from .models import CommonModel, InverterData, MpptModelData
from ..mqtt import MQTTBridge, MQTTConfig

logging.basicConfig(level=logging.INFO, format="%(asctime)s - %(name)s - %(levelname)s - %(message)s")


def _positive_float(value: str) -> float:
    parsed = float(value)
    if parsed <= 0:
        raise argparse.ArgumentTypeError("must be a positive number")
    return parsed


def build_parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(description="SolarEdge Modbus (SunSpec) utility")
    parser.add_argument("--transport", choices=["tcp", "rtu"], default="tcp")
    parser.add_argument("--unit", type=int, default=1, help="Modbus unit/device ID")
    parser.add_argument("--host", default="127.0.0.1", help="TCP host")
    parser.add_argument("--port", type=int, default=1502, help="TCP port")
    parser.add_argument("--timeout", type=float, default=3.0, help="Socket/serial timeout")

    parser.add_argument("--serial-port", default="COM1", help="RTU serial port")
    parser.add_argument("--baudrate", type=int, default=115200)
    parser.add_argument("--bytesize", type=int, default=8)
    parser.add_argument("--parity", default="N")
    parser.add_argument("--stopbits", type=int, default=1)

    subparsers = parser.add_subparsers(dest="command", required=True)
    mqtt_parser = argparse.ArgumentParser(add_help=False)
    mqtt_parser.add_argument("--mqtt-host", default="127.0.0.1", help="MQTT broker host")
    mqtt_parser.add_argument("--mqtt-port", type=int, default=1883, help="MQTT broker port")
    mqtt_parser.add_argument("--mqtt-username", help="MQTT username")
    mqtt_parser.add_argument("--mqtt-password", help="MQTT password")
    mqtt_parser.add_argument("--mqtt-client-id", default="", help="MQTT client ID")
    mqtt_parser.add_argument("--mqtt-topic", default="solaredge/modbus", help="MQTT base topic")

    subparsers.add_parser("read-common", help="Read SunSpec common model")
    subparsers.add_parser("read-inverter", help="Read inverter model 101/102/103")
    subparsers.add_parser("read-mppt", help="Read MPPT extension model 160")

    read_regs = subparsers.add_parser("read-registers", help="Read raw holding registers")
    read_regs.add_argument("address", type=int, help="Base-0 Modbus address")
    read_regs.add_argument("count", type=int)

    write_reg = subparsers.add_parser("write-register", help="Write one register")
    write_reg.add_argument("address", type=int, help="Base-0 Modbus address")
    write_reg.add_argument("value", type=int)

    write_regs = subparsers.add_parser("write-registers", help="Write multiple registers")
    write_regs.add_argument("address", type=int, help="Base-0 Modbus address")
    write_regs.add_argument("values", nargs="+", type=int)

    set_device = subparsers.add_parser("set-device-address", help="Set C_DeviceAddress")
    set_device.add_argument("new_unit_id", type=int, help="New ID in range 1..247")

    # MQTT commands
    mqtt_pub = subparsers.add_parser("mqtt-publish", parents=[mqtt_parser], help="Publish Modbus values to MQTT")
    mqtt_pub.add_argument("--interval", type=_positive_float, default=30.0, help="Publish interval in seconds")
    mqtt_pub.add_argument(
        "--models", nargs="+", choices=["common", "inverter", "mppt"], default=["inverter"], help="Which models to publish"
    )

    mqtt_listen = subparsers.add_parser("mqtt-listen", parents=[mqtt_parser], help="Listen for MQTT write commands")
    mqtt_listen.add_argument("--timeout", dest="listen_timeout", type=_positive_float, help="How long to listen (seconds)")

    mqtt_bridge = subparsers.add_parser(
        "mqtt-bridge", parents=[mqtt_parser], help="Run bi-directional MQTT bridge (publish + listen)"
    )
    mqtt_bridge.add_argument("--publish-interval", type=_positive_float, default=30.0, help="Publish interval in seconds")
    mqtt_bridge.add_argument(
        "--models", nargs="+", choices=["common", "inverter", "mppt"], default=["inverter"], help="Which models to publish"
    )
    mqtt_bridge.add_argument("--timeout", dest="bridge_timeout", type=_positive_float, help="How long to run (seconds)")

    return parser


def _build_client(args: argparse.Namespace) -> SolarEdgeModbusClient:
    if args.transport == "tcp":
        return SolarEdgeModbusClient.tcp(host=args.host, port=args.port, timeout=args.timeout)

    return SolarEdgeModbusClient.rtu(
        port=args.serial_port,
        baudrate=args.baudrate,
        bytesize=args.bytesize,
        parity=args.parity,
        stopbits=args.stopbits,
        timeout=args.timeout,
    )


def _emit(
    data: CommonModel | InverterData | MpptModelData | dict[str, Any] | list[int],
) -> None:
    if isinstance(data, list):
        print(json.dumps({"registers": data}, indent=2))
        return

    if hasattr(data, "to_dict"):
        print(json.dumps(data.to_dict(), indent=2))
        return

    print(json.dumps(data, indent=2))


def _build_mqtt_config(args: argparse.Namespace) -> MQTTConfig:
    """Build MQTT configuration from arguments."""
    return MQTTConfig(
        broker_host=args.mqtt_host,
        broker_port=args.mqtt_port,
        username=args.mqtt_username,
        password=args.mqtt_password,
        client_id=args.mqtt_client_id,
    )


def _handle_mqtt_publish(client: SolarEdgeModbusClient, args: argparse.Namespace) -> int:
    """Handle mqtt-publish command."""
    mqtt_config = _build_mqtt_config(args)

    client.connect()
    try:
        bridge = MQTTBridge(client, mqtt_config, args.mqtt_topic, modbus_unit=args.unit)
        bridge.start_writer()

        print(f"Publishing to {args.mqtt_host}:{args.mqtt_port} on topic {args.mqtt_topic}")
        print(f"Models: {', '.join(args.models)}")
        print("Press Ctrl+C to stop...\n")

        iteration = 0
        try:
            while True:
                iteration += 1
                try:
                    if "common" in args.models:
                        data = bridge.modbus_call(lambda: client.read_common_model(unit=args.unit))
                        bridge.publish_common_model(data.to_dict())
                        print(f"[{iteration}] Published common model")

                    if "inverter" in args.models:
                        data = bridge.modbus_call(lambda: client.read_inverter_data(unit=args.unit))
                        bridge.publish_inverter_data(data.to_dict())
                        print(f"[{iteration}] Published inverter data")

                    if "mppt" in args.models:
                        data = bridge.modbus_call(lambda: client.read_mppt_model(unit=args.unit))
                        bridge.publish_mppt_data(data.to_dict())
                        print(f"[{iteration}] Published MPPT data")

                    time.sleep(args.interval)
                except Exception as e:
                    print(f"Error reading Modbus: {e}")
                    time.sleep(args.interval)
        except KeyboardInterrupt:
            print("\nStopped")
            return 0
    finally:
        bridge.stop()
        client.close()


def _handle_mqtt_listen(client: SolarEdgeModbusClient, args: argparse.Namespace) -> int:
    """Handle mqtt-listen command."""
    mqtt_config = _build_mqtt_config(args)

    client.connect()
    try:
        bridge = MQTTBridge(client, mqtt_config, args.mqtt_topic, modbus_unit=args.unit)
        reader = bridge.start_reader()

        print(f"Listening on {args.mqtt_host}:{args.mqtt_port}")
        print(f"Subscribe to '{args.mqtt_topic}/set/register/ADDRESS' to write single register")
        print(f"Subscribe to '{args.mqtt_topic}/set/registers/ADDRESS' to write multiple registers")
        print("Press Ctrl+C to stop...\n")

        try:
            reader.wait_for_messages(timeout=args.listen_timeout)
            if args.listen_timeout:
                print(f"\nTimeout after {args.listen_timeout} seconds")
                return 0
        except KeyboardInterrupt:
            print("\nStopped")
            return 0
    finally:
        bridge.stop()
        client.close()


def _handle_mqtt_bridge(client: SolarEdgeModbusClient, args: argparse.Namespace) -> int:
    """Handle mqtt-bridge command."""
    mqtt_config = _build_mqtt_config(args)

    client.connect()
    try:
        bridge = MQTTBridge(client, mqtt_config, args.mqtt_topic, modbus_unit=args.unit)
        bridge.start_writer()
        bridge.start_reader()

        print(f"MQTT Bridge started")
        print(f"Broker: {args.mqtt_host}:{args.mqtt_port}")
        print(f"Base topic: {args.mqtt_topic}")
        print(f"Publishing interval: {args.publish_interval}s")
        print(f"Models: {', '.join(args.models)}")
        print("Press Ctrl+C to stop...\n")

        iteration = 0
        last_publish = time.time()
        start_time = last_publish

        try:
            while True:
                current_time = time.time()

                # Publish on interval
                if current_time - last_publish >= args.publish_interval:
                    iteration += 1
                    try:
                        if "common" in args.models:
                            data = bridge.modbus_call(lambda: client.read_common_model(unit=args.unit))
                            bridge.publish_common_model(data.to_dict())

                        if "inverter" in args.models:
                            data = bridge.modbus_call(lambda: client.read_inverter_data(unit=args.unit))
                            bridge.publish_inverter_data(data.to_dict())

                        if "mppt" in args.models:
                            data = bridge.modbus_call(lambda: client.read_mppt_model(unit=args.unit))
                            bridge.publish_mppt_data(data.to_dict())

                        print(f"[{iteration}] Published data")
                    except Exception as e:
                        print(f"Error reading Modbus: {e}")

                    last_publish = current_time

                if args.bridge_timeout and current_time - start_time >= args.bridge_timeout:
                    print(f"\nTimeout after {args.bridge_timeout} seconds")
                    return 0

                time.sleep(1)
        except KeyboardInterrupt:
            print("\nStopped")
            return 0
    finally:
        bridge.stop()
        client.close()


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    client = _build_client(args)

    # Handle MQTT commands first (they may not need to open/close in same context)
    if args.command == "mqtt-publish":
        return _handle_mqtt_publish(client, args)

    if args.command == "mqtt-listen":
        return _handle_mqtt_listen(client, args)

    if args.command == "mqtt-bridge":
        return _handle_mqtt_bridge(client, args)

    with client:
        if args.command == "read-common":
            _emit(client.read_common_model(unit=args.unit))
            return 0

        if args.command == "read-inverter":
            _emit(client.read_inverter_data(unit=args.unit))
            return 0

        if args.command == "read-mppt":
            _emit(client.read_mppt_model(unit=args.unit))
            return 0

        if args.command == "read-registers":
            _emit(client.read_holding(args.address, args.count, unit=args.unit))
            return 0

        if args.command == "write-register":
            client.write_register(args.address, args.value, unit=args.unit)
            _emit({"ok": True, "address": args.address, "value": args.value})
            return 0

        if args.command == "write-registers":
            client.write_registers(args.address, args.values, unit=args.unit)
            _emit({"ok": True, "address": args.address, "values": args.values})
            return 0

        if args.command == "set-device-address":
            client.set_device_address(args.new_unit_id, unit=args.unit)
            _emit({"ok": True, "new_unit_id": args.new_unit_id})
            return 0

    parser.error(f"Unsupported command: {args.command}")
    return 2


if __name__ == "__main__":
    raise SystemExit(main())
