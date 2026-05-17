# Quick Start: MQTT Gateway

## Installation

1. Update dependencies:
```bash
uv sync
```

This will install `paho-mqtt>=1.7.0` along with other project dependencies.

## Setup with Docker (Easiest)

1. Start Mosquitto MQTT broker:
```bash
docker-compose up -d
```

2. In another terminal, run the bridge:
```bash
solaredge-modbus mqtt-bridge --mqtt-host localhost --mqtt-topic solaredge
```

3. Monitor messages in a third terminal:
```bash
docker exec -it solaredge_modbus-mosquitto_1 mosquitto_sub -t 'solaredge/#' -v
```

4. Send a test command:
```bash
docker exec -it solaredge_modbus-mosquitto_1 mosquitto_pub \
  -t 'solaredge/set/register/40245' \
  -m '{"value": 50}'
```

## Manual Setup

If you have an MQTT broker running at `mqtt.example.com`:

### 1. Publish Modbus Data

```bash
solaredge-modbus mqtt-publish \
  --mqtt-host mqtt.example.com \
  --mqtt-topic solaredge \
  --interval 30 \
  --models inverter mppt common
```

### 2. Listen for Commands

```bash
solaredge-modbus mqtt-listen \
  --mqtt-host mqtt.example.com \
  --mqtt-topic solaredge
```

### 3. Run Both (Bridge Mode)

```bash
solaredge-modbus mqtt-bridge \
  --mqtt-host mqtt.example.com \
  --mqtt-topic solaredge \
  --publish-interval 30 \
  --models inverter mppt common
```

## Verify It Works

### Monitor all messages:
```bash
mosquitto_sub -h mqtt.example.com -t 'solaredge/#' -v
```

### Subscribe to specific model:
```bash
mosquitto_sub -h mqtt.example.com -t 'solaredge/inverter' -v
```

### Send a write command:
```bash
mosquitto_pub -h mqtt.example.com \
  -t 'solaredge/set/register/40245' \
  -m '{"value": 100}'
```

## Test with Home Assistant

Add to `configuration.yaml`:

```yaml
mqtt:
  broker: mqtt.example.com

sensor:
  - platform: mqtt
    name: "Solar AC Power"
    state_topic: "solaredge/inverter"
    value_template: "{{ value_json.data.ac_power_w }}"
    unit_of_measurement: "W"
    icon: mdi:flash
```

## Next Steps

See [MQTT.md](MQTT.md) for:
- Full command documentation
- Topic structure and payload formats
- Python API usage
- Advanced configurations
- Troubleshooting

See [examples/mqtt_examples.py](examples/mqtt_examples.py) for:
- Writer example
- Reader example  
- Bridge example
- Context manager usage

## Troubleshooting

### "Connection refused"
- Check MQTT broker is running: `docker-compose ps`
- Verify hostname/port: `docker-compose logs mosquitto`

### "No module named 'paho'"
- Run `uv sync` to install dependencies

### Messages not received
- Check topic subscriptions: `mosquitto_sub -t 'solaredge/#' -v`
- Enable debug logging: Set `logging.basicConfig(level=logging.DEBUG)` in Python code

### Registers not being written
- Check the write topic format: `solaredge/set/register/ADDRESS`
- Verify JSON payload: `{"value": 12345}`
- Monitor Modbus errors in console output

## Example Workflow

**Terminal 1** - Start MQTT broker:
```bash
docker-compose up mosquitto
```

**Terminal 2** - Start bridge:
```bash
solaredge-modbus mqtt-bridge --mqtt-host localhost
```

**Terminal 3** - Monitor:
```bash
mosquitto_sub -h localhost -t 'solaredge/#' -v
```

**Terminal 4** - Test write:
```bash
mosquitto_pub -h localhost -t 'solaredge/set/register/40245' -m '{"value": 50}'
```

You should see:
- Terminal 2: "Published data" messages every 30s
- Terminal 3: JSON data for inverter/mppt/common, then write confirmations
- Terminal 4: Command is sent

Enjoy! 🚀
