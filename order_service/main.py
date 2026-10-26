import json
import os
import time
import threading
from contextlib import asynccontextmanager

import pika
import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


SERVICE_ID = os.getenv("INSTANCE_NAME", "orders")
PORT = int(os.getenv("PORT", "8000"))
CONSUL_URL = os.getenv("CONSUL_URL", "http://consul:8500")
RABBITMQ_HOST = os.getenv("RABBITMQ_HOST", "rabbitmq")

EXCHANGE_NAME = "saga_events"
ORDER_QUEUE_NAME = "orders_payment_results"


class OrderItem(BaseModel):
    product_id: int = Field(gt=0, description="ID товара")
    quantity: int = Field(gt=0, description="Количество товара")


class Order(BaseModel):
    id: int
    user_id: int
    items: list[OrderItem]
    status: str = "CONFIRMED"


class CreateOrder(BaseModel):
    user_id: int = Field(gt=0)
    items: list[OrderItem] = Field(min_length=1)


# Сохраняем учебные заказы из ЛР №3.
orders = [
    Order(
        id=1,
        user_id=1,
        items=[
            OrderItem(product_id=1, quantity=2),
            OrderItem(product_id=2, quantity=1)
        ]
    ),
    Order(
        id=2,
        user_id=1,
        items=[
            OrderItem(product_id=1, quantity=1)
        ]
    ),
    Order(
        id=3,
        user_id=2,
        items=[
            OrderItem(product_id=2, quantity=3)
        ]
    )
]

next_order_id = 4


def register_in_consul():
    payload = {
        "Name": "orders",
        "ID": SERVICE_ID,
        "Address": SERVICE_ID,
        "Port": PORT
    }

    for attempt in range(10):
        try:
            response = requests.put(
                f"{CONSUL_URL}/v1/agent/service/register",
                json=payload,
                timeout=3
            )
            response.raise_for_status()
            print(f"Registered {SERVICE_ID} in Consul")
            return
        except requests.RequestException as error:
            print(f"Consul is not ready: {error}")
            time.sleep(2)

    print("Could not register in Consul")


def deregister_from_consul():
    try:
        requests.put(
            f"{CONSUL_URL}/v1/agent/service/deregister/{SERVICE_ID}",
            timeout=3
        )
        print(f"Deregistered {SERVICE_ID} from Consul")
    except requests.RequestException as error:
        print(f"Could not deregister from Consul: {error}")


def connect_rabbitmq():
    for attempt in range(10):
        try:
            connection = pika.BlockingConnection(
                pika.ConnectionParameters(
                    host=RABBITMQ_HOST,
                    heartbeat=60
                )
            )
            return connection

        except pika.exceptions.AMQPConnectionError:
            print("Waiting for RabbitMQ...")
            time.sleep(2)

    raise RuntimeError("Cannot connect to RabbitMQ")


def setup_rabbitmq():
    connection = connect_rabbitmq()

    try:
        channel = connection.channel()

        channel.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type="topic",
            durable=True
        )

        print("RabbitMQ exchange is ready")
    finally:
        connection.close()


def publish_event(event_type, data):
    connection = connect_rabbitmq()

    try:
        channel = connection.channel()

        channel.exchange_declare(
            exchange=EXCHANGE_NAME,
            exchange_type="topic",
            durable=True
        )

        message = {
            "event": event_type,
            "data": data
        }

        channel.basic_publish(
            exchange=EXCHANGE_NAME,
            routing_key=event_type,
            body=json.dumps(message).encode("utf-8"),
            properties=pika.BasicProperties(
                delivery_mode=2,
                content_type="application/json"
            )
        )

        print(
            f"Published event: {event_type}, "
            f"data: {data}"
        )
    finally:
        connection.close()

def handle_payment(channel, method, properties, body):
    message = json.loads(body)
    event_type = message.get("event_type") or message.get("event")
    data = message["data"]

    order_id = data["order_id"]

    for order in orders:
        if order.id != order_id:
            continue

        if order.status != "PENDING":
            print(f"Order {order_id} already processed", flush=True)
            break

        if event_type == "PaymentCompleted":
            order.status = "CONFIRMED"
            print(
                f"Order {order_id}: PENDING -> CONFIRMED",
                flush=True
            )

        elif event_type == "PaymentFailed":
            order.status = "CANCELLED"
            print(
                f"Order {order_id}: PENDING -> CANCELLED",
                flush=True
            )

            publish_event(
                "OrderCancelled",
                {
                    "order_id": order_id,
                    "reason": data.get("reason", "Payment failed")
                }
            )

        break

    channel.basic_ack(delivery_tag=method.delivery_tag)


def consume_payment_events():
    while True:
        connection = None

        try:
            connection = connect_rabbitmq()
            channel = connection.channel()

            channel.exchange_declare(
                exchange=EXCHANGE_NAME,
                exchange_type="topic",
                durable=True
            )

            channel.queue_declare(
                queue=ORDER_QUEUE_NAME,
                durable=True
            )

            for event_type in ["PaymentCompleted", "PaymentFailed"]:
                channel.queue_bind(
                    exchange=EXCHANGE_NAME,
                    queue=ORDER_QUEUE_NAME,
                    routing_key=event_type
                )

            channel.basic_qos(prefetch_count=1)

            channel.basic_consume(
                queue=ORDER_QUEUE_NAME,
                on_message_callback=handle_payment
            )

            print(
                "Orders is waiting for payment events...",
                flush=True
            )

            channel.start_consuming()

        except Exception as error:
            print(f"RabbitMQ consumer error: {error}", flush=True)
            time.sleep(3)

        finally:
            if connection is not None and connection.is_open:
                connection.close()

@asynccontextmanager
async def lifespan(app: FastAPI):
    # Действия при запуске сервиса
    register_in_consul()
    setup_rabbitmq()

    consumer_thread = threading.Thread(
        target=consume_payment_events,
        daemon=True
    )
    consumer_thread.start()

    try:
        yield
    finally:
        # Действия при завершении сервиса
        deregister_from_consul()


app = FastAPI(
    title="Order Service",
    description="REST API для управления заказами и реализации Saga",
    version="1.0.0",
    lifespan=lifespan
)


@app.get(
    "/orders",
    response_model=list[Order],
    tags=["Orders"],
    summary="Получение всех заказов"
)
def get_orders():
    return orders


@app.get(
    "/orders/user/{user_id}",
    response_model=list[Order],
    tags=["Orders"],
    summary="Получение заказов пользователя"
)
def get_user_orders(user_id: int):
    return [
        order for order in orders
        if order.user_id == user_id
    ]


@app.get(
    "/orders/{order_id}",
    response_model=Order,
    tags=["Orders"],
    summary="Получение заказа по ID"
)
def get_order(order_id: int):
    for order in orders:
        if order.id == order_id:
            return order

    raise HTTPException(
        status_code=404,
        detail="Order not found"
    )


@app.post(
    "/orders",
    response_model=Order,
    status_code=201,
    tags=["Orders"],
    summary="Создание заказа"
)
def create_order(order_data: CreateOrder):
    global next_order_id

    order = Order(
        id=next_order_id,
        user_id=order_data.user_id,
        items=order_data.items,
        status="PENDING"
    )

    orders.append(order)
    next_order_id += 1

    publish_event(
        "OrderCreated",
        {
            "order_id": order.id,
            "user_id": order.user_id,
            "items": [
                item.model_dump()
                for item in order.items
            ]
        }
    )

    return order
