import json
import os
import time

from kafka import KafkaConsumer
from opentelemetry import trace, propagate
from opentelemetry.trace import SpanKind

from order_projection import apply_projection
from rabbitmq_bridge import forward_event
from json_logger import log_event


KAFKA_SERVER = os.getenv("KAFKA_SERVER", "kafka:9092")
TOPIC = "orders-events"

tracer = trace.get_tracer(__name__)


def consume_order_events():
    while True:
        consumer = None

        try:
            consumer = KafkaConsumer(
                TOPIC,
                bootstrap_servers=KAFKA_SERVER,
                group_id=None,
                auto_offset_reset="earliest",
                enable_auto_commit=False,
                value_deserializer=lambda value: json.loads(
                    value.decode("utf-8")
                )
            )

            log_event(
                "orders",
                "INFO",
                "Read model consumer started"
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
                    "Kafka consume " + event["eventType"],
                    context=parent_context,
                    kind=SpanKind.CONSUMER
                ) as span:

                    span.set_attribute(
                        "messaging.system", "kafka"
                    )

                    span.set_attribute(
                        "order.id", event["orderId"]
                    )

                    apply_projection(event)

                    log_event(
                        "orders",
                        "INFO",
                        "Read model updated",
                        event_type=event["eventType"],
                        order_id=event["orderId"]
                    )

        except Exception as error:
            log_event(
                "orders",
                "ERROR",
                "Read model consumer error",
                error=str(error)
            )
            time.sleep(3)

        finally:
            if consumer is not None:
                consumer.close()
