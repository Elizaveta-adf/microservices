import grpc

import payment_pb2
import payment_pb2_grpc


channel = grpc.insecure_channel("localhost:50051")
client = payment_pb2_grpc.PaymentServiceStub(channel)

for simulate_failure in [False, True]:
    try:
        response = client.CheckPaymentStatus(
            payment_pb2.PaymentRequest(
                order_id="1",
                amount=100.0,
                simulate_failure=simulate_failure
            ),
            timeout=3
        )

        print(
            f"SUCCESS: status={response.status}, "
            f"transaction_id={response.transaction_id}"
        )

    except grpc.RpcError as error:
        print(f"ERROR: {error.code().name}")