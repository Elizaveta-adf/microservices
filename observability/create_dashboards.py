import json
from pathlib import Path

folder = Path(__file__).parent / "grafana" / "dashboards"
folder.mkdir(parents=True, exist_ok=True)


def panel(id, title, query, x, y, kind="timeseries", unit="short"):
    return {
        "id": id,
        "title": title,
        "type": kind,
        "datasource": {
            "type": "prometheus",
            "uid": "${DS_PROMETHEUS}"
        },
        "gridPos": {
            "x": x,
            "y": y,
            "w": 12,
            "h": 8
        },
        "targets": [
            {
                "expr": query,
                "refId": "A"
            }
        ],
        "fieldConfig": {
            "defaults": {
                "unit": unit
            },
            "overrides": []
        }
    }


def save_dashboard(filename, uid, title, panels):
    dashboard = {
        "id": None,
        "uid": uid,
        "title": title,
        "tags": ["microservices", "lab8"],
        "timezone": "browser",
        "schemaVersion": 39,
        "version": 1,
        "refresh": "5s",
        "time": {
            "from": "now-30m",
            "to": "now"
        },
        "templating": {
            "list": [
                {
                    "name": "DS_PROMETHEUS",
                    "type": "datasource",
                    "query": "prometheus",
                    "hide": 2
                }
            ]
        },
        "panels": panels
    }

    with open(folder / filename, "w", encoding="utf-8") as file:
        json.dump(dashboard, file, ensure_ascii=False, indent=2)

    print(f"Created: {filename}")


technical = [
    panel(
        1, "Service availability",
        'up{job!="api_gateway"}',
        0, 0, "stat"
    ),
    panel(
        2, "HTTP requests total",
        'sum by (service) (http_requests_total{endpoint!="/metrics"})',
        12, 0
    ),
    panel(
        3, "Requests per second (RPS)",
        'sum by (service) (rate(http_requests_total{endpoint!="/metrics"}[1m]))',
        0, 8
    ),
    panel(
        4, "HTTP errors (4xx and 5xx)",
        'sum by (service) (http_requests_total{status=~"4..|5.."}) or (0 * sum by (service) (http_requests_total))',
        12, 8
    ),
    panel(
        5, "Average response time",
        'sum by (service) (rate(http_request_duration_seconds_sum{endpoint!="/metrics"}[5m])) / sum by (service) (rate(http_request_duration_seconds_count{endpoint!="/metrics"}[5m]))',
        0, 16, unit="s"
    ),
    panel(
        6, "Response time P95",
        'histogram_quantile(0.95, sum by (le, service) (rate(http_request_duration_seconds_bucket{endpoint!="/metrics"}[5m])))',
        12, 16, unit="s"
    )
]


business = [
    panel(
        1, "Orders created",
        "sum(orders_created_total)",
        0, 0, "stat"
    ),
    panel(
        2, "Total order amount",
        "sum(orders_amount_total)",
        12, 0, "stat"
    ),
    panel(
        3, "Successful payments",
        'sum(payments_total{status="success"})',
        0, 8
    ),
    panel(
        4, "Failed payments",
        'sum(payments_total{status="failed"})',
        12, 8
    ),
    panel(
        5, "Payment success rate",
        '100 * sum(payments_total{status="success"}) / sum(payments_total)',
        0, 16, "stat", "percent"
    ),
    panel(
        6, "Notifications sent",
        "sum by (event_type) (notifications_total)",
        12, 16
    ),
    panel(
        7, "Cancelled orders",
        "sum(orders_cancelled_total)",
        0, 24
    ),
    panel(
        8, "Order creation dynamics",
        "sum(orders_created_total)",
        12, 24
    )
]


save_dashboard(
    "technical.json",
    "lab8-technical",
    "Microservices Technical Dashboard",
    technical
)

save_dashboard(
    "business.json",
    "lab8-business",
    "Microservices Business Dashboard",
    business
)