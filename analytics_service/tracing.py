from opentelemetry import trace
from opentelemetry.sdk.resources import Resource
from opentelemetry.sdk.trace import TracerProvider
from opentelemetry.sdk.trace.export import BatchSpanProcessor
from opentelemetry.exporter.otlp.proto.http.trace_exporter import OTLPSpanExporter


def setup_tracing(service_name):
    resource = Resource.create({
        "service.name": service_name
    })

    provider = TracerProvider(resource=resource)

    exporter = OTLPSpanExporter(
        endpoint="http://jaeger:4318/v1/traces"
    )

    provider.add_span_processor(
        BatchSpanProcessor(exporter)
    )

    trace.set_tracer_provider(provider)

    return trace.get_tracer(service_name)


def get_trace_id():
    span = trace.get_current_span()
    context = span.get_span_context()

    if context.is_valid:
        return format(context.trace_id, "032x")

    return ""