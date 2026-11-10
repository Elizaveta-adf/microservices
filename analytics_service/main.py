
import json
import os
import threading
import time
from contextlib import asynccontextmanager

from fastapi import FastAPI
from kafka import KafkaConsumer


KAFKA_SERVER = os.getenv("KAFKA_SERVER", "kafka:9092")
TOPIC = "orders-events"

orders = {}
lock = threading.Lock()



def process_event(event):
    order_id = event["orderId"]
    event_type = event["eventType"]
    payload = event["payload"]
    version = event["version"]

    with lock:
        current = orders.get(order_id)

        if current and version <= current["version"]:
            return

        if event_type == "OrderCreated":
            orders[order_id] = {
                "amount": payload["amount"],
                "status": "CREATED",
                "version": version
            }

        elif event_type == "OrderPaid":
            if current and version == current["version"] + 1:
                current["status"] = "PAID"
                current["version"] = version

        elif event_type == "OrderCancelled":
            if current and version == current["version"] + 1:
                current["status"] = "CANCELLED"
                current["version"] = version


def consume_events():
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

            print("Analytics consumer started", flush=True)

            for message in consumer:
                process_event(message.value)
                print(
                    f"Analytics event: {message.value['eventType']}",
                    flush=True
                )

        except Exception as error:
            print(f"Analytics consumer error: {error}", flush=True)
            time.sleep(3)


@asynccontextmanager
async def lifespan(app: FastAPI):
    thread = threading.Thread(
        target=consume_events,
        daemon=True
    )
    thread.start()
    yield


app = FastAPI(
    title="Analytics Service",
    lifespan=lifespan
)


@app.get("/analytics/summary")
def get_summary():
    with lock:
        total_orders = len(orders)

        paid_amount = sum(
            order["amount"]
            for order in orders.values()
            if order["status"] == "PAID"
        )

        status_counts = {
            "CREATED": 0,
            "PAID": 0,
            "CANCELLED": 0
        }

        for order in orders.values():
            status_counts[order["status"]] += 1

        total_amount = sum(
            order["amount"]
            for order in orders.values()
        )

        average_amount = (
            total_amount / total_orders
            if total_orders > 0 else 0
        )

        return {
            "total_orders": total_orders,
            "paid_amount": paid_amount,
            "status_counts": status_counts,
            "average_amount": average_amount
        }
