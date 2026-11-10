
from collections import defaultdict
from datetime import datetime, timezone
from uuid import uuid4
from threading import Lock


events = defaultdict(list)
lock = Lock()


def get_events(order_id):
    with lock:
        return [event.copy() for event in events[order_id]]


def save_event(order_id, event_type, payload, expected_version):
    with lock:
        current_version = len(events[order_id])

        if current_version != expected_version:
            raise ValueError("Order version conflict")

        event = {
            "eventId": str(uuid4()),
            "orderId": order_id,
            "eventType": event_type,
            "payload": payload,
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "version": current_version + 1
        }

        events[order_id].append(event)

        return event
