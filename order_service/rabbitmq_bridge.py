import json
import os

import pika

from opentelemetry import trace, propagate
from opentelemetry.trace import SpanKind
from json_logger import log_event


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
EXCHANGE_NAME = "saga_events"

tracer = trace.get_tracer(__name__)


def forward_event(event):
    event_type = event["eventType"]

    if event_type not in ("OrderCreated", "OrderCancelled"):
        return

    with tracer.start_as_current_span(
        "RabbitMQ publish " + event_type,
        kind=SpanKind.PRODUCER
    ) as span:

        span.set_attribute("messaging.system", "rabbitmq")
        span.set_attribute("order.id", event["orderId"])

        carrier = {}
        propagate.inject(carrier)

        message = {
            "event_type": event_type,
            "data": {
                **event["payload"],
                "order_id": event["orderId"]
            }
        }

        connection = pika.BlockingConnection(
            pika.ConnectionParameters(host=RABBITMQ_HOST)
        )

        try:
            channel = connection.channel()

            channel.exchange_declare(
                exchange=EXCHANGE_NAME,
                exchange_type="topic",
                durable=True
            )

            channel.confirm_delivery()

            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=event_type,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    headers=carrier,
                    message_id=event["eventId"]
                )
            )

            log_event(
                "orders",
                "INFO",
                "Event forwarded to RabbitMQ",
                event_type=event_type,
                order_id=event["orderId"]
            )

        finally:
            connection.close()

def consume_bridge_events():
    import time
    from kafka import KafkaConsumer

    while True:
        consumer = None

        try:
            consumer = KafkaConsumer(
                "orders-events",
                bootstrap_servers=os.getenv(
                    "KAFKA_SERVER", "kafka:9092"
                ),
                group_id="lab8-rabbitmq-bridge",
                auto_offset_reset="latest",
                enable_auto_commit=False,
                value_deserializer=lambda value: json.loads(
                    value.decode("utf-8")
                )
            )

            log_event(
                "orders",
                "INFO",
                "Kafka RabbitMQ bridge started"
            )

            for message in consumer:
                carrier = {
                    key: value.decode("utf-8")
                    for key, value in (message.headers or [])
                    if value is not None
                }

                parent_context = propagate.extract(carrier)
                event = message.value

                with tracer.start_as_current_span(
                    "Kafka bridge " + event["eventType"],
                    context=parent_context,
                    kind=SpanKind.CONSUMER
                ):
                    forward_event(event)

                consumer.commit()

        except Exception as error:
            log_event(
                "orders",
                "ERROR",
                "Kafka RabbitMQ bridge error",
                error=str(error)
            )

            time.sleep(3)

        finally:
            if consumer is not None:
                consumer.close()