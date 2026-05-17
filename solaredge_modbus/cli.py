from __future__ import annotations

import argparse
import json
from typing import Any

from .client import SolarEdgeModbusClient
from .models import CommonModel, InverterData, MpptModelData


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


def main() -> int:
    parser = build_parser()
    args = parser.parse_args()

    client = _build_client(args)
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
