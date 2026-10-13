
import os
import time

import requests
from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field


app = FastAPI(
    title="Order Service",
    description="REST API для получения заказов пользователей",
    version="1.0.0",
    openapi_version="3.1.0"
)

SERVICE_ID = os.getenv("INSTANCE_NAME", "orders")
PORT = int(os.getenv("PORT", "8000"))
CONSUL_URL = os.getenv("CONSUL_URL", "http://consul:8500")


class OrderItem(BaseModel):
    product_id: int = Field(gt=0, description="ID товара")
    quantity: int = Field(gt=0, description="Количество товара")


class Order(BaseModel):
    id: int
    user_id: int
    items: list[OrderItem]


# Учебные данные заказов.
# Здесь хранятся только идентификаторы товаров,
# а не названия или цены из Catalog.
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


@app.on_event("startup")
def startup_event():
    register_in_consul()


@app.on_event("shutdown")
def shutdown_event():
    deregister_from_consul()


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
