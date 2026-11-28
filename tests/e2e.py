import json
import time
import base64
from uuid import uuid4
from urllib.request import Request, urlopen
from urllib.error import HTTPError
import atexit

from opentelemetry import trace, propagate, context
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter


BASE_URL = "http://localhost:8081"
token = None

provider = TracerProvider(
    resource=Resource.create({
        "service.name": "e2e-test"
    })
)

provider.add_span_processor(
    BatchSpanProcessor(
        OTLPSpanExporter(
            endpoint="http://localhost:4318/v1/traces"
        )
    )
)

trace.set_tracer_provider(provider)

tracer = trace.get_tracer("e2e-test")

span = tracer.start_span("Lab9 E2E scenario")

ctx_token = context.attach(
    trace.set_span_in_context(span)
)

print("Trace ID:", format(
    span.get_span_context().trace_id, "032x"
))


@atexit.register
def finish_trace():
    context.detach(ctx_token)
    span.end()
    provider.shutdown()


def request(method, path, data=None, expected=200):
    headers = {"Content-Type": "application/json"}
    propagate.inject(headers)

    if token:
        headers["Authorization"] = f"Bearer {token}"

    body = json.dumps(data).encode() if data is not None else None

    req = Request(
        BASE_URL + path,
        data=body,
        headers=headers,
        method=method
    )

    with urlopen(req, timeout=15) as response:
        assert response.status == expected
        return json.loads(response.read())


def wait_for_order(order_id):
    for _ in range(20):
        try:
            order = request("GET", f"/orders/{order_id}")

            if order["status"] in ("CONFIRMED", "CANCELLED"):
                return order

        except HTTPError as error:
            if error.code != 404:
                raise

        time.sleep(1)

    raise RuntimeError("Order processing timeout")


# 1. Registration
user = {
    "email": f"lab9-{uuid4().hex[:8]}@example.com",
    "password": "Lab9Test123!"
}

request("POST", "/auth/register", user)
print("[PASS] 1. User registered")
print("Email:", user["email"])


# 2. Login and JWT
login = request("POST", "/auth/login", user)
token = login["access_token"]

payload = token.split(".")[1]
payload += "=" * (-len(payload) % 4)

user_id = json.loads(
    base64.urlsafe_b64decode(payload)
)["sub"]

print("[PASS] 2. JWT received")
print("User ID:", user_id)


# 3. Catalog
catalog = request("GET", "/catalog/products")

assert len(catalog["products"]) > 0

product = catalog["products"][0]

print("[PASS] 3. Catalog received")
print("Catalog instance:", catalog["instance_id"])
print("Product:", product["name"])
print("Price:", product["price"])


# Analytics before order creation
before = request("GET", "/analytics/summary")


# 4-6. Order creation and automatic payment
order_data = {
    "user_id": user_id,
    "items": [
        {
            "product_id": product["id"],
            "quantity": 1
        }
    ],
    "amount": product["price"]
}

for attempt in range(2):
    created = request(
        "POST",
        "/orders",
        order_data,
        expected=201
    )

    order_id = created["order_id"]

    print("[PASS] 4. Order created:", order_id)

    order = wait_for_order(order_id)

    if order["status"] == "CONFIRMED":
        break

    print("Payment declined. Trying next order.")

assert order["status"] == "CONFIRMED"
assert str(order["user_id"]) == str(user_id)

print("[PASS] 5. Automatic payment completed")
print("[PASS] 6. Order status: CONFIRMED")


# 7. Analytics verification
for _ in range(20):
    after = request("GET", "/analytics/summary")

    if (
        after["total_orders"] > before["total_orders"]
        and after["paid_amount"]
        >= before["paid_amount"] + product["price"]
        and after["status_counts"]["CONFIRMED"]
        > before["status_counts"]["CONFIRMED"]
    ):
        break

    time.sleep(1)

else:
    raise RuntimeError("Analytics was not updated")

print("[PASS] 7. Analytics updated")
print("Orders:", before["total_orders"],
      "->", after["total_orders"])
print("Paid amount:", before["paid_amount"],
      "->", after["paid_amount"])
print("Confirmed:", before["status_counts"]["CONFIRMED"],
      "->", after["status_counts"]["CONFIRMED"])

print()
print("E2E TEST PASSED: 7/7")