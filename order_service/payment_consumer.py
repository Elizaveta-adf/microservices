import json
import os
import time

import pika
from opentelemetry import trace, propagate
from opentelemetry.trace import SpanKind

from order_commands import pay_order, cancel_order
from event_store import get_events
from order_aggregate import rehydrate
from json_logger import log_event


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
EXCHANGE_NAME = "saga_events"
QUEUE_NAME = "orders_payment_results"

tracer = trace.get_tracer(__name__)


def consume_payment_results(on_cancel):
    def process_result(channel, method, properties, body):
        event = json.loads(body)
        event_type = event["event_type"]
        order_id = event["data"]["order_id"]

        context = propagate.extract(properties.headers or {})

        with tracer.start_as_current_span(
            "Process " + event_type,
            context=context,
            kind=SpanKind.CONSUMER
        ) as span:

            span.set_attribute("order.id", order_id)
            span.set_attribute("messaging.system", "rabbitmq")

            state = rehydrate(get_events(order_id))

            if state is not None and state["status"] == "CREATED":
                if event_type == "PaymentCompleted":
                    pay_order(order_id)

                elif event_type == "PaymentFailed":
                    cancel_order(order_id)
                    on_cancel()

                log_event(
                    "orders",
                    "INFO",
                    "Payment result processed",
                    order_id=order_id,
                    event_type=event_type
                )

            channel.basic_ack(
                delivery_tag=method.delivery_tag
            )

    while True:
        connection = None

        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )

            channel = connection.channel()

            channel.exchange_declare(
                exchange=EXCHANGE_NAME,
                exchange_type="topic",
                durable=True
            )

            channel.queue_declare(
                queue=QUEUE_NAME,
                durable=True
            )

            for event_type in (
                "PaymentCompleted",
                "PaymentFailed"
            ):
                channel.queue_bind(
                    exchange=EXCHANGE_NAME,
                    queue=QUEUE_NAME,
                    routing_key=event_type
                )

            channel.basic_qos(prefetch_count=1)

            channel.basic_consume(
                queue=QUEUE_NAME,
                on_message_callback=process_result
            )

            log_event(
                "orders",
                "INFO",
                "Payment result consumer started"
            )

            channel.start_consuming()

        except Exception as error:
            log_event(
                "orders",
                "ERROR",
                "Payment consumer error",
                error=str(error)
            )
            time.sleep(3)

        finally:
            if connection is not None and connection.is_open:
                connection.close()