
from threading import Lock

read_orders = {}
read_lock = Lock()


def apply_projection(event):
    order_id = event["orderId"]
    event_type = event["eventType"]
    payload = event["payload"]
    version = event["version"]

    with read_lock:
        current = read_orders.get(order_id)

        if current and version <= current["version"]:
            return

        if event_type == "OrderCreated":
            read_orders[order_id] = {
                "id": order_id,
                "user_id": payload["user_id"],
                "items": payload["items"],
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


def get_order_projection(order_id):
    with read_lock:
        order = read_orders.get(order_id)
        if not order:
            return None

        return {
            key: value
            for key, value in order.items()
            if key != "version"
        }


def get_all_projections():
    with read_lock:
        return [
            {
                key: value
                for key, value in order.items()
                if key != "version"
            }
            for order in read_orders.values()
        ]
