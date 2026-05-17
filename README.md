# SolarEdge Modbus Module with MQTT sender/receiver

Python module and CLI for reading SolarEdge SunSpec Modbus data and writing setting registers when needed.

MQTT gateway documentation:
- [MQTT.md](MQTT.md)
- [MQTT_QUICKSTART.md](MQTT_QUICKSTART.md)

Implementation is based on the spec file in this repository:

- `sunspec-implementation-technical-note.pdf` (Version 3.2, June 2025)

Supported model blocks:

- Common model block (base-0 `40000`)
- Inverter model `101/102/103` (base-0 `40069`)
- Multiple MPPT model `160` (base-0 `40121`)

## Install

```bash
uv sync
```

## CLI Usage

The CLI uses base-0 Modbus addresses, as in protocol address format.

Read common model over TCP:

```bash
uv run python main.py --transport tcp --host 192.168.1.50 --port 1502 --unit 1 read-common
```

Read inverter metrics:

```bash
uv run python main.py --transport tcp --host 192.168.1.50 --port 1502 --unit 1 read-inverter
```

Read MPPT extension model 160:

```bash
uv run python main.py --transport tcp --host 192.168.1.50 --port 1502 --unit 1 read-mppt
```

Read raw registers:

```bash
uv run python main.py --transport tcp --host 192.168.1.50 --port 1502 --unit 1 read-registers 40069 52
```

Write a single register (use carefully):

```bash
uv run python main.py --transport tcp --host 192.168.1.50 --port 1502 --unit 1 write-register 40068 2
```

Set `C_DeviceAddress` (valid range `1..247`):

```bash
uv run python main.py --transport tcp --host 192.168.1.50 --port 1502 --unit 1 set-device-address 2
```

RTU example:

```bash
uv run python main.py --transport rtu --serial-port COM3 --baudrate 115200 --unit 1 read-inverter
```

## Python Module Usage

```python
from solaredgemodbus2mqtt.solaredge_modbus.client import SolarEdgeModbusClient

with SolarEdgeModbusClient.tcp("192.168.1.50", port=1502, timeout=3.0) as client:
	common = client.read_common_model(unit=1)
	inverter = client.read_inverter_data(unit=1)

	print(common.to_dict())
	print(inverter.to_dict())

	# Optional write operation for supported setting registers.
	# Example: set C_DeviceAddress
	# client.set_device_address(new_unit_id=2, unit=1)
```

## Notes

- Scale factors are applied to values according to SunSpec rules.
- Not-implemented values are returned as `None` where relevant.
- Write operations are available, but whether a specific register is writable depends on device firmware/configuration.

## Pydantic Schemas

The package includes Pydantic models to validate and describe parsed data fields:

- `CommonModelSchema`
- `InverterDataSchema`
- `MpptUnitDataSchema`
- `MpptModelDataSchema`

Example:

```python
from solaredgemodbus2mqtt.solaredge_modbus.client import SolarEdgeModbusClient
from solaredgemodbus2mqtt.solaredge_modbus.schemas import InverterDataSchema

with SolarEdgeModbusClient.tcp("192.168.1.50", port=1502) as client:
	inverter = client.read_inverter_data(unit=1)
	validated = InverterDataSchema.from_inverter_data(inverter)
	print(validated.model_dump())
```

## Testing

Install dev dependencies and run tests:

```bash
uv sync --group dev
uv run pytest -q
```

Test layout:

- `tests/test_parsing_unit.py`: unit tests for low-level parsing and scale factor handling
- `tests/test_client_integration.py`: integration-style parsing tests with mocked Modbus reads
- `tests/test_schemas.py`: Pydantic validation tests
