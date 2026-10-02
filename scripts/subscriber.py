import json
import logging
import os
import time

import paho.mqtt.client as mqtt
from influxdb_client import InfluxDBClient, Point
from influxdb_client.client.write_api import SYNCHRONOUS

MQTT_BROKER = os.getenv('MQTT_BROKER', 'broker.hivemq.com')
MQTT_PORT = int(os.getenv('MQTT_PORT', '1883'))
MQTT_TOPIC = os.getenv('MQTT_TOPIC', 'iot/B23DCAT066/telemetry')
MQTT_KEEPALIVE = int(os.getenv('MQTT_KEEPALIVE', '60'))

INFLUX_URL = os.getenv('INFLUX_URL', 'http://localhost:8086')
INFLUX_TOKEN = os.getenv('INFLUX_TOKEN')
INFLUX_ORG = os.getenv('INFLUX_ORG', 'PTIT')
INFLUX_BUCKET = os.getenv('INFLUX_BUCKET', 'iot_data')

STUDENT_ID = 'B23DCAT066'
RAW_MEASUREMENT = 'environment'

TEMPERATURE_MIN, TEMPERATURE_MAX = -40.0, 85.0
HUMIDITY_MIN, HUMIDITY_MAX = 0.0, 100.0
DISTANCE_MIN, DISTANCE_MAX = 2.0, 400.0

logging.basicConfig(level=logging.INFO, format='%(asctime)s | %(levelname)s | %(message)s')

influx_client = InfluxDBClient(url=INFLUX_URL, token=INFLUX_TOKEN, org=INFLUX_ORG, timeout=20000)
write_api = influx_client.write_api(write_options=SYNCHRONOUS)

last_seq = {}
seen_messages = set()
MAX_SEEN_MESSAGES = 10000


def validate_payload(payload):
    required = ['student_id', 'device_id', 'seq', 'timestamp_ms', 'temperature', 'humidity', 'distance']
    missing = [f for f in required if f not in payload]
    if missing:
        return False, f"Missing fields: {', '.join(missing)}"

    if payload['student_id'] != STUDENT_ID:
        return False, f"Invalid student_id: {payload['student_id']}"
    if not isinstance(payload['device_id'], str) or not payload['device_id'].strip():
        return False, 'device_id must be a non-empty string'

    try:
        seq = int(payload['seq'])
    except (TypeError, ValueError):
        return False, 'seq must be an integer'
    if seq < 1:
        return False, 'seq must be >= 1'

    try:
        timestamp_ms = int(payload['timestamp_ms'])
    except (TypeError, ValueError):
        return False, 'timestamp_ms must be an integer'
    if timestamp_ms < 1_000_000_000_000:
        return False, 'timestamp_ms is not a valid Unix timestamp in milliseconds'

    try:
        temperature = float(payload['temperature'])
        humidity = float(payload['humidity'])
        distance = float(payload['distance'])
    except (TypeError, ValueError):
        return False, 'temperature, humidity and distance must be numeric'

    if not TEMPERATURE_MIN <= temperature <= TEMPERATURE_MAX:
        return False, f'temperature out of range: {temperature}'
    if not HUMIDITY_MIN <= humidity <= HUMIDITY_MAX:
        return False, f'humidity out of range: {humidity}'
    if not DISTANCE_MIN <= distance <= DISTANCE_MAX:
        return False, f'distance out of range: {distance}'

    return True, ''


def calculate_latency(timestamp_ms):
    receive_time_ms = time.time_ns() // 1_000_000
    return receive_time_ms, receive_time_ms - timestamp_ms


def check_sequence(device_id, seq):
    previous = last_seq.get(device_id)
    if previous is None:
        last_seq[device_id] = seq
        return True, f'First packet, seq={seq}'

    if seq == previous + 1:
        last_seq[device_id] = seq
        return True, f'OK, seq={seq}'

    if seq == previous:
        return False, f'Duplicate packet: seq={seq}'

    if seq < previous:
        if seq == 1:
            logging.warning('Device %s restarted: sequence reset to 1.', device_id)
            last_seq[device_id] = seq
            return True, 'New device session, seq reset to 1'
        return False, f'Out-of-order packet: seq={seq}, last_seq={previous}'

    missing = seq - previous - 1
    last_seq[device_id] = seq
    return True, f'WARNING: {missing} packet(s) possibly lost before seq={seq}'


def write_to_influx(payload, latency_ms):
    timestamp_ms = int(payload['timestamp_ms'])
    point = (
        Point(RAW_MEASUREMENT)
        .tag('student_id', STUDENT_ID)
        .tag('device_id', payload['device_id'])
        .field('seq', int(payload['seq']))
        .field('temperature', float(payload['temperature']))
        .field('humidity', float(payload['humidity']))
        .field('distance', float(payload['distance']))
        .field('latency_ms', float(latency_ms))
        .time(timestamp_ms * 1_000_000)
    )
    write_api.write(bucket=INFLUX_BUCKET, org=INFLUX_ORG, record=point)


def on_connect(client, userdata, flags, reason_code, properties=None):
    if reason_code == 0:
        logging.info('Connected to MQTT broker: %s:%s', MQTT_BROKER, MQTT_PORT)
        result, mid = client.subscribe(MQTT_TOPIC, qos=0)
        if result == mqtt.MQTT_ERR_SUCCESS:
            logging.info('Subscribed to topic: %s', MQTT_TOPIC)
        else:
            logging.error('Subscribe failed: result=%s', result)
    else:
        logging.error('MQTT connection failed. reason_code=%s', reason_code)


def on_disconnect(client, userdata, disconnect_flags, reason_code, properties=None):
    logging.warning('Disconnected from MQTT broker. reason_code=%s', reason_code)


def on_message(client, userdata, msg):
    try:
        text = msg.payload.decode('utf-8')
        payload = json.loads(text)
    except UnicodeDecodeError as exc:
        logging.error('Invalid UTF-8 payload: %s', exc)
        return
    except json.JSONDecodeError as exc:
        logging.error('Invalid JSON: %s | payload=%r', exc, msg.payload)
        return

    if not isinstance(payload, dict):
        logging.error('JSON payload must be an object.')
        return

    valid, error = validate_payload(payload)
    if not valid:
        logging.error('INVALID PAYLOAD | %s | payload=%s', error, payload)
        return

    device_id = payload['device_id']
    seq = int(payload['seq'])
    timestamp_ms = int(payload['timestamp_ms'])
    key = (device_id, seq, timestamp_ms)

    if key in seen_messages:
        logging.warning('Duplicate MQTT message ignored | device=%s | seq=%s', device_id, seq)
        return

    accepted, sequence_message = check_sequence(device_id, seq)
    if not accepted:
        logging.warning('%s | device=%s', sequence_message, device_id)
        return
    if 'WARNING' in sequence_message:
        logging.warning('%s | device=%s', sequence_message, device_id)

    receive_time_ms, latency_ms = calculate_latency(timestamp_ms)
    if latency_ms < -5000:
        logging.warning('Negative latency detected: %d ms. Check clock synchronization.', latency_ms)

    try:
        write_to_influx(payload, latency_ms)
    except Exception:
        logging.exception('Failed to write data to InfluxDB.')
        return

    seen_messages.add(key)
    if len(seen_messages) > MAX_SEEN_MESSAGES:
        seen_messages.pop()

    logging.info(
        'DATA SAVED | student=%s | device=%s | seq=%d | temperature=%.2f C | humidity=%.2f %% | distance=%.2f cm | latency=%d ms | receive=%d',
        payload['student_id'], device_id, seq,
        float(payload['temperature']), float(payload['humidity']), float(payload['distance']),
        latency_ms, receive_time_ms
    )


def create_mqtt_client():
    client = mqtt.Client(
        mqtt.CallbackAPIVersion.VERSION2,
        client_id=f'subscriber-{STUDENT_ID}',
        protocol=mqtt.MQTTv311,
    )
    client.on_connect = on_connect
    client.on_message = on_message
    client.on_disconnect = on_disconnect
    client.reconnect_delay_set(min_delay=1, max_delay=30)
    return client


def main():
    logging.info('=' * 70)
    logging.info('IoT MQTT SUBSCRIBER')
    logging.info('Student: %s', STUDENT_ID)
    logging.info('Broker: %s:%s', MQTT_BROKER, MQTT_PORT)
    logging.info('Topic: %s', MQTT_TOPIC)
    logging.info('InfluxDB: %s', INFLUX_URL)
    logging.info('Organization: %s', INFLUX_ORG)
    logging.info('Bucket: %s', INFLUX_BUCKET)
    logging.info('Measurement: %s', RAW_MEASUREMENT)
    logging.info('=' * 70)

    mqtt_client = create_mqtt_client()
    try:
        mqtt_client.connect(MQTT_BROKER, MQTT_PORT, MQTT_KEEPALIVE)
        logging.info('Starting MQTT network loop...')
        mqtt_client.loop_forever()
    except KeyboardInterrupt:
        logging.info('Subscriber stopped by user.')
    except Exception:
        logging.exception('Subscriber stopped because of an error.')
    finally:
        try:
            mqtt_client.disconnect()
        except Exception:
            pass
        write_api.close()
        influx_client.close()
        logging.info('Resources closed.')


if __name__ == '__main__':
    main()
