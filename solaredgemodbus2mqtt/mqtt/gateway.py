"""MQTT gateway for publishing/subscribing to SolarEdge Modbus values."""

from __future__ import annotations

import json
import logging
import ssl
import time
from abc import ABC, abstractmethod
from dataclasses import dataclass, field
from threading import Event, Lock
from typing import Any, Callable

import paho.mqtt.client as mqtt

logger = logging.getLogger(__name__)


class MQTTError(RuntimeError):
    """Raised for MQTT-related failures."""


@dataclass(slots=True)
class MQTTConfig:
    """MQTT broker configuration."""

    broker_host: str
    broker_port: int = 1883
    username: str | None = None
    password: str | None = None
    client_id: str = ""
    keepalive: int = 60
    # TLS/SSL settings
    ssl_ca_certs: str | None = None
    """Path to CA certificate file for server verification."""
    ssl_certfile: str | None = None
    """Path to client certificate file for mutual TLS authentication."""
    ssl_keyfile: str | None = None
    """Path to client private key file for mutual TLS authentication."""
    ssl_tls_version: int = field(default_factory=lambda: ssl.PROTOCOL_TLS_CLIENT)
    """TLS protocol version (default: ssl.PROTOCOL_TLS_CLIENT)."""
    ssl_insecure: bool = False
    """When True, disable server certificate hostname verification (not recommended for production)."""


class MQTTGatewayBase(ABC):
    """Base class for MQTT gateway operations."""

    def __init__(self, config: MQTTConfig):
        """Initialize MQTT gateway.

        Args:
            config: MQTT broker configuration
        """
        self._config = config
        self._client: mqtt.Client | None = None
        self._connected = Event()

    def connect(self) -> None:
        """Connect to MQTT broker."""
        if self._client is not None and self._connected.is_set():
            return

        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
            self._connected.clear()

        self._client = mqtt.Client(mqtt.CallbackAPIVersion.VERSION2, client_id=self._config.client_id)
        self._client.on_connect = self._on_connect
        self._client.on_disconnect = self._on_disconnect
        self._client.on_message = self._on_message

        if self._config.username is not None:
            self._client.username_pw_set(self._config.username, self._config.password)

        tls_requested = (
            self._config.ssl_ca_certs is not None
            or self._config.ssl_certfile is not None
            or self._config.ssl_keyfile is not None
            or self._config.ssl_insecure
        )
        if tls_requested:
            self._client.tls_set(
                ca_certs=self._config.ssl_ca_certs,
                certfile=self._config.ssl_certfile,
                keyfile=self._config.ssl_keyfile,
                tls_version=self._config.ssl_tls_version,
            )
            if self._config.ssl_insecure:
                self._client.tls_insecure_set(True)

        try:
            self._client.connect(self._config.broker_host, self._config.broker_port, keepalive=self._config.keepalive)
            self._client.loop_start()

            # Wait for connection with timeout
            if not self._connected.wait(timeout=5.0):
                self._client.loop_stop()
                raise MQTTError(f"Failed to connect to MQTT broker at {self._config.broker_host}:{self._config.broker_port}")
        except Exception as exc:
            if self._client:
                self._client.loop_stop()
                self._client = None
            raise MQTTError(f"MQTT connection failed: {exc}") from exc

    def disconnect(self) -> None:
        """Disconnect from MQTT broker."""
        if self._client is not None:
            self._client.loop_stop()
            self._client.disconnect()
            self._client = None
            self._connected.clear()

    def __enter__(self) -> "MQTTGatewayBase":
        self.connect()
        return self

    def __exit__(self, exc_type: object, exc: object, tb: object) -> None:
        self.disconnect()

    def _on_connect(
        self,
        client: mqtt.Client,
        userdata: Any,
        flags: mqtt.ConnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        """Handle MQTT connection."""
        if reason_code == 0:
            logger.info("Connected to MQTT broker")
            self._connected.set()
            self._on_connected()
        else:
            logger.error(f"MQTT connection failed with code {reason_code}")
            self._connected.clear()

    def _on_disconnect(
        self,
        client: mqtt.Client,
        userdata: Any,
        disconnect_flags: mqtt.DisconnectFlags,
        reason_code: mqtt.ReasonCode,
        properties: mqtt.Properties | None,
    ) -> None:
        """Handle MQTT disconnection."""
        self._connected.clear()
        if reason_code != 0:
            logger.warning(f"Unexpected disconnection from MQTT broker (code {reason_code})")

    @abstractmethod
    def _on_connected(self) -> None:
        """Called when connected to broker. Subclasses should implement subscriptions here."""

    @abstractmethod
    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """Handle incoming MQTT message."""

    def _ensure_connected(self) -> None:
        """Ensure MQTT client is connected."""
        if not self._connected.is_set():
            raise MQTTError("Not connected to MQTT broker")

    def publish(self, topic: str, payload: Any, qos: int = 0, retain: bool = False) -> None:
        """Publish message to MQTT topic.

        Args:
            topic: MQTT topic
            payload: Message payload (will be JSON-encoded if not string)
            qos: Quality of Service (0, 1, or 2)
            retain: Whether to retain the message
        """
        self._ensure_connected()

        if isinstance(payload, str):
            message = payload
        else:
            message = json.dumps(payload)

        publish_info = self._client.publish(topic, message, qos=qos, retain=retain)
        if publish_info.rc != mqtt.MQTT_ERR_SUCCESS:
            raise MQTTError(f"Failed to publish MQTT message to {topic}: rc={publish_info.rc}")
        logger.debug(f"Published to {topic}: {message}")


class MQTTWriter(MQTTGatewayBase):
    """MQTT writer for publishing Modbus values."""

    def __init__(self, config: MQTTConfig, base_topic: str = "solaredge/modbus"):
        """Initialize MQTT writer.

        Args:
            config: MQTT broker configuration
            base_topic: Base topic for all published messages
        """
        super().__init__(config)
        self._base_topic = base_topic.rstrip("/")

    def _on_connected(self) -> None:
        """No subscriptions needed for writer."""

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """No messages expected for writer."""

    def publish_register(self, register_name: str, value: int | float, topic_suffix: str | None = None, **kwargs: Any) -> None:
        """Publish a single register value.

        Args:
            register_name: Name of the register (e.g., "ac_current")
            value: Register value
            topic_suffix: Optional topic suffix (defaults to register_name)
            **kwargs: Additional fields to include in JSON payload
        """
        topic = f"{self._base_topic}/{topic_suffix or register_name}"
        payload = {"value": value, "name": register_name, "timestamp": time.time(), **kwargs}
        self.publish(topic, payload, qos=1, retain=True)

    def publish_model(self, model_name: str, data: dict[str, Any], **kwargs: Any) -> None:
        """Publish entire model data.

        Args:
            model_name: Name of the model (e.g., "inverter", "mppt")
            data: Dictionary of model data
            **kwargs: Additional fields to include in payload
        """
        topic = f"{self._base_topic}/{model_name}"
        payload = {
            "model": model_name,
            "data": data,
            "timestamp": time.time(),
            **kwargs,
        }
        self.publish(topic, payload, qos=1, retain=True)

    def publish_holding_registers(self, address: int, values: list[int]) -> None:
        """Publish raw holding registers.

        Args:
            address: Base register address
            values: List of register values
        """
        topic = f"{self._base_topic}/registers/raw"
        payload = {
            "address": address,
            "values": values,
            "count": len(values),
            "timestamp": time.time(),
        }
        self.publish(topic, payload, qos=1, retain=True)


class MQTTReader(MQTTGatewayBase):
    """MQTT reader for subscribing to Modbus write commands."""

    def __init__(
        self,
        config: MQTTConfig,
        write_callback: Callable[[int, int | list[int]], None],
        base_topic: str = "solaredge/modbus/set",
    ):
        """Initialize MQTT reader.

        Args:
            config: MQTT broker configuration
            write_callback: Callback function(address, value) for write operations
            base_topic: Base topic to subscribe to
        """
        super().__init__(config)
        self._base_topic = base_topic.rstrip("/")
        self._write_callback = write_callback

    def _on_connected(self) -> None:
        """Subscribe to write command topics."""
        # Subscribe to single register writes: solaredge/modbus/set/register/<address>
        self._client.subscribe(f"{self._base_topic}/register/+")
        # Subscribe to bulk register writes: solaredge/modbus/set/registers/<address>
        self._client.subscribe(f"{self._base_topic}/registers/+")
        logger.info(f"Subscribed to write topics under {self._base_topic}")

    def _on_message(self, client: mqtt.Client, userdata: Any, msg: mqtt.MQTTMessage) -> None:
        """Handle incoming write command."""
        try:
            topic = msg.topic
            payload = json.loads(msg.payload.decode("utf-8"))

            if f"{self._base_topic}/register/" in topic:
                # Single register write
                address = int(topic.split("/")[-1])
                if "value" not in payload:
                    raise ValueError("Missing required 'value' field in register write payload")
                value = int(payload["value"])
                logger.info(f"Setting register {address} to {value}")
                self._write_callback(address, value)

            elif f"{self._base_topic}/registers/" in topic:
                # Bulk register write
                address = int(topic.split("/")[-1])
                values = payload.get("values")
                if not isinstance(values, (list, tuple)) or not values:
                    raise ValueError("Missing required non-empty 'values' list in bulk register write payload")
                values = [int(v) for v in values]
                logger.info(f"Setting registers {address}-{address + len(values) - 1} to {values}")
                self._write_callback(address, values)

        except (json.JSONDecodeError, ValueError, KeyError) as e:
            logger.error(f"Failed to process MQTT message: {e}")
        except Exception as e:
            logger.error(f"Error in message handler: {e}")

    def wait_for_messages(self, timeout: float | None = None) -> None:
        """Block until disconnect or timeout.

        Args:
            timeout: How long to wait in seconds (None for indefinite)
        """
        self._ensure_connected()
        if timeout:
            time.sleep(timeout)
        else:
            try:
                while self._connected.is_set():
                    time.sleep(0.1)
            except KeyboardInterrupt:
                logger.info("Interrupted")


class MQTTBridge:
    """Bridge to synchronize Modbus client with MQTT."""

    def __init__(
        self, modbus_client: Any, mqtt_config: MQTTConfig, base_topic: str = "solaredge/modbus", modbus_unit: int = 1
    ):
        """Initialize bridge.

        Args:
            modbus_client: SolarEdgeModbusClient instance
            mqtt_config: MQTT broker configuration
            base_topic: Base topic for MQTT communication
        """
        self._modbus_client = modbus_client
        self._mqtt_config = mqtt_config
        self._base_topic = base_topic
        self._modbus_unit = modbus_unit
        self._writer: MQTTWriter | None = None
        self._reader: MQTTReader | None = None
        self._modbus_lock = Lock()

    def _role_config(self, role: str) -> MQTTConfig:
        client_id = self._mqtt_config.client_id
        if client_id:
            client_id = f"{client_id}-{role}"
        return MQTTConfig(
            broker_host=self._mqtt_config.broker_host,
            broker_port=self._mqtt_config.broker_port,
            username=self._mqtt_config.username,
            password=self._mqtt_config.password,
            client_id=client_id,
            keepalive=self._mqtt_config.keepalive,
            ssl_ca_certs=self._mqtt_config.ssl_ca_certs,
            ssl_certfile=self._mqtt_config.ssl_certfile,
            ssl_keyfile=self._mqtt_config.ssl_keyfile,
            ssl_tls_version=self._mqtt_config.ssl_tls_version,
            ssl_insecure=self._mqtt_config.ssl_insecure,
        )

    def modbus_call(self, operation: Callable[[], Any]) -> Any:
        """Execute one Modbus operation under a lock."""
        with self._modbus_lock:
            return operation()

    def start_writer(self) -> MQTTWriter:
        """Start MQTT writer."""
        if self._writer is None:
            self._writer = MQTTWriter(self._role_config("writer"), self._base_topic)
            self._writer.connect()
        return self._writer

    def start_reader(self) -> MQTTReader:
        """Start MQTT reader for write commands."""

        def write_callback(address: int, value: int | list[int]) -> None:
            try:
                if isinstance(value, list):
                    self.modbus_call(lambda: self._modbus_client.write_registers(address, value, unit=self._modbus_unit))
                else:
                    self.modbus_call(lambda: self._modbus_client.write_register(address, value, unit=self._modbus_unit))
            except Exception as e:
                logger.error(f"Failed to write Modbus register(s): {e}")

        if self._reader is None:
            self._reader = MQTTReader(self._role_config("reader"), write_callback, f"{self._base_topic}/set")
            self._reader.connect()
        return self._reader

    def stop(self) -> None:
        """Stop both reader and writer."""
        if self._writer is not None:
            self._writer.disconnect()
            self._writer = None
        if self._reader is not None:
            self._reader.disconnect()
            self._reader = None

    def publish_inverter_data(self, data: dict[str, Any]) -> None:
        """Publish inverter data to MQTT."""
        if self._writer is None:
            raise MQTTError("Writer not started")
        self._writer.publish_model("inverter", data, unit=self._modbus_unit)

    def publish_mppt_data(self, data: dict[str, Any]) -> None:
        """Publish MPPT data to MQTT."""
        if self._writer is None:
            raise MQTTError("Writer not started")
        self._writer.publish_model("mppt", data, unit=self._modbus_unit)

    def publish_common_model(self, data: dict[str, Any]) -> None:
        """Publish common model data to MQTT."""
        if self._writer is None:
            raise MQTTError("Writer not started")
        self._writer.publish_model("common", data, unit=self._modbus_unit)
