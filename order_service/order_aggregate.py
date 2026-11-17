
def apply(state, event):
    event_type = event["eventType"]
    payload = event["payload"]

    if event_type == "OrderCreated":
        state = {
            "id": event["orderId"],
            "user_id": payload["user_id"],
            "items": payload["items"],
            "amount": payload["amount"],
            "status": "CREATED"
        }

    elif event_type == "OrderPaid":
        state["status"] = "PAID"

    elif event_type == "OrderCancelled":
        state["status"] = "CANCELLED"

    return state


def rehydrate(events):
    state = None

    for event in events:
        state = apply(state, event)

    return state

