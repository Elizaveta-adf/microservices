const client = require("prom-client");

client.collectDefaultMetrics();

const requests = new client.Counter({
    name: "http_requests_total",
    help: "Total HTTP requests",
    labelNames: ["service", "method", "endpoint", "status"]
});

const errors = new client.Counter({
    name: "errors_total",
    help: "Total HTTP errors",
    labelNames: ["service", "status"]
});

const duration = new client.Histogram({
    name: "http_request_duration_seconds",
    help: "HTTP request duration",
    labelNames: ["service", "method", "endpoint"]
});

const inProgress = new client.Gauge({
    name: "http_requests_in_progress",
    help: "HTTP requests in progress",
    labelNames: ["service"]
});

function setupMetrics(app) {
    app.get("/metrics", async (req, res) => {
        res.set("Content-Type", client.register.contentType);
        res.end(await client.register.metrics());
    });

    app.use((req, res, next) => {
        const start = process.hrtime.bigint();
        const service = "api_gateway";
        const method = req.method;

        const endpoint = req.path.replace(
            /\/\d+(?=\/|$)/g,
            "/:id"
        );

        inProgress.labels(service).inc();

        let recorded = false;

        function record() {
            if (recorded) return;
            recorded = true;

            const status = String(
                res.writableFinished ? res.statusCode : 499
            );

            const seconds =
                Number(process.hrtime.bigint() - start) / 1e9;

            requests.labels(
                service, method, endpoint, status
            ).inc();

            duration.labels(
                service, method, endpoint
            ).observe(seconds);

            if (Number(status) >= 400) {
                errors.labels(service, status).inc();
            }

            inProgress.labels(service).dec();
        }

        res.once("finish", record);
        res.once("close", record);

        next();
    });
}

module.exports = { setupMetrics };