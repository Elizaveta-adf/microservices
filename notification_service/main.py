import json
import os
import time

import pika


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
EXCHANGE_NAME = "saga_events"
QUEUE_NAME = "notification_events"


def handle_event(channel, method, properties, body):
    message = json.loads(body)

    event_type = message.get("event_type") or message.get("event")
    data = message["data"]

    order_id = data["order_id"]

    print(
        f"Received event: {event_type}, order_id={order_id}",
        flush=True
    )

    if event_type == "PaymentCompleted":
        print(
            f"Отправлено уведомление клиенту: "
            f"заказ {order_id} успешно оплачен",
            flush=True
        )

    elif event_type == "OrderCancelled":
        print(
            f"Отправлено уведомление клиенту: "
            f"заказ {order_id} отменён",
            flush=True
        )

    channel.basic_ack(delivery_tag=method.delivery_tag)


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

    print(
        "Notification Service is waiting for events...",
        flush=True
    )

    channel.start_consuming()


if __name__ == "__main__":
    main()