import json
import os
import time
import uuid
import threading
from grpc_server import serve
from json_logger import log_event

import pika

from tracing import setup_tracing
from opentelemetry import propagate
from opentelemetry.trace import SpanKind

tracer = setup_tracing("payment")
from prometheus_client import Counter, start_http_server

PAYMENTS = Counter(
    "payments_total",
    "Total processed payments",
    ["status"]
)

PAYMENTS.labels(status="success")
PAYMENTS.labels(status="failed")

RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
EXCHANGE_NAME = "saga_events"
QUEUE_NAME = "payment_order_created"


def process_order(channel, method, properties, body):
    carrier = properties.headers or {}
    parent_context = propagate.extract(carrier)

    with tracer.start_as_current_span(
        "Process OrderCreated",
        context=parent_context,
        kind=SpanKind.CONSUMER
    ) as span:

        event = json.loads(body)
        data = event["data"]
        order_id = data["order_id"]

        span.set_attribute("order.id", order_id)
        span.set_attribute("messaging.system", "rabbitmq")

        log_event(
            "payment",
            "INFO",
            "Received OrderCreated",
            order_id=order_id
        )

        if order_id % 2 == 1:
            event_type = "PaymentCompleted"

            result = {
                "order_id": order_id,
                "transaction_id": str(uuid.uuid4())
            }
        else:
            event_type = "PaymentFailed"

            result = {
                "order_id": order_id,
                "reason": "Payment declined (test scenario)"
            }

        message = {
            "event_type": event_type,
            "data": result
        }

        with tracer.start_as_current_span(
            "RabbitMQ publish " + event_type,
            kind=SpanKind.PRODUCER
        ):
            outgoing_headers = {}
            propagate.inject(outgoing_headers)

            channel.basic_publish(
                exchange=EXCHANGE_NAME,
                routing_key=event_type,
                body=json.dumps(message),
                properties=pika.BasicProperties(
                    delivery_mode=2,
                    headers=outgoing_headers
                )
            )

            log_event(
                "payment",
                "INFO" if event_type == "PaymentCompleted" else "ERROR",
                "Published " + event_type,
                event_type=event_type,
                order_id=order_id
            )
        PAYMENTS.labels(
            status="success"
            if event_type == "PaymentCompleted"
            else "failed"
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
        routing_key="OrderCreated"
    )

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=process_order
    )

    log_event(
        "payment",
        "INFO",
        "Payment Service is waiting for OrderCreated"
    )

    channel.start_consuming()


if __name__ == "__main__":
    start_http_server(8001)
    threading.Thread(target=serve, daemon=True).start()
    main()