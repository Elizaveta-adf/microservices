const { NodeSDK } = require("@opentelemetry/sdk-node");
const {
    OTLPTraceExporter
} = require("@opentelemetry/exporter-trace-otlp-http");
const {
    HttpInstrumentation
} = require("@opentelemetry/instrumentation-http");

const sdk = new NodeSDK({
    serviceName: "api_gateway",

    traceExporter: new OTLPTraceExporter({
        url: "http://jaeger:4318/v1/traces"
    }),

    instrumentations: [
        new HttpInstrumentation()
    ]
});

sdk.start();

process.on("SIGTERM", () => {
    sdk.shutdown().finally(() => process.exit(0));
});