"""Runnable examples for MQTT gateway functionality."""

from solaredgemodbus2mqtt.solaredge_modbus.client import SolarEdgeModbusClient
from solaredgemodbus2mqtt.mqtt import MQTTBridge, MQTTConfig, MQTTReader, MQTTWriter


def example_mqtt_writer() -> None:
    """Example: Publish Modbus values to MQTT."""
    # Create Modbus client
    client = SolarEdgeModbusClient.tcp("127.0.0.1", port=1502)
    writer = None
    try:
        client.connect()

        # Create MQTT writer
        mqtt_config = MQTTConfig(
            broker_host="127.0.0.1",
            broker_port=1883,
        )
        writer = MQTTWriter(mqtt_config, base_topic="solaredge/modbus")
        writer.connect()

        # Read and publish inverter data
        inverter_data = client.read_inverter_data()
        writer.publish_model("inverter", inverter_data.to_dict())

        # Read and publish common model
        common_data = client.read_common_model()
        writer.publish_model("common", common_data.to_dict())

        # Publish single register value
        value = client.read_holding(40245, 1)[0]
        writer.publish_register("inverter_status", value)

    finally:
        if writer is not None:
            writer.disconnect()
        client.close()


def example_mqtt_reader() -> None:
    """Example: Listen for MQTT write commands and apply to Modbus."""
    # Create Modbus client
    client = SolarEdgeModbusClient.tcp("127.0.0.1", port=1502)
    reader = None
    try:
        client.connect()

        # Define callback for write operations
        def handle_write(address: int, value: int | list[int]) -> None:
            """Handle incoming MQTT write command."""
            if isinstance(value, list):
                client.write_registers(address, value)
                print(f"Wrote registers at {address}: {value}")
            else:
                client.write_register(address, value)
                print(f"Wrote register at {address}: {value}")

        # Create and start MQTT reader
        mqtt_config = MQTTConfig(
            broker_host="127.0.0.1",
            broker_port=1883,
        )
        reader = MQTTReader(mqtt_config, handle_write, base_topic="solaredge/modbus/set")
        reader.connect()

        # Listen for messages for 60 seconds
        reader.wait_for_messages(timeout=60)
    finally:
        if reader is not None:
            reader.disconnect()
        client.close()


def example_mqtt_bridge() -> None:
    """Example: Full bi-directional bridge."""
    import time

    # Create Modbus client
    client = SolarEdgeModbusClient.tcp("127.0.0.1", port=1502)
    bridge = None
    try:
        client.connect()

        # Create bridge
        mqtt_config = MQTTConfig(
            broker_host="127.0.0.1",
            broker_port=1883,
        )
        bridge = MQTTBridge(client, mqtt_config, base_topic="solaredge/modbus")

        # Start both reader and writer
        bridge.start_writer()
        bridge.start_reader()

        print("Bridge started. Publishing and listening for commands...")

        # Publish every 30 seconds
        for i in range(60):  # Run for ~30 minutes
            try:
                # Read and publish
                inverter_data = client.read_inverter_data()
                bridge.publish_inverter_data(inverter_data.to_dict())
                print(f"[{i}] Published inverter data")
            except Exception as e:
                print(f"Error: {e}")

            time.sleep(30)
    finally:
        if bridge is not None:
            bridge.stop()
        client.close()


def example_context_managers() -> None:
    """Example: Using context managers for clean resource management."""
    mqtt_config = MQTTConfig(
        broker_host="127.0.0.1",
        broker_port=1883,
    )

    with SolarEdgeModbusClient.tcp("127.0.0.1") as client:
        with MQTTWriter(mqtt_config) as writer:
            # Publish data
            inverter_data = client.read_inverter_data()
            writer.publish_model("inverter", inverter_data.to_dict())

        # Resources cleaned up automatically


def example_mqtt_ssl_writer() -> None:
    """Example: Read Modbus values and publish to MQTT broker using SSL/TLS authentication.

    This example demonstrates:
    - One-way TLS: broker identity is verified against a CA certificate.
    - Mutual TLS (mTLS): the client also authenticates with its own certificate and key.

    Replace the placeholder paths with your actual certificate files.
    The broker must be configured to listen on the TLS port (typically 8883).
    """
    import time

    # Create Modbus client (adjust host/port to match your inverter)
    client = SolarEdgeModbusClient.tcp("192.168.1.100", port=1502)
    writer = None
    try:
        client.connect()

        # --- SSL/TLS configuration ---
        # One-way TLS: only the broker certificate is verified.
        # Set ssl_ca_certs to the CA bundle that signed the broker's certificate.
        #
        # For mutual TLS (mTLS), also supply ssl_certfile and ssl_keyfile so the
        # broker can verify the identity of this client.
        mqtt_config = MQTTConfig(
            broker_host="mqtt.example.com",
            broker_port=8883,  # Standard MQTT-over-TLS port
            username="solaredge",  # Optional: broker username
            password="secret",  # Optional: broker password
            client_id="solaredge-inverter-1",
            # TLS: path to the CA certificate that signed the broker's certificate
            ssl_ca_certs="/etc/ssl/certs/ca-bundle.crt",
            # mTLS: uncomment the two lines below and point to your client cert/key
            # ssl_certfile="/etc/ssl/client/client.crt",
            # ssl_keyfile="/etc/ssl/client/client.key",
        )

        writer = MQTTWriter(mqtt_config, base_topic="solaredge/modbus")
        writer.connect()

        print("Connected to MQTT broker with SSL/TLS. Publishing data every 30 seconds...")
        print("Press Ctrl+C to stop.\n")

        iteration = 0
        try:
            while True:
                iteration += 1
                try:
                    # Read all available models from the inverter
                    inverter_data = client.read_inverter_data()
                    writer.publish_model("inverter", inverter_data.to_dict())

                    common_data = client.read_common_model()
                    writer.publish_model("common", common_data.to_dict())

                    mppt_data = client.read_mppt_model()
                    writer.publish_model("mppt", mppt_data.to_dict())

                    print(f"[{iteration}] Published inverter, common, and MPPT data at {time.strftime('%H:%M:%S')}")
                except Exception as e:
                    print(f"[{iteration}] Error reading Modbus data: {e}")

                time.sleep(30)
        except KeyboardInterrupt:
            print("\nStopped by user.")
    finally:
        if writer is not None:
            writer.disconnect()
        client.close()


if __name__ == "__main__":
    # Run examples:
    # example_mqtt_writer()
    # example_mqtt_reader()
    # example_mqtt_bridge()
    # example_context_managers()
    # example_mqtt_ssl_writer()
    print("See examples above - uncomment to run")
