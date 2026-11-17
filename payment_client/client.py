import time
import grpc
import pybreaker
import json

import payment_pb2
import payment_pb2_grpc


breaker = pybreaker.CircuitBreaker(
    fail_max=3,
    reset_timeout=10
)


from datetime import datetime


class CircuitBreakerListener(pybreaker.CircuitBreakerListener):

    def state_change(self, cb, old_state, new_state):
        timestamp = datetime.now().strftime("%H:%M:%S")

        print(
            f"[{timestamp}] Circuit Breaker: "
            f"{old_state.name.upper()} -> {new_state.name.upper()}",
            flush=True
        )


breaker.add_listener(CircuitBreakerListener())


def check_payment(order_id, simulate_failure=False):

    with grpc.insecure_channel("payment:50051") as channel:
        client = payment_pb2_grpc.PaymentServiceStub(channel)

        response = client.CheckPaymentStatus(
            payment_pb2.PaymentRequest(
                order_id=str(order_id),
                amount=100.0,
                simulate_failure=simulate_failure
            ),
            timeout=3
        )

        return {
            "transaction_id": response.transaction_id,
            "status": response.status,
            "message": response.message
        }


def fallback():
    return {
        "transaction_id": "",
        "status": "PROCESSING",
        "message": "Платежная система временно недоступна, попробуйте позже"
    }


@breaker
def protected_payment(order_id, simulate_failure=False):
    return check_payment(order_id, simulate_failure)


def safe_payment(order_id, simulate_failure=False):
    try:
        return protected_payment(order_id, simulate_failure)
    except (pybreaker.CircuitBreakerError, grpc.RpcError):
        return fallback()


if __name__ == "__main__":

    print("\n1. Успешные запросы")

    for i in range(5):
        print(json.dumps(safe_payment(i + 1), ensure_ascii=False))

    print("\n2. Имитация ошибок")

    for i in range(4):
        print(json.dumps(
            safe_payment(i + 10, simulate_failure=True),
            ensure_ascii=False
        ))

    print("\n3. Ожидание восстановления")
    time.sleep(11)

    print("\n4. Проверка восстановления")
    print(json.dumps(safe_payment(20), ensure_ascii=False))