import json
import os
import time

from kafka import KafkaProducer
from opentelemetry import trace, propagate
from opentelemetry.trace import SpanKind
from json_logger import log_event


KAFKA_SERVER = os.getenv("KAFKA_SERVER", "kafka:9092")
TOPIC = "orders-events"

tracer = trace.get_tracer(__name__)


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
        with tracer.start_as_current_span(
            "Kafka publish " + event["eventType"],
            kind=SpanKind.PRODUCER
        ) as span:

            span.set_attribute("messaging.system", "kafka")
            span.set_attribute("messaging.destination.name", TOPIC)
            span.set_attribute("order.id", event["orderId"])

            carrier = {}
            propagate.inject(carrier)

            headers = [
                (key, value.encode("utf-8"))
                for key, value in carrier.items()
            ]

            future = producer.send(
                TOPIC,
                event,
                headers=headers
            )

            future.get(timeout=10)
            producer.flush()

            log_event(
                "orders",
                "INFO",
                "Kafka event published",
                event_type=event["eventType"],
                order_id=event["orderId"]
            )

    finally:
        producer.close()