
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException
from pydantic import BaseModel, Field

from event_store import get_events
from order_aggregate import rehydrate
from order_commands import create_order, pay_order, cancel_order
from order_projection import get_order_projection, get_all_projections
from order_consumer import consume_order_events


class OrderItem(BaseModel):
    product_id: int = Field(gt=0)
    quantity: int = Field(gt=0)


class CreateOrder(BaseModel):
    user_id: int = Field(gt=0)
    items: list[OrderItem] = Field(min_length=1)
    amount: float = Field(gt=0)


next_order_id = 1


@asynccontextmanager
async def lifespan(app: FastAPI):
    consumer_thread = threading.Thread(
        target=consume_order_events,
        daemon=True
    )
    consumer_thread.start()

    yield


app = FastAPI(
    title="Order Service — CQRS + Event Sourcing",
    lifespan=lifespan
)


@app.post("/orders", status_code=201)
def create_order_endpoint(order_data: CreateOrder):
    global next_order_id

    order_id = next_order_id
    next_order_id += 1

    try:
        event = create_order(
            order_id=order_id,
            user_id=order_data.user_id,
            items=[item.model_dump() for item in order_data.items],
            amount=order_data.amount
        )
        return {
            "order_id": order_id,
            "event": event
        }
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/orders/{order_id}/pay")
def pay_order_endpoint(order_id: int):
    try:
        event = pay_order(order_id)
        return {"event": event}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.post("/orders/{order_id}/cancel")
def cancel_order_endpoint(order_id: int):
    try:
        event = cancel_order(order_id)
        return {"event": event}
    except ValueError as error:
        raise HTTPException(status_code=400, detail=str(error))


@app.get("/orders")
def get_orders():
    return get_all_projections()


@app.get("/orders/user/{user_id}")
def get_user_orders(user_id: int):
    return [
        order for order in get_all_projections()
        if order["user_id"] == user_id
    ]


@app.get("/orders/{order_id}")
def get_order(order_id: int):
    order = get_order_projection(order_id)

    if order is None:
        raise HTTPException(
            status_code=404,
            detail="Order not found in read model"
        )

    return order
