import time
import uuid
from concurrent import futures

import grpc

import payment_pb2
import payment_pb2_grpc


class PaymentServicer(payment_pb2_grpc.PaymentServiceServicer):

    def CheckPaymentStatus(self, request, context):
        print(
            f"gRPC request: order_id={request.order_id}, "
            f"amount={request.amount}, "
            f"simulate_failure={request.simulate_failure}",
            flush=True
        )

        if request.simulate_failure:
            print("Simulating payment service failure", flush=True)

            context.abort(
                grpc.StatusCode.UNAVAILABLE,
                "Payment service temporarily unavailable"
            )

        return payment_pb2.PaymentResponse(
            transaction_id=str(uuid.uuid4()),
            status="SUCCESS",
            message="Payment completed successfully"
        )


def serve():
    server = grpc.server(futures.ThreadPoolExecutor(max_workers=10))

    payment_pb2_grpc.add_PaymentServiceServicer_to_server(
        PaymentServicer(),
        server
    )

    server.add_insecure_port("[::]:50051")
    server.start()

    print("Payment gRPC server started on port 50051", flush=True)

    server.wait_for_termination()


if __name__ == "__main__":
    serve()