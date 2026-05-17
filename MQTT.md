# MQTT Gateway Integration

The SolarEdge Modbus project now includes MQTT gateway functionality for publishing Modbus values and receiving commands to set values over MQTT.

## Features

- **MQTT Writer**: Publish Modbus register values and model data to MQTT topics
- **MQTT Reader**: Subscribe to MQTT topics and set Modbus register values
- **MQTT Bridge**: Bi-directional synchronization between Modbus and MQTT

## Installation

The MQTT functionality requires the `paho-mqtt` package, which is included in the project dependencies:

```bash
uv sync
```

## Usage

### Environment Variables

All MQTT commands support the following options:

- `--mqtt-host`: MQTT broker hostname (default: `127.0.0.1`)
- `--mqtt-port`: MQTT broker port (default: `1883`)
- `--mqtt-username`: MQTT broker username (optional)
- `--mqtt-password`: MQTT broker password (optional)
- `--mqtt-client-id`: MQTT client ID (default: `solaredge-modbus`)
- `--mqtt-topic`: Base MQTT topic (default: `solaredge/modbus`)

Plus all standard Modbus connection options (`--transport`, `--host`, `--port`, `--serial-port`, etc.)

### Commands

#### 1. Publish Modbus Data to MQTT

Continuously publish Modbus values to MQTT:

```bash
solaredge-modbus mqtt-publish \
  --mqtt-host mqtt.example.com \
  --mqtt-topic solaredge \
  --interval 30 \
  --models inverter mppt common
```

**Options:**
- `--interval`: Publish interval in seconds (default: 30)
- `--models`: Which models to publish: `common`, `inverter`, `mppt` (default: `inverter`)

**Published Topics:**
- `solaredge/inverter`: Inverter AC/DC data
- `solaredge/mppt`: MPPT extension data
- `solaredge/common`: Common device info

#### 2. Listen for MQTT Write Commands

Listen for commands to set Modbus registers:

```bash
solaredge-modbus mqtt-listen \
  --mqtt-host mqtt.example.com \
  --mqtt-topic solaredge
```

**Options:**
- `--timeout`: Duration to listen in seconds (optional)

**Subscription Topics:**
- `solaredge/set/register/ADDRESS`: Write single register
  - Payload: `{"value": 100}`
  
- `solaredge/set/registers/ADDRESS`: Write multiple registers
  - Payload: `{"values": [100, 200, 300]}`

**Example:**
```bash
# Send to MQTT
mosquitto_pub -h mqtt.example.com -t "solaredge/set/register/40245" -m '{"value": 50}'
```

#### 3. Run Bi-directional Bridge

Run both publisher and listener simultaneously:

```bash
solaredge-modbus mqtt-bridge \
  --mqtt-host mqtt.example.com \
  --mqtt-topic solaredge \
  --publish-interval 30 \
  --models inverter mppt common
```

**Options:**
- `--publish-interval`: How often to publish data (default: 30s)
- `--models`: Which models to publish
- `--timeout`: Total runtime in seconds (optional)

## Topic Structure

### Publishing (Writer)

```
solaredge/
├── common/          # Common device model
│   ├── model
│   ├── data
│   └── timestamp
├── inverter/        # Inverter data
│   ├── data: {...}  # All inverter metrics
│   └── timestamp
├── mppt/            # MPPT extension data
│   ├── data: {...}  # MPPT metrics
│   └── timestamp
└── registers/raw/   # Raw register data
    ├── address
    ├── values: [...]
    └── timestamp
```

### Subscribing (Reader)

```
solaredge/set/
├── register/ADDRESS       # Write single register
│   └── {"value": 12345}
└── registers/ADDRESS      # Write multiple registers
    └── {"values": [100, 200, 300]}
```

## Payload Format

### Single Register Write

Topic: `solaredge/set/register/40245`

```json
{
  "value": 50
}
```

### Multiple Registers Write

Topic: `solaredge/set/registers/40100`

```json
{
  "values": [100, 200, 300, 400]
}
```

### Published Inverter Data

Topic: `solaredge/inverter`

```json
{
  "model": "inverter",
  "data": {
    "model_id": 101,
    "ac_current_total": 12.5,
    "ac_voltage_ab": 400.2,
    "ac_power_w": 5000,
    ...
  },
  "unit": 1,
  "timestamp": 1234567890.123
}
```

## Python API

You can also use the MQTT gateway directly in Python:

### MQTT Writer

```python
from solaredge_modbus.client import SolarEdgeModbusClient
from solaredge_modbus.mqtt_gateway import MQTTWriter, MQTTConfig

# Create client and connect
client = SolarEdgeModbusClient.tcp("127.0.0.1")
client.connect()

# Create MQTT writer
mqtt_config = MQTTConfig(broker_host="mqtt.example.com")
writer = MQTTWriter(mqtt_config, base_topic="solaredge")
writer.connect()

# Publish data
inverter_data = client.read_inverter_data()
writer.publish_model("inverter", inverter_data.to_dict())

writer.disconnect()
client.close()
```

### MQTT Reader

```python
from solaredge_modbus.mqtt_gateway import MQTTReader, MQTTConfig

client = SolarEdgeModbusClient.tcp("127.0.0.1")
client.connect()

def write_callback(address: int, value: int | list[int]) -> None:
    if isinstance(value, list):
        client.write_registers(address, value)
    else:
        client.write_register(address, value)

mqtt_config = MQTTConfig(broker_host="mqtt.example.com")
reader = MQTTReader(mqtt_config, write_callback, base_topic="solaredge/set")
reader.connect()

reader.wait_for_messages(timeout=60)

reader.disconnect()
client.close()
```

### MQTT Bridge

```python
from solaredge_modbus.mqtt_gateway import MQTTBridge, MQTTConfig

client = SolarEdgeModbusClient.tcp("127.0.0.1")
client.connect()

mqtt_config = MQTTConfig(broker_host="mqtt.example.com")
bridge = MQTTBridge(client, mqtt_config, base_topic="solaredge")

# Start both writer and reader
writer = bridge.start_writer()
reader = bridge.start_reader()

# Publish data
inverter_data = client.read_inverter_data()
bridge.publish_inverter_data(inverter_data.to_dict())

# Wait for messages
reader.wait_for_messages(timeout=60)

bridge.stop()
client.close()
```

## Error Handling

All MQTT operations can raise `MQTTError` exceptions:

```python
from solaredge_modbus.mqtt_gateway import MQTTError

try:
    writer = MQTTWriter(mqtt_config)
    writer.connect()
except MQTTError as e:
    print(f"MQTT connection failed: {e}")
```

## Logging

Enable debug logging to see MQTT activity:

```python
import logging

logging.basicConfig(level=logging.DEBUG)
```

## Examples

### Docker Compose Setup with Mosquitto

```yaml
version: '3.8'

services:
  mosquitto:
    image: eclipse-mosquitto:latest
    ports:
      - "1883:1883"
    volumes:
      - ./mosquitto.conf:/mosquitto/config/mosquitto.conf

  solaredge:
    image: python:3.12
    command: >
      bash -c "pip install paho-mqtt pymodbus pydantic &&
               solaredge-modbus mqtt-bridge
               --mqtt-host mosquitto
               --mqtt-topic solaredge
               --publish-interval 30
               --models inverter mppt"
    depends_on:
      - mosquitto
    environment:
      PYTHONUNBUFFERED: 1
```

### Monitor with `mosquitto_sub`

```bash
# Subscribe to all inverter updates
mosquitto_sub -h mqtt.example.com -t "solaredge/inverter" -v

# Subscribe to all topics
mosquitto_sub -h mqtt.example.com -t "solaredge/#" -v
```

### Control via `mosquitto_pub`

```bash
# Set register 40245 to value 50
mosquitto_pub -h mqtt.example.com \
  -t "solaredge/set/register/40245" \
  -m '{"value": 50}'

# Set registers starting at 40100 with multiple values
mosquitto_pub -h mqtt.example.com \
  -t "solaredge/set/registers/40100" \
  -m '{"values": [10, 20, 30]}'
```

## Troubleshooting

### Connection Refused

- Ensure MQTT broker is running on the specified host and port
- Check firewall rules
- Verify credentials if authentication is enabled

### Messages Not Being Received

- Check topic subscriptions match the base topic
- Verify MQTT QoS settings
- Enable debug logging to see message flow

### Slow Updates

- Increase publish interval if system is overloaded
- Reduce number of models being published
- Check network latency

## Integration with Home Assistant

The MQTT topics can be easily integrated with Home Assistant's MQTT integration:

```yaml
# configuration.yaml
mqtt:
  broker: mqtt.example.com
  username: !secret mqtt_user
  password: !secret mqtt_password

sensor:
  - platform: mqtt
    name: "SolarEdge AC Power"
    state_topic: "solaredge/inverter"
    value_template: "{{ value_json.data.ac_power_w }}"
    unit_of_measurement: "W"
```
