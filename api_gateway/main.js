require("./tracing");

const { trace } = require("@opentelemetry/api");
const express = require("express");
const jwt = require("jsonwebtoken");
const { rateLimit } = require("express-rate-limit");
const { createProxyMiddleware } = require("http-proxy-middleware");

const app = express();

const { setupMetrics } = require("./metrics");

setupMetrics(app);

// ЛР8. Структурированное логирование
app.use((req, res, next) => {
    const start = process.hrtime.bigint();
    const traceId = trace.getActiveSpan()
        ?.spanContext().traceId || "";

    res.on("finish", () => {
        const duration = Number(
            process.hrtime.bigint() - start
        ) / 1e9;

        console.log(JSON.stringify({
            timestamp: new Date().toISOString(),
            service_name: "api_gateway",
            level: res.statusCode >= 400 ? "ERROR" : "INFO",
            trace_id: traceId,
            message: "HTTP request",
            method: req.method,
            endpoint: req.path,
            status: res.statusCode,
            duration_seconds: Number(duration.toFixed(3))
        }));
    });

    next();
});
const JWT_SECRET = process.env.JWT_SECRET;

if (!JWT_SECRET) {
    throw new Error("JWT_SECRET is required");
}

// Общий лимит: 100 запросов за 15 минут
const limiter = rateLimit({
    windowMs: 15 * 60 * 1000,
    limit: 100,
    legacyHeaders: true,
    standardHeaders: false
});

// Для логина: 5 попыток за 15 минут
const loginLimiter = rateLimit({
    windowMs: 15 * 60 * 1000,
    limit: 5,
    legacyHeaders: true,
    standardHeaders: false
});

app.use(limiter);

app.use((req, res, next) => {
    if (
        req.method === "POST" &&
        ["/auth/login", "/auth/api/auth/login"].includes(req.path)
    ) {
        return loginLimiter(req, res, next);
    }
    next();
});

// Проверка JWT
function authMiddleware(req, res, next) {
    // Не доверяем заголовкам роли, присланным клиентом
    delete req.headers["x-user-id"];
    delete req.headers["x-user-role"];

    const publicPaths = [
        "/auth/register",
        "/auth/login",
        "/auth/api/auth/register",
        "/auth/api/auth/login",
        "/auth/docs",
        "/auth/openapi.json",
        "/catalog/docs",
        "/catalog/openapi.json",
        "/orders/docs",
        "/orders/openapi.json"
    ];

    if (publicPaths.includes(req.path)) {
        return next();
    }

    const authorization = req.headers.authorization;

    if (!authorization || !authorization.startsWith("Bearer ")) {
        return res.status(401).json({ error: "No token" });
    }

    const token = authorization.slice(7);

    try {
        const decoded = jwt.verify(token, JWT_SECRET, {
            algorithms: ["HS256"]
        });

        if (
            !decoded.sub ||
            !["user", "admin"].includes(decoded.role) ||
            typeof decoded.exp !== "number"
        ) {
            return res.status(401).json({ error: "Invalid token" });
        }

        req.user = decoded;
        next();
    } catch (error) {
        return res.status(401).json({ error: "Invalid token" });
    }
}

app.use(authMiddleware);

// Передача запроса внутренним сервисам через Nginx
app.use(createProxyMiddleware({
    target: "http://nginx:80",
    changeOrigin: true,
    on: {
        proxyReq: (proxyReq, req) => {
            if (req.user) {
                proxyReq.setHeader("X-User-Id", req.user.sub);
                proxyReq.setHeader("X-User-Role", req.user.role);
            }
        }
    }
}));

app.listen(3000, "0.0.0.0", () => {
    console.log("API Gateway started on port 3000");
});
