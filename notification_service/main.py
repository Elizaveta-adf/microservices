import json
import os
import time
from json_logger import log_event
import pika

from tracing import setup_tracing
from opentelemetry import propagate
from opentelemetry.trace import SpanKind

tracer = setup_tracing("notification")
from prometheus_client import Counter, start_http_server

NOTIFICATIONS = Counter(
    "notifications_total",
    "Total processed notifications",
    ["event_type"]
)

NOTIFICATIONS.labels(event_type="PaymentCompleted")
NOTIFICATIONS.labels(event_type="OrderCancelled")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
EXCHANGE_NAME = "saga_events"
QUEUE_NAME = "notification_events"


def handle_event(channel, method, properties, body):
    carrier = properties.headers or {}
    parent_context = propagate.extract(carrier)

    with tracer.start_as_current_span(
        "Process notification",
        context=parent_context,
        kind=SpanKind.CONSUMER
    ) as span:

        message = json.loads(body)

        event_type = (
            message.get("event_type")
            or message.get("event")
        )

        data = message["data"]
        order_id = data["order_id"]

        span.set_attribute("order.id", order_id)
        span.set_attribute("event.type", event_type)
        span.set_attribute("messaging.system", "rabbitmq")

        log_event(
            "notification",
            "INFO",
            "Received event",
            event_type=event_type,
            order_id=order_id
        )

        if event_type == "PaymentCompleted":
            log_event(
                "notification",
                "INFO",
                f"Заказ {order_id} успешно оплачен",
                order_id=order_id
            )

        elif event_type == "OrderCancelled":
            log_event(
                "notification",
                "INFO",
                f"Заказ {order_id} отменён",
                order_id=order_id
            )
        if event_type in ("PaymentCompleted", "OrderCancelled"):
            NOTIFICATIONS.labels(
                event_type=event_type
            ).inc()
        channel.basic_ack(
            delivery_tag=method.delivery_tag
        )


def main():
    while True:
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(host=RABBITMQ_HOST)
            )
            break

        except pika.exceptions.AMQPConnectionError:
            print("Waiting for RabbitMQ...", flush=True)
            time.sleep(3)

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

    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue=QUEUE_NAME,
        routing_key="PaymentCompleted"
    )

    channel.queue_bind(
        exchange=EXCHANGE_NAME,
        queue=QUEUE_NAME,
        routing_key="OrderCancelled"
    )

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=handle_event
    )

    log_event(
        "notification",
        "INFO",
        "Notification Service is waiting for events"
    )

    channel.start_consuming()


if __name__ == "__main__":
    start_http_server(8001)
    main()