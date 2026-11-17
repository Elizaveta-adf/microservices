from kafka_producer import publish_order_event
from event_store import get_events, save_event
from order_aggregate import rehydrate


def create_order(order_id, user_id, items, amount):
    events = get_events(order_id)
    state = rehydrate(events)

    if state is not None:
        raise ValueError("Order already exists")

    event = save_event(
        order_id=order_id,
        event_type="OrderCreated",
        payload={
            "user_id": user_id,
            "items": items,
            "amount": amount
        },
        expected_version=len(events)
    )
    publish_order_event(event)
    return event


def pay_order(order_id):
    events = get_events(order_id)
    state = rehydrate(events)

    if state is None:
        raise ValueError("Order not found")

    if state["status"] != "CREATED":
        raise ValueError("Order cannot be paid")

    event = save_event(
        order_id=order_id,
        event_type="OrderPaid",
        payload={},
        expected_version=len(events)
    )
    publish_order_event(event)
    return event


def cancel_order(order_id):
    events = get_events(order_id)
    state = rehydrate(events)

    if state is None:
        raise ValueError("Order not found")

    if state["status"] == "CANCELLED":
        raise ValueError("Order already cancelled")

    event = save_event(
        order_id=order_id,
        event_type="OrderCancelled",
        payload={},
        expected_version=len(events)
    )
    publish_order_event(event)
    return event
