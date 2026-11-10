
import json
import os
import time

from kafka import KafkaProducer


KAFKA_SERVER = os.getenv("KAFKA_SERVER", "kafka:9092")
TOPIC = "orders-events"


def publish_order_event(event):
    producer = None

    for attempt in range(10):
        try:
            producer = KafkaProducer(
                bootstrap_servers=KAFKA_SERVER,
                value_serializer=lambda value: json.dumps(
                    value
                ).encode("utf-8")
            )
            break
        except Exception:
            time.sleep(2)

    if producer is None:
        raise RuntimeError("Cannot connect to Kafka")

    try:
        future = producer.send(TOPIC, event)
        future.get(timeout=10)
        producer.flush()
        print(
            f"Kafka event published: {event['eventType']}",
            flush=True
        )
    finally:
        producer.close()
