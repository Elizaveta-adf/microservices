import json
import time
from datetime import datetime, timezone
from tracing import get_trace_id


def log_event(service_name, level, message, trace_id="", **fields):
    data = {
        "timestamp": datetime.now(timezone.utc).isoformat(),
        "service_name": service_name,
        "level": level,
        "trace_id": trace_id or get_trace_id(),
        "message": message,
        **fields
    }

    print(json.dumps(data, ensure_ascii=False), flush=True)


def setup_http_logs(app, service_name):
    @app.middleware("http")
    async def logging_middleware(request, call_next):
        start = time.perf_counter()
        status = 500

        try:
            response = await call_next(request)
            status = response.status_code
            return response

        finally:
            duration = round(time.perf_counter() - start, 3)

            log_event(
                service_name=service_name,
                level="ERROR" if status >= 400 else "INFO",
                message="HTTP request",
                method=request.method,
                endpoint=request.url.path,
                status=status,
                duration_seconds=duration
            )