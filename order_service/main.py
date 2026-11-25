
import threading
from contextlib import asynccontextmanager

from fastapi import FastAPI, HTTPException, Header, Depends
from fastapi.security import HTTPBearer
from pydantic import BaseModel, Field

from event_store import get_events
from order_aggregate import rehydrate
from order_commands import create_order, pay_order, cancel_order
from order_projection import get_order_projection, get_all_projections
from order_consumer import consume_order_events
from rabbitmq_bridge import consume_bridge_events

from prometheus_client import Counter

ORDERS_CREATED = Counter(
    "orders_created_total",
    "Total created orders"
)

ORDERS_AMOUNT = Counter(
    "orders_amount_total",
    "Total amount of created orders"
)

ORDERS_CANCELLED = Counter(
    "orders_cancelled_total",
    "Total cancelled orders"
)

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

    bridge_thread = threading.Thread(
        target=consume_bridge_events,
        daemon=True
    )
    bridge_thread.start()

    yield


app = FastAPI(
    title="Order Service — CQRS + Event Sourcing",
    lifespan=lifespan,
    docs_url="/orders/docs",
    openapi_url="/orders/openapi.json"
)

bearer_scheme = HTTPBearer(auto_error=False)


@app.post(
    "/orders",
    status_code=201,
    dependencies=[Depends(bearer_scheme)]
)
def create_order_endpoint(
    order_data: CreateOrder,
    x_user_role: str = Header(default="", alias="X-User-Role")
):
    global next_order_id

    # Создавать заказ могут user и admin
    if x_user_role not in ("user", "admin"):
        raise HTTPException(
            status_code=403,
            detail="Forbidden: authentication required"
        )

    order_id = next_order_id
    next_order_id += 1

    try:
        event = create_order(
            order_id=order_id,
            user_id=order_data.user_id,
            items=[item.model_dump() for item in order_data.items],
            amount=order_data.amount
        )
        ORDERS_CREATED.inc()
        ORDERS_AMOUNT.inc(order_data.amount)
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
        ORDERS_CANCELLED.inc()
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


# ЛР8. Структурированное логирование
from json_logger import setup_http_logs

setup_http_logs(app, "orders")

from tracing import setup_tracing
from opentelemetry.instrumentation.fastapi import FastAPIInstrumentor

tracer = setup_tracing("orders")
FastAPIInstrumentor.instrument_app(app)

from metrics import setup_metrics

setup_metrics(app, "orders")