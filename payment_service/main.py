import json
import os
import time
import uuid

import pika


RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")
EXCHANGE_NAME = "saga_events"
QUEUE_NAME = "payment_order_created"


def process_order(channel, method, properties, body):
    event = json.loads(body)
    data = event["data"]
    order_id = data["order_id"]

    print(f"Received OrderCreated: order_id={order_id}", flush=True)

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

    channel.basic_publish(
        exchange=EXCHANGE_NAME,
        routing_key=event_type,
        body=json.dumps(message),
        properties=pika.BasicProperties(delivery_mode=2)
    )

    print(f"Published {event_type}: {result}", flush=True)

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
        routing_key="OrderCreated"
    )

    channel.basic_qos(prefetch_count=1)

    channel.basic_consume(
        queue=QUEUE_NAME,
        on_message_callback=process_order
    )

    print("Payment Service is waiting for OrderCreated...", flush=True)

    channel.start_consuming()


if __name__ == "__main__":
    main()