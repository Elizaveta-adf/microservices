import time

from fastapi import Response
from prometheus_client import (
    Counter,
    Histogram,
    Gauge,
    generate_latest,
    CONTENT_TYPE_LATEST
)


HTTP_REQUESTS = Counter(
    "http_requests_total",
    "Total HTTP requests",
    ["service", "method", "endpoint", "status"]
)

HTTP_ERRORS = Counter(
    "errors_total",
    "Total HTTP errors",
    ["service", "status"]
)

HTTP_DURATION = Histogram(
    "http_request_duration_seconds",
    "HTTP request duration",
    ["service", "method", "endpoint"]
)

HTTP_IN_PROGRESS = Gauge(
    "http_requests_in_progress",
    "HTTP requests in progress",
    ["service"]
)


def setup_metrics(app, service_name):

    @app.get("/metrics", include_in_schema=False)
    def metrics_endpoint():
        return Response(
            content=generate_latest(),
            media_type=CONTENT_TYPE_LATEST
        )

    @app.middleware("http")
    async def metrics_middleware(request, call_next):

        if request.url.path == "/metrics":
            return await call_next(request)

        start = time.perf_counter()
        status = 500

        HTTP_IN_PROGRESS.labels(service_name).inc()

        try:
            response = await call_next(request)
            status = response.status_code
            return response

        finally:
            route = request.scope.get("route")
            endpoint = getattr(route, "path", "unmatched")
            method = request.method

            HTTP_REQUESTS.labels(
                service_name,
                method,
                endpoint,
                str(status)
            ).inc()

            HTTP_DURATION.labels(
                service_name,
                method,
                endpoint
            ).observe(time.perf_counter() - start)

            if status >= 400:
                HTTP_ERRORS.labels(
                    service_name,
                    str(status)
                ).inc()

            HTTP_IN_PROGRESS.labels(service_name).dec()