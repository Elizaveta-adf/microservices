
import json
import os
import time

from kafka import KafkaConsumer
from order_projection import apply_projection


KAFKA_SERVER = os.getenv("KAFKA_SERVER", "kafka:9092")
TOPIC = "orders-events"


def consume_order_events():
    while True:
        try:
            consumer = KafkaConsumer(
                TOPIC,
                bootstrap_servers=KAFKA_SERVER,
                group_id=None,
                auto_offset_reset="earliest",
                enable_auto_commit=True,
                value_deserializer=lambda value: json.loads(
                    value.decode("utf-8")
                )
            )

            print("Read model consumer started", flush=True)

            for message in consumer:
                apply_projection(message.value)
                print(
                    f"Read model updated: "
                    f"{message.value['eventType']}, "
                    f"order={message.value['orderId']}",
                    flush=True
                )

        except Exception as error:
            print(f"Read model consumer error: {error}", flush=True)
            time.sleep(3)
